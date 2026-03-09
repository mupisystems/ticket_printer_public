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

if os.name == "nt":
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("meuatendimento.printer_agent")
    except Exception:
        pass

# PyInstaller onefile: apontar escpos para capabilities.json no bundle (antes de importar printer_service)
if getattr(sys, "frozen", False):
    bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    os.environ.setdefault(
        "ESCPOS_CAPABILITIES_FILE",
        os.path.join(bundle_dir, "escpos", "capabilities.json"),
    )

import config
import printer_service
from websocket_client import PrinterWebSocketClient
from tray import TrayIcon
from config_window import ConfigWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("printer_agent")


class PrinterAgent:
    def __init__(self):
        self._config = config.load_config()
        self._ws_client: PrinterWebSocketClient | None = None
        self._tray: TrayIcon | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tk_root: tk.Tk | None = None
        self._status = "disconnected"

    def run(self) -> None:
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
        # Ao iniciar o app, abre a janela de configuração por padrão.
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
        if self._tray:
            self._tray.stop()
        if self._tk_root:
            self._tk_root.after(0, self._tk_root.quit)


def main():
    agent = PrinterAgent()
    try:
        agent.run()
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário (Ctrl+C)")
        agent._request_exit()


if __name__ == "__main__":
    main()
