"""
Entry point do agente de impressão v2.
Coordena system tray, WebSocket client e janela de configuração.

Threading model:
  - Main thread: tkinter (hidden root + config window as Toplevel)
  - Background thread 1: pystray (system tray icon)
  - Background thread 2: asyncio event loop (WebSocket client)
"""

import os
import sys
import asyncio
import logging
import threading
import tkinter as tk
import msvcrt
import socket
from contextlib import closing

# PyInstaller onefile: apontar escpos para capabilities.json no bundle (antes de importar printer_service)
if getattr(sys, "frozen", False):
    bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    os.environ.setdefault(
        "ESCPOS_CAPABILITIES_FILE",
        os.path.join(bundle_dir, "escpos", "capabilities.json"),
    )

import config
import printer_service
import windows_startup
from websocket_client import PrinterWebSocketClient
from tray import TrayIcon
from config_window import ConfigWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("printer_agent")

ACTIVATION_HOST = "127.0.0.1"
ACTIVATION_PORT = 52379
ACTIVATION_TOKEN = b"OPEN_CONFIG"


class SingleInstanceLock:
    """Trava simples por arquivo para garantir apenas uma instância do agente."""

    def __init__(self, lock_file: str):
        self._lock_file = lock_file
        self._fh = None

    def acquire(self) -> bool:
        os.makedirs(os.path.dirname(self._lock_file), exist_ok=True)
        self._fh = open(self._lock_file, "a+")
        try:
            self._fh.seek(0)
            msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            self._fh.seek(0)
            self._fh.write(str(os.getpid()))
            self._fh.flush()
            return True
        except OSError:
            return False

    def release(self) -> None:
        if not self._fh:
            return
        try:
            self._fh.seek(0)
            msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        try:
            self._fh.close()
        except OSError:
            pass
        self._fh = None


