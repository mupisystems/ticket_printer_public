"""
Janela do Agente de Impressão — interface web (HTML/CSS/JS em ``ui/``) exibida
numa janela nativa do Windows via pywebview (motor Microsoft Edge WebView2).

Comunicação:
  - JS → Python: métodos públicos da classe ``Api`` (``window.pywebview.api``).
    O pywebview executa cada chamada numa thread própria.
  - Python → JS: ``AppWindow.emit()`` enfileira eventos que uma thread dedicada
    entrega com ``window.agent.receive({type, data})`` — quem chama nunca
    fica bloqueado esperando a página.

Fechar a janela apenas a esconde: o agente continua ativo na bandeja.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import queue
import socket
import sys
import threading
import time
from collections import deque
from datetime import datetime
from typing import Callable, Optional

import webview

import config
import log_buffer
import printer_service

logger = logging.getLogger(__name__)

WINDOW_TITLE = "Agente de Impressão · Meu Atendimento Virtual"
BACKGROUND = "#f4f6fb"
PANEL_PRINTER_URL = "https://painel.meuatendimentovirtual.com.br/adm/config/geral/editar/printer/"
WEBVIEW2_CLIENT = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"
DEFAULT_SIZE = (1040, 700)
MIN_SIZE = (760, 560)

# Nomes que indicam impressora virtual (não imprime em papel).
_VIRTUAL_HINTS = ("pdf", "xps", "onenote", "fax", "microsoft print", "send to",
                  "enviar para", "anydesk", "snagit", "foxit")
# Nomes que indicam impressora térmica de cupom (só uma dica visual).
_THERMAL_HINTS = ("tm-", "tm ", "elgin", "bematech", "daruma", "sweda", "tanca",
                  "control id", "diebold", "pos-", "pos ", "pos58", "pos80", "80mm",
                  "58mm", "thermal", "térmica", "termica", "receipt", "mp-4200",
                  "mp4200", "tsp1", "tsp6")

_PRINTER_REASON_LABELS = {
    "impressora em pausa": "Pausada",
    "impressora offline": "Offline",
    "impressora em estado de erro": "Com erro",
    "impressora não disponível": "Indisponível",
    "impressora não encontrada": "Não encontrada",
}


def webview2_available() -> bool:
    """True se o Microsoft Edge WebView2 está instalado (necessário para a janela)."""
    if os.environ.get("PRINTER_AGENT_NO_WEBVIEW2") == "1":      # para testes
        return False
    import winreg
    for root, path in (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\EdgeUpdate\Clients"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\EdgeUpdate\Clients"),
    ):
        try:
            with winreg.OpenKey(root, rf"{path}\{WEBVIEW2_CLIENT}") as key:
                version, _ = winreg.QueryValueEx(key, "pv")
            if str(version).strip() not in ("", "0.0.0.0"):
                return True
        except OSError:
            continue
    return False


def _free_port() -> int:
    """Porta local livre para servir a interface. A padrão do pywebview é fixa (42001):
    ocupada por outro programa ou outra sessão, a janela abriria em branco ou errada."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _ui_index() -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "ui", "index.html")


def _logical_screen() -> tuple[int, int]:
    """Tamanho da tela em pixels lógicos (independente da escala do Windows)."""
    try:
        u = ctypes.windll.user32
        w, h = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
        if u.IsProcessDPIAware():
            scale = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100 or 1
            w, h = w / scale, h / scale
        return int(w), int(h)
    except Exception:
        return DEFAULT_SIZE[0] + 200, DEFAULT_SIZE[1] + 200


# ─── Estatísticas do dia (persistidas) ───────────────────────────────────────

