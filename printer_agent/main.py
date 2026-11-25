"""
Entry point do agente de impressão v2.
Coordena system tray, WebSocket client e janela de configuração.

Threading model:
  - Main thread: pywebview (janela da interface — HTML/CSS/JS em ui/)
  - Background thread 1: pystray (system tray icon)
  - Background thread 2: asyncio event loop (WebSocket client)
"""

import os
import sys
import asyncio
import logging
import threading
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
import log_buffer
from logging.handlers import RotatingFileHandler
from websocket_client import PrinterWebSocketClient
from tray import TrayIcon
from app_window import AppWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    # Sem console (versão instalada) sys.stdout é None
    handlers=[logging.StreamHandler(sys.stdout)] if sys.stdout else [logging.NullHandler()],
    # A python-escpos já configura o log ao ser importada (nível WARNING); sem
    # force, esta configuração era ignorada e os registros INFO se perdiam.
    force=True,
)
log_buffer.install()

# Log persistido em arquivo rotativo (2 MB × 3 arquivos)
_log_file = os.path.join(config.get_config_dir(), "printer_agent.log")
_file_handler = RotatingFileHandler(
    _log_file, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
))
logging.getLogger().addHandler(_file_handler)

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
        self._ui: AppWindow | None = None
        self._status = "disconnected"
        self._activation_server: ActivationServer | None = None
        self._pending_open_config = False
        # Identifica a conexão ativa. Cada _connect() incrementa a geração;
        # callbacks de clientes antigos (que ainda estão encerrando) são
        # ignorados, evitando que um "disconnected" atrasado sobrescreva o
        # "connected" do cliente atual.
        self._connect_generation = 0
        # Último status já registrado no log — evita repetir a mesma linha a
        # cada tentativa, mas garante que toda transição real apareça.
        self._last_logged_status: str | None = None

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

        # Interface (criada antes das threads para receber status desde o início).
        # Em modo --background a janela começa oculta; o ícone da bandeja a abre.
        self._ui = AppWindow(
            get_config=lambda: self._config,
            get_status=lambda: self._status,
            on_save=self._on_config_saved,
            on_reconnect=self._reconnect,
            on_test_print=self._on_test_print_from_config,
            on_first_hide=self._notify_still_running,
            on_config_quiet=self._set_config_quiet,
            start_hidden=not (open_config_on_start or self._pending_open_config),
        )
        self._pending_open_config = False

        self._activation_server = ActivationServer(self._request_open_config)
        self._activation_server.start()

        # Thread 2: asyncio event loop. O loop é criado aqui, antes da thread: o
        # pedido de conexão automática logo abaixo se perdia (em silêncio) quando
        # a thread ainda não o tinha criado, e o totem ficava desconectado.
        self._loop = asyncio.new_event_loop()
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

        # Estado inicial explícito no log (o primeiro evento é sempre este).
        self._set_status("disconnected")

        # Auto-connect
        if (
            self._config.get("auto_connect", True)
            and config.get_ws_url(self._config).strip()
            and config.get_auth_token(self._config).strip()
        ):
            self._schedule_connect()
        else:
            logger.info("URL e/ou chave não configuradas — abra as configurações pelo ícone na bandeja")

        # Main thread: interface (bloqueia aqui até o agente ser encerrado)
        self._ui.run()

    # -- Async loop --

    def _run_async_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _schedule_connect(self) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(self._connect(), loop=self._loop)
        )

    async def _connect(self) -> None:
        # Nova geração de conexão: invalida callbacks do cliente anterior.
        self._connect_generation += 1
        gen = self._connect_generation

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
            on_connected=lambda g=gen: self._on_ws_connected(g),
            on_disconnected=lambda g=gen: self._on_ws_disconnected(g),
            on_reconnecting=lambda g=gen: self._on_ws_reconnecting(g),
            on_error=lambda msg: logger.error("WebSocket erro: %s", msg),
            on_auth_failed=lambda msg, g=gen: self._handle_auth_failed(msg, g),
            on_print_result=lambda job, ok, m, g=gen: self._on_print_result(job, ok, m, g),
            on_ticket_sample=self._on_ticket_sample,
            on_server_error=lambda msg, g=gen: self._handle_server_error(msg, g),
        )

        # Inicia monitor periódico de impressora junto com a conexão
        asyncio.ensure_future(self._printer_monitor_loop())

        await self._ws_client.start()

    def _on_ws_connected(self, gen: int) -> None:
        if gen != self._connect_generation:
            return
        self._set_status("connected")

    def _on_ws_disconnected(self, gen: int) -> None:
        # Ignora "disconnected" de um cliente antigo já substituído.
        if gen != self._connect_generation:
            return
        # Token recusado / erro do servidor são mais específicos que
        # "desconectado": mantém para a interface orientar o usuário.
        if self._status in ("auth_failed", "server_error"):
            return
        self._set_status("disconnected")

    def _on_ws_reconnecting(self, gen: int) -> None:
        if gen != self._connect_generation:
            return
        self._set_status("reconnecting")

    def _on_print_result(self, job_id: str, success: bool, message: str,
                         gen: int | None = None) -> None:
        """Chamado pela thread do WebSocket após cada impressão real."""
        if gen is not None and gen != self._connect_generation:
            return
        # Recebemos tráfego do servidor → a conexão está de fato ativa.
        # Garante que o status reflita "conectado" mesmo que um evento de
        # desconexão obsoleto o tenha deixado incorreto (falha de impressão
        # é problema da impressora, não da conexão com o servidor).
        if self._status != "connected":
            self._set_status("connected")
        if self._ui:
            self._ui.record_print(job_id, success, message)
        printer_name = self._config.get("printer_name", "")
        if self._tray:
            self._tray.set_printer_status(success, printer_name)
            if not success:
                code = job_id if job_id != "unknown" else ""
                title = "Falha na Impressão"
                body = f"Ticket {code}: {message}" if code else message
                logger.warning("Notificando falha de impressão (job %s): %s", job_id, message)
                self._tray.notify(title, body)

    async def _printer_monitor_loop(self) -> None:
        """Verifica o status da impressora a cada 30s e atualiza o ícone da bandeja."""
        client = self._ws_client  # captura o cliente atual; para quando ele trocar
        while self._ws_client is client and client is not None:
            await asyncio.sleep(30)
            if self._ws_client is not client:
                break
            printer_name = self._config.get("printer_name", "")
            if printer_name and self._tray:
                ready, _ = printer_service._check_printer_status(printer_name)
                self._tray.set_printer_status(ready, printer_name)

    def _handle_auth_failed(self, message: str, gen: int | None = None) -> None:
        if gen is not None and gen != self._connect_generation:
            return
        self._set_status("auth_failed")
        logger.error("Autenticação falhou: %s — verifique a chave nas configurações", message)

    def _handle_server_error(self, message: str, gen: int | None = None) -> None:
        if gen is not None and gen != self._connect_generation:
            return
        self._set_status("server_error")
        logger.error("O servidor falhou ao validar a chave (erro interno): %s", message)

    # Mensagens amigáveis (nível de log, texto) para cada estado da conexão.
    _STATUS_LOG = {
        "connecting":   (logging.INFO,    "Conectando ao servidor..."),
        "connected":    (logging.INFO,    "Aplicativo conectado ao servidor. Pronto para imprimir."),
        "reconnecting": (logging.WARNING, "Conexão perdida — reconectando ao servidor..."),
        "disconnected": (logging.WARNING, "Aplicativo desconectado do servidor."),
        "auth_failed":  (logging.ERROR,   "Aplicativo desconectado: o servidor recusou a chave."),
        "server_error": (logging.ERROR,   "Aplicativo desconectado: erro interno do servidor ao validar a chave."),
    }

    def _set_status(self, status: str) -> None:
        self._status = status
        if self._tray:
            try:
                self._tray.set_status(status)
            except Exception:
                logger.debug("Falha ao atualizar status na bandeja", exc_info=True)
        if self._ui:
            # Só enfileira o evento (não bloqueia) — isso NUNCA pode
            # derrubar a thread da conexão.
            try:
                self._ui.push_status(status)
            except Exception:
                logger.debug("Falha ao atualizar status na interface", exc_info=True)
        # Registra a transição no log (uma vez por mudança de estado).
        if status != self._last_logged_status:
            self._last_logged_status = status
            level, msg = self._STATUS_LOG.get(status, (logging.INFO, f"Status: {status}"))
            logger.log(level, msg)

    # -- Janela da interface --

    def _request_open_config(self) -> None:
        """Chamado da thread do tray / servidor de ativação — mostra a janela."""
        if self._ui:
            self._ui.show()
            return
        self._pending_open_config = True

    def _notify_still_running(self) -> None:
        """Na primeira vez que a janela é fechada, avisa que o agente segue ativo."""
        if self._tray:
            self._tray.notify(
                "O agente continua ativo",
                "As senhas seguem sendo impressas. Abra pelo ícone perto do relógio.",
            )

    def _on_ticket_sample(self, data: dict, source: str) -> None:
        """Formato real do ticket da conta (para as prévias do comprovante)."""
        if self._ui:
            self._ui.ticket_sample(data, source)

    def _set_config_quiet(self, new_config: dict) -> None:
        """Ajuste que não muda a conexão (ex.: logo do comprovante): só atualiza."""
        self._config = new_config

    def _on_config_saved(self, new_config: dict) -> None:
        self._config = new_config
        logger.info("Configuração atualizada")
        self.sync_windows_startup()
        self._reconnect()

    def _on_test_print_from_config(self, printer_name: str, receipt_model: str | None = None,
                                   with_qr: bool | None = None,
                                   paper: str | None = None) -> tuple[bool, str]:
        success, msg = printer_service.test_print(printer_name, receipt_model, with_qr, paper)
        logger.info("Teste de impressão: %s — %s", "OK" if success else "FALHA", msg)
        return success, msg

    # -- Tray actions --

    def _reconnect(self) -> None:
        logger.info("Reconectando...")
        self._schedule_connect()

    def _test_print(self) -> None:
        printer_name = self._config.get("printer_name", "")
        if not printer_name:
            if self._tray:
                self._tray.notify("Impressão de Teste", "Nenhuma impressora configurada.")
            logger.warning("Nenhuma impressora configurada")
            return
        success, msg = printer_service.test_print(printer_name)
        logger.info("Teste de impressão: %s — %s", "OK" if success else "FALHA", msg)
        if self._ui:
            self._ui.add_activity("success" if success else "error",
                                  "Impressão de teste" + (" enviada" if success else " falhou"),
                                  printer_name if success else msg)
        if self._tray:
            title = "Impressão de Teste"
            self._tray.notify(title, msg)

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
        if self._ui:
            self._ui.quit()


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