class ActivationServer:
    """Servidor local para receber sinal de ativacao da segunda execucao."""

    def __init__(self, on_activate):
        self._on_activate = on_activate
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        # Desbloqueia accept() com conexao local curta.
        try:
            with closing(socket.create_connection((ACTIVATION_HOST, ACTIVATION_PORT), timeout=0.2)):
                pass
        except OSError:
            pass

    def _serve(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((ACTIVATION_HOST, ACTIVATION_PORT))
            server.listen(2)
            server.settimeout(0.5)
            while not self._stop_event.is_set():
                try:
                    conn, _ = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                with conn:
                    try:
                        payload = conn.recv(64)
                    except OSError:
                        continue
                    if payload == ACTIVATION_TOKEN:
                        self._on_activate()


class PrinterAgent:
    def __init__(self):
        self._config = config.load_config()
        self._ws_client: PrinterWebSocketClient | None = None
        self._tray: TrayIcon | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tk_root: tk.Tk | None = None
        self._status = "disconnected"
        self._activation_server: ActivationServer | None = None
        self._pending_open_config = False

    def sync_windows_startup(self) -> None:
        desired = bool(self._config.get("start_with_windows", True))
        current = windows_startup.is_enabled()
        if desired and not getattr(sys, "frozen", False) and not current:
            return
        if desired == current:
            return
        ok, msg = windows_startup.set_enabled(desired)
        if ok:
            logger.info(msg)
        else:
            logger.warning(msg)

    def run(self, open_config_on_start: bool = False) -> None:
        print()
        print("=============================================")
        print("  Meu Atendimento - Agente de Impressão v2")
        print("=============================================")
        print("  O ícone do agente aparecerá na bandeja do")
        print("  sistema (área de notificação, perto do relógio).")
        print("  Clique com botão direito no ícone para opções.")
        print()
        print("  Pressione Ctrl+C para encerrar.")
        print("=============================================")
        print()

        self._activation_server = ActivationServer(self._request_open_config)
        self._activation_server.start()

        # Thread 2: asyncio event loop
        ws_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        ws_thread.start()

        # Thread 1: system tray (background)
        self._tray = TrayIcon(
            on_open_config=self._request_open_config,
            on_reconnect=self._reconnect,
            on_test_print=self._test_print,
            on_exit=self._request_exit,
        )
        tray_thread = threading.Thread(target=self._tray.start, daemon=True)
        tray_thread.start()

        # Auto-connect
        if (
            self._config.get("auto_connect", True)
            and config.get_ws_url(self._config).strip()
            and config.get_auth_token(self._config).strip()
        ):
            self._schedule_connect()
        else:
            logger.info("URL e/ou token não configurados — abra as configurações pelo ícone na bandeja")

        # Main thread: tkinter (hidden root)
        self._tk_root = tk.Tk()
        self._tk_root.withdraw()
        if open_config_on_start or self._pending_open_config:
            self._pending_open_config = False
            self._tk_root.after(0, self._open_config)
        self._tk_root.mainloop()  # Blocks here — handles config window events

    # -- Async loop --

    def _run_async_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _schedule_connect(self) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(self._connect(), loop=self._loop)
        )

    async def _connect(self) -> None:
        if self._ws_client:
            await self._ws_client.stop()

        ws_url = config.get_ws_url(self._config).strip()
        auth_token = config.get_auth_token(self._config).strip()
        printer_name = self._config.get("printer_name", "")

        if not ws_url or not auth_token:
            missing = []
            if not ws_url:
                missing.append("URL")
            if not auth_token:
                missing.append("token")
            logger.warning("%s não configurado(s) — abra as configurações", " e ".join(missing))
            self._set_status("disconnected")
            return

        if not printer_name:
            logger.warning("Impressora não selecionada — abra as configurações")

        self._set_status("connecting")

        self._ws_client = PrinterWebSocketClient(
            ws_url=ws_url,
            auth_token=auth_token,
            printer_name=printer_name,
            on_connected=lambda: self._set_status("connected"),
            on_disconnected=lambda: self._set_status("disconnected"),
            on_error=lambda msg: logger.error("WebSocket erro: %s", msg),
            on_auth_failed=lambda msg: self._handle_auth_failed(msg),
        )

        await self._ws_client.start()

    def _handle_auth_failed(self, message: str) -> None:
        self._set_status("disconnected")
        logger.error("Autenticação falhou: %s — verifique o token nas configurações", message)

    def _set_status(self, status: str) -> None:
        self._status = status
        if self._tray:
            self._tray.set_status(status)
        if self._tk_root:
            self._tk_root.after(0, lambda s=status: self._sync_config_status(s))
        logger.info("Status: %s", status)

    def _sync_config_status(self, status: str) -> None:
        """Atualiza o status na janela de configuração se estiver aberta (chamado na thread tk)."""
        if ConfigWindow._instance is not None:
            ConfigWindow._instance.update_status(status)

    # -- Config window (scheduled on tkinter main thread) --

    def _request_open_config(self) -> None:
        """Chamado da thread do tray — agenda abertura na thread do tkinter."""
        if self._tk_root:
            self._tk_root.after(0, self._open_config)
            return
        self._pending_open_config = True

    def _open_config(self) -> None:
        """Executa na thread principal do tkinter."""
        ConfigWindow.show(
            tk_root=self._tk_root,
            current_config=self._config,
            on_save=self._on_config_saved,
            on_test_print=self._on_test_print_from_config,
            on_test_connection=self._reconnect,
            connection_status=self._status,
        )

    def _on_config_saved(self, new_config: dict) -> None:
        self._config = new_config
        logger.info("Configuração atualizada")
        self.sync_windows_startup()
        self._reconnect()

    def _on_test_print_from_config(self, printer_name: str) -> None:
        success, msg = printer_service.test_print(printer_name)
        logger.info("Teste de impressão: %s — %s", "OK" if success else "FALHA", msg)

    # -- Tray actions --

    def _reconnect(self) -> None:
        logger.info("Reconectando...")
        self._schedule_connect()

    def _test_print(self) -> None:
        printer_name = self._config.get("printer_name", "")
        if not printer_name:
            logger.warning("Nenhuma impressora configurada")
            return
        success, msg = printer_service.test_print(printer_name)
        logger.info("Teste de impressão: %s — %s", "OK" if success else "FALHA", msg)

    def _request_exit(self) -> None:
        """Chamado da thread do tray — agenda shutdown na thread do tkinter."""
        logger.info("Encerrando agente...")
        if self._ws_client and self._loop:
            future = asyncio.run_coroutine_threadsafe(self._ws_client.stop(), self._loop)
            try:
                future.result(timeout=5)
            except Exception:
                pass
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._activation_server:
            self._activation_server.stop()
        if self._tray:
            self._tray.stop()
        if self._tk_root:
            self._tk_root.after(0, self._tk_root.quit)


def _notify_running_instance_open_config() -> bool:
    try:
        with closing(socket.create_connection((ACTIVATION_HOST, ACTIVATION_PORT), timeout=0.4)) as conn:
            conn.sendall(ACTIVATION_TOKEN)
        return True
    except OSError:
        return False


def main():
    args = {arg.lower() for arg in sys.argv[1:]}
    background_mode = "--background" in args

    lock_path = os.path.join(config.get_config_dir(), "printer_agent.lock")
    instance_lock = SingleInstanceLock(lock_path)
    if not instance_lock.acquire():
        if not background_mode:
            _notify_running_instance_open_config()
        return

    agent = PrinterAgent()
    try:
        agent.sync_windows_startup()
        agent.run(open_config_on_start=not background_mode)
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário (Ctrl+C)")
        agent._request_exit()
    finally:
        instance_lock.release()


if __name__ == "__main__":
    main()