class _DailyStats:
    """Contagem de tickets impressos/falhos no dia, salva em print_stats.json."""

    def __init__(self) -> None:
        self._path = os.path.join(config.get_config_dir(), "print_stats.json")
        self._lock = threading.Lock()
        self._data = {"date": "", "printed": 0, "failed": 0, "last_print_at": None}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._data.update(json.load(f))
        except (OSError, ValueError):
            pass

    def _roll(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        if self._data.get("date") != today:
            self._data = {"date": today, "printed": 0, "failed": 0,
                          "last_print_at": self._data.get("last_print_at")}

    def record(self, success: bool) -> dict:
        with self._lock:
            self._roll()
            if success:
                self._data["printed"] += 1
                self._data["last_print_at"] = time.time()
            else:
                self._data["failed"] += 1
            try:
                with open(self._path, "w", encoding="utf-8") as f:
                    json.dump(self._data, f)
            except OSError as e:
                logger.debug("Falha ao salvar estatísticas: %s", e)
            return dict(self._data)

    def snapshot(self) -> dict:
        with self._lock:
            self._roll()
            return dict(self._data)


# ─── API exposta ao JavaScript ───────────────────────────────────────────────

class Api:
    """Métodos chamados pela interface (``window.pywebview.api.<nome>``)."""

    def __init__(self, app: "AppWindow"):
        self._app = app

    def get_state(self) -> dict:
        return self._app.snapshot()

    def save_config(self, changes: dict) -> dict:
        return self._app.save(changes or {})

    def reconnect(self) -> dict:
        self._app.reconnect()
        return {"ok": True}

    def list_printers(self) -> list:
        items = []
        for name in printer_service.list_printers():
            low = name.lower()
            virtual = any(h in low for h in _VIRTUAL_HINTS)
            thermal = not virtual and any(h in low for h in _THERMAL_HINTS)
            items.append({"name": name, "virtual": virtual, "thermal": thermal})
        # Térmicas primeiro, depois as demais físicas, virtuais por último.
        items.sort(key=lambda p: (p["virtual"], not p["thermal"]))
        return items

    def printer_status(self, name: str) -> dict:
        ready, reason = printer_service.get_printer_status(name)
        label = "Pronta" if ready else _PRINTER_REASON_LABELS.get(reason, "Indisponível")
        return {"name": name, "ready": ready, "reason": reason, "label": label}

    def test_print(self, name: str, model: Optional[str] = None,
                   with_qr: Optional[bool] = None, paper: Optional[str] = None) -> dict:
        return self._app.test_print(name, model, with_qr, paper)

    def preview_ticket(self, model: str, with_qr: Optional[bool] = None,
                       paper: Optional[str] = None) -> dict:
        """Imagem do ticket de exemplo, gerada dos mesmos comandos da impressora."""
        if model not in config.RECEIPT_MODEL_LABELS:
            return {"ok": False}
        try:
            import ticket_preview
            return ticket_preview.preview_data_url(model, with_qr, paper)
        except Exception:
            logger.warning("Falha ao gerar prévia do modelo %s", model, exc_info=True)
            return {"ok": False}

    # ── Logo do comprovante (aplicado na hora, sem reconectar) ──

    def set_logo(self, data_url: str) -> dict:
        import ticket_logo
        cfg = self._app.config_snapshot()
        size = cfg.get("logo_size", ticket_logo.DEFAULT_SIZE)
        try:
            ticket_logo.set_logo(data_url, size)
        except ValueError as e:
            return {"ok": False, "message": str(e)}
        except Exception as e:
            logger.warning("Falha ao salvar o logo", exc_info=True)
            return {"ok": False, "message": f"Não foi possível usar esta imagem: {e}"}
        cfg = self._app.update_quiet(logo_enabled=True, logo_size=size)
        return {"ok": True, "logo": ticket_logo.info(cfg)}

    def set_logo_size(self, size: str) -> dict:
        import ticket_logo
        try:
            ticket_logo.set_size(size)
        except ValueError as e:
            return {"ok": False, "message": str(e)}
        cfg = self._app.update_quiet(logo_size=size)
        return {"ok": True, "logo": ticket_logo.info(cfg)}

    def remove_logo(self) -> dict:
        import ticket_logo
        ticket_logo.remove_logo()
        cfg = self._app.update_quiet(logo_enabled=False)
        return {"ok": True, "logo": ticket_logo.info(cfg)}

    def get_logs(self, since: int = 0) -> dict:
        total, lines = log_buffer.buffer.get_since(int(since or 0))
        return {"total": total, "lines": lines}

    def clear_logs(self) -> dict:
        log_buffer.buffer.clear()
        logger.info("Registros limpos pelo usuário")
        return {"total": log_buffer.buffer.total()}

    def copy_text(self, text: str) -> dict:
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text or "", win32clipboard.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def read_clipboard(self) -> str:
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                    return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT) or ""
            finally:
                win32clipboard.CloseClipboard()
        except Exception as e:
            logger.debug("Leitura da área de transferência: %s", e)
        return ""

    def open_panel(self) -> dict:
        """Abre no navegador a tela do painel onde fica a chave de impressão."""
        import webbrowser
        return {"ok": webbrowser.open(PANEL_PRINTER_URL)}

    def open_logs_folder(self) -> dict:
        try:
            os.startfile(config.get_config_dir())
            return {"ok": True}
        except OSError as e:
            return {"ok": False, "message": str(e)}

    def hide_window(self) -> dict:
        self._app.hide()
        return {"ok": True}


# ─── Janela ──────────────────────────────────────────────────────────────────

class AppWindow:
    """Gerencia a janela pywebview e o estado exibido na interface."""

    def __init__(
        self,
        *,
        get_config: Callable[[], dict],
        get_status: Callable[[], str],
        on_save: Callable[[dict], None],
        on_reconnect: Callable[[], None],
        on_test_print: Callable[..., tuple],
        on_first_hide: Optional[Callable[[], None]] = None,
        on_config_quiet: Optional[Callable[[dict], None]] = None,
        start_hidden: bool = False,
    ):
        self._get_config = get_config
        self._on_config_quiet = on_config_quiet
        self._get_status = get_status
        self._on_save = on_save
        self._on_reconnect = on_reconnect
        self._on_test_print = on_test_print
        self._on_first_hide = on_first_hide
        self._hidden_once = False
        self._start_hidden = start_hidden
        self._quitting = False
        self._last_status: Optional[str] = None
        self._loaded = threading.Event()
        self._js_queue: "queue.Queue[str]" = queue.Queue(maxsize=500)
        self._activity: deque = deque(maxlen=60)
        self.stats = _DailyStats()
        self._window = None
        self._exit = threading.Event()

        # Sem o WebView2 a janela não abre direito, mas o totem não pode parar:
        # o agente segue conectado e imprimindo pela bandeja.
        if not webview2_available():
            logger.error("Microsoft Edge WebView2 não encontrado: o agente segue imprimindo, "
                         "mas a janela só abre depois de instalá-lo (%s)", WEBVIEW2_URL)
            return

        sw, sh = _logical_screen()
        width = min(DEFAULT_SIZE[0], max(MIN_SIZE[0], sw - 60))
        height = min(DEFAULT_SIZE[1], max(MIN_SIZE[1], sh - 90))

        self._window = webview.create_window(
            WINDOW_TITLE,
            url=_ui_index(),
            js_api=Api(self),
            width=width,
            height=height,
            min_size=MIN_SIZE,
            hidden=start_hidden,
            background_color=BACKGROUND,
        )
        self._window.events.closing += self._on_closing
        self._window.events.loaded += self._on_loaded
        threading.Thread(target=self._js_pump, name="ui-events", daemon=True).start()

    # ── Ciclo de vida ────────────────────────────────────────────────────────

    def run(self) -> None:
        """Inicia o loop da interface. Bloqueia a thread principal até quit()."""
        if self._window is None:
            if not self._start_hidden:
                self._warn_no_webview2()
            while not self._exit.wait(1):      # espera curta: mantém o Ctrl+C funcionando
                pass
            return
        debug = os.environ.get("PRINTER_AGENT_DEBUG") == "1"
        webview.start(
            gui="edgechromium",
            debug=debug,
            http_server=True,
            http_port=_free_port(),
            private_mode=False,
            storage_path=os.path.join(config.get_config_dir(), "webview"),
        )

    def _warn_no_webview2(self) -> None:
        """Avisa (sem travar o agente) que falta o WebView2 e oferece a página oficial."""
        def ask():
            text = ("O Agente de Impressão está ativo e continua imprimindo, mas a janela precisa do "
                    "Microsoft Edge WebView2, que não foi encontrado neste computador.\n\n"
                    "Abrir a página oficial da Microsoft para instalar? Depois, reinicie o agente.")
            if ctypes.windll.user32.MessageBoxW(None, text, WINDOW_TITLE, 0x4 | 0x30 | 0x40000) == 6:
                os.startfile(WEBVIEW2_URL)
        threading.Thread(target=ask, daemon=True).start()

    def show(self) -> None:
        if self._window is None:
            self._warn_no_webview2()
            return
        try:
            self._window.show()
        except Exception:
            logger.debug("Falha ao exibir a janela", exc_info=True)
        self.emit("shown", {})

    def hide(self) -> None:
        try:
            self._window.hide()
        except Exception:
            logger.debug("Falha ao ocultar a janela", exc_info=True)
        if not self._hidden_once:
            self._hidden_once = True
            if self._on_first_hide:
                try:
                    self._on_first_hide()
                except Exception:
                    logger.debug("Callback de ocultação falhou", exc_info=True)

    def quit(self) -> None:
        self._quitting = True
        self._exit.set()
        if self._window is None:
            return
        try:
            self._js_queue.put_nowait("")      # acorda a thread de eventos para encerrar
        except queue.Full:
            pass
        try:
            self._window.destroy()
        except Exception:
            logger.debug("Falha ao fechar a janela", exc_info=True)

    def _on_closing(self):
        if self._quitting:
            return True
        # Fechar só esconde a janela: o agente segue funcionando na bandeja.
        threading.Thread(target=self.hide, daemon=True).start()
        return False

    def _on_loaded(self) -> None:
        first = not self._loaded.is_set()
        self._loaded.set()
        if first and not self._start_hidden:
            # Se o processo foi iniciado com "janela oculta/minimizada" (atalho
            # configurado assim, alguns lançadores), o Windows aplica isso ao
            # primeiro ShowWindow e a janela nunca aparece. Reexibir garante.
            threading.Thread(target=self._window.show, daemon=True).start()

    # ── Eventos Python → JS ──────────────────────────────────────────────────

    def emit(self, kind: str, data) -> None:
        if self._window is None:
            return
        payload = json.dumps({"type": kind, "data": data}, ensure_ascii=False)
        try:
            self._js_queue.put_nowait(f"window.agent && window.agent.receive({payload})")
        except queue.Full:
            logger.debug("Fila de eventos da interface cheia; evento %s descartado", kind)

    def _js_pump(self) -> None:
        while True:
            script = self._js_queue.get()
            if self._quitting:
                return
            self._loaded.wait()
            try:
                self._window.evaluate_js(script)
            except Exception:
                logger.debug("Falha ao entregar evento à interface", exc_info=True)

    # ── Estado ───────────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        cfg = self._get_config()
        token = config.get_auth_token(cfg)
        printer = cfg.get("printer_name", "")
        return {
            "version": config.APP_VERSION,
            "status": self._get_status(),
            "configured": bool(token and printer),
            "onboarding_required": config.onboarding_required(cfg),
            "frozen": bool(getattr(sys, "frozen", False)),
            "config": {
                "environment": cfg.get("environment", "producao_br"),
                "server_url": cfg.get("server_url", ""),
                "token": token,
                "printer_name": printer,
                "receipt_model": cfg.get("receipt_model", "default"),
                "paper_width": str(cfg.get("paper_width") or "80"),
                "auto_connect": bool(cfg.get("auto_connect", True)),
                "start_with_windows": bool(cfg.get("start_with_windows", True)),
            },
            "environments": [
                {"key": k, "label": config.ENVIRONMENT_LABELS.get(k, k), "url": url or ""}
                for k, url in config.ENVIRONMENTS.items()
            ],
            "receipt_models": [
                {"key": k, "label": v} for k, v in config.RECEIPT_MODEL_LABELS.items()
            ],
            "stats": self.stats.snapshot(),
            "activity": list(self._activity),
            "logo": self._logo_info(cfg),
            "ticket_sample": self._sample_info(),
        }

    @staticmethod
    def _sample_info() -> dict:
        try:
            import ticket_preview
            return ticket_preview.sample_info()
        except Exception:
            return {"source": None, "has_qr": False}

    def ticket_sample(self, data: dict, source: str) -> None:
        """Formato real do ticket da conta chegou (ticket recebido ou servidor)."""
        try:
            import ticket_preview
            sample, changed = ticket_preview.save_sample(data, source)
        except Exception:
            logger.debug("Falha ao guardar a amostra do ticket", exc_info=True)
            return
        if changed:
            logger.info("Formato do ticket da conta atualizado (%s; QR Code: %s)",
                        source, "sim" if sample.get("has_qr") else "não")
            self.emit("sample", self._sample_info())

    @staticmethod
    def _logo_info(cfg: dict) -> dict:
        try:
            import ticket_logo
            return ticket_logo.info(cfg)
        except Exception:
            logger.debug("Logo indisponível", exc_info=True)
            return {"enabled": False, "size": "medium"}

    def save(self, changes: dict) -> dict:
        cfg = dict(self._get_config())
        for key in ("environment", "server_url", "printer_name", "receipt_model", "paper_width"):
            if key in changes and changes[key] is not None:
                cfg[key] = str(changes[key]).strip()
        for key in ("auto_connect", "start_with_windows"):
            if key in changes:
                cfg[key] = bool(changes[key])
        if "token" in changes:
            config.set_auth_token(cfg, str(changes.get("token") or "").strip())

        env = cfg.get("environment")
        if env not in config.ENVIRONMENTS:
            env = cfg["environment"] = "producao_br"
        if env != "custom":
            cfg["server_url"] = config.ENVIRONMENTS[env]
        if cfg.get("receipt_model") not in config.RECEIPT_MODEL_LABELS:
            cfg["receipt_model"] = "default"
        if cfg.get("paper_width") not in ("58", "80"):
            cfg["paper_width"] = "80"
        if changes.get("onboarding_done"):
            cfg["onboarded_install_id"] = config.get_install_id()   # boas-vindas concluídas

        config.save_config(cfg)
        logger.info(
            "Configurações salvas pelo usuário (ambiente: %s, impressora: %s). Aplicando e reconectando...",
            config.ENVIRONMENT_LABELS.get(env, env), cfg.get("printer_name") or "nenhuma",
        )
        self._on_save(cfg)
        return self.snapshot()

    def config_snapshot(self) -> dict:
        return dict(self._get_config())

    def update_quiet(self, **changes) -> dict:
        """Salva ajustes que não exigem reconectar (ex.: logo do comprovante)."""
        cfg = dict(self._get_config())
        cfg.update(changes)
        config.save_config(cfg)
        if self._on_config_quiet:
            self._on_config_quiet(cfg)
        return cfg

    def reconnect(self) -> None:
        self._on_reconnect()

    def test_print(self, name: str, model: Optional[str] = None,
                   with_qr: Optional[bool] = None, paper: Optional[str] = None) -> dict:
        name = (name or "").strip()
        if not name:
            return {"ok": False, "message": "Selecione uma impressora."}
        if model not in config.RECEIPT_MODEL_LABELS:
            model = None                      # usa o modelo salvo na configuração
        try:
            ok, msg = self._on_test_print(name, model, with_qr,
                                          paper if paper in ("58", "80") else None)
        except Exception as e:
            ok, msg = False, f"Erro: {e}"
        label = config.RECEIPT_MODEL_LABELS.get(model or self._get_config().get("receipt_model"), "")
        self.add_activity("success" if ok else "error",
                          "Impressão de teste" + (" enviada" if ok else " falhou"),
                          (f"{name} · modelo {label}" if label else name) if ok else msg)
        return {"ok": bool(ok), "message": msg}

    # ── Notificações vindas do agente ────────────────────────────────────────

    def add_activity(self, tone: str, title: str, detail: str = "") -> None:
        item = {"ts": time.time(), "tone": tone, "title": title, "detail": detail}
        self._activity.appendleft(item)
        self.emit("activity", item)

    def push_status(self, status: str) -> None:
        previous, self._last_status = self._last_status, status
        self.emit("status", {"status": status})
        if status == previous:
            return
        if status == "connected":
            self.add_activity("success", "Conectado ao servidor")
        elif status == "auth_failed":
            self.add_activity("error", "Chave recusada pelo servidor",
                              "Confira a chave de impressão nas configurações.")
        elif status == "server_error":
            self.add_activity("error", "Erro no servidor ao validar a chave",
                              "Falha interna do servidor. Avise o suporte do Meu Atendimento Virtual.")
        elif status == "reconnecting" and previous == "connected":
            self.add_activity("warning", "Conexão perdida", "Tentando reconectar automaticamente.")

    def record_print(self, job_id: str, success: bool, message: str) -> None:
        stats = self.stats.record(success)
        code = job_id if job_id and job_id != "unknown" else ""
        if success:
            self.add_activity("success", "Ticket impresso", f"Job {code}" if code else "")
        else:
            self.add_activity("error", "Falha na impressão", message)
        self.emit("stats", stats)
