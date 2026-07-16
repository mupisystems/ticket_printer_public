"""
Janela de configuração moderna - Meu Atendimento Virtual / Agente de Impressão
"""

import logging
import os
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

import config
import printer_service

logger = logging.getLogger(__name__)

# ─── Paleta ──────────────────────────────────────────────────────────────────
C_PRIMARY       = "#334398"
C_PRIMARY_DARK  = "#243080"
C_PRIMARY_LIGHT = "#eaedfa"
C_BG            = "#f0f2f8"
C_CARD          = "#ffffff"
C_SHADOW        = "#c8d2e8"
C_BORDER        = "#dde3f0"
C_INPUT_BG      = "#f5f7fc"
C_TEXT          = "#1e2a4a"
C_MUTED         = "#6b7a99"
C_SUCCESS       = "#16a34a"
C_ERROR         = "#dc2626"
C_WARNING       = "#d97706"

# ─── Tipografia ───────────────────────────────────────────────────────────────
F_HERO    = ("Clash Grotesk", 15, "bold")
F_SUB     = ("Inter", 8)
F_SECTION = ("Clash Grotesk", 9, "bold")
F_LABEL   = ("Inter", 9)
F_INPUT   = ("Inter", 10)
F_STATUS  = ("Inter", 10, "bold")
F_BTN_LG  = ("Inter", 10, "bold")
F_BTN_SM  = ("Inter", 9, "bold")

LOGO_FILE              = "logo.png"
WINDOW_ICON_CANDIDATES = ("tray_icon.png", "logo.png")

# Largura máxima do conteúdo; em telas largas o conteúdo é centralizado
# em vez de esticar, mantendo os cards legíveis em totens grandes.
MAX_CONTENT_W = 620
# Largura padrão da janela em telas normais.
DEFAULT_W = 490


# ─── Utilidades ───────────────────────────────────────────────────────────────

def _base_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _safe_bg(widget) -> str:
    try:
        return widget.cget("bg")
    except Exception:
        return C_BG


def _rr(c: tk.Canvas, x1: int, y1: int, x2: int, y2: int, r: int = 6, **kw):
    """Retângulo com cantos arredondados via polígono suave."""
    pts = [
        x1 + r, y1, x2 - r, y1,
        x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r,
        x1, y1 + r, x1, y1,
    ]
    return c.create_polygon(pts, smooth=True, **kw)


def _card_frames(parent: tk.Widget):
    """Retorna (outer_to_pack, inner_for_children) simulando card com sombra."""
    outer = tk.Frame(parent, bg=C_SHADOW)
    inner = tk.Frame(outer, bg=C_CARD)
    inner.pack(fill=tk.BOTH, expand=True, padx=(0, 2), pady=(0, 2))
    return outer, inner


# ─── Widgets customizados ─────────────────────────────────────────────────────

class _Btn(tk.Canvas):
    """Botão primário com fundo sólido e efeito hover."""

    def __init__(self, parent, text: str, cmd=None,
                 bg: str = C_PRIMARY, hv: str = C_PRIMARY_DARK, fg: str = "#ffffff",
                 w: int = 110, h: int = 34, r: int = 6, font=F_BTN_LG, **kw):
        super().__init__(parent, width=w, height=h, bg=_safe_bg(parent),
                         highlightthickness=0, cursor="hand2", **kw)
        self._text, self._cmd = text, cmd
        self._bg, self._hv, self._fg = bg, hv, fg
        # Nota: self._w é reservado pelo tkinter — usar _bw/_bh para largura/altura
        self._bw, self._bh, self._br, self._bfont = w, h, r, font
        self._draw(bg)
        self.bind("<Enter>",           lambda e: self._draw(hv))
        self.bind("<Leave>",           lambda e: self._draw(bg))
        self.bind("<ButtonRelease-1>", self._click)

    def _draw(self, color: str):
        self.delete("all")
        _rr(self, 1, 1, self._bw - 1, self._bh - 1, self._br, fill=color, outline=color)
        self.create_text(self._bw // 2, self._bh // 2,
                         text=self._text, fill=self._fg, font=self._bfont)

    def _click(self, _):
        self._draw(self._bg)
        if self._cmd:
            self._cmd()


class _OBtn(tk.Canvas):
    """Botão outline (ghost) — fundo branco com borda colorida."""

    def __init__(self, parent, text: str, cmd=None,
                 color: str = C_PRIMARY, w: int = 110, h: int = 32, r: int = 6, **kw):
        super().__init__(parent, width=w, height=h, bg=_safe_bg(parent),
                         highlightthickness=0, cursor="hand2", **kw)
        self._text, self._cmd, self._color = text, cmd, color
        self._bw, self._bh, self._br = w, h, r
        self._enabled = True
        self._draw(False)
        self.bind("<Enter>",           lambda e: self._enabled and self._draw(True))
        self.bind("<Leave>",           lambda e: self._enabled and self._draw(False))
        self.bind("<ButtonRelease-1>", self._click)

    def _draw(self, hover: bool):
        self.delete("all")
        if not self._enabled:
            disabled_color = "#94a3b8"
            _rr(self, 1, 1, self._bw - 1, self._bh - 1, self._br,
                fill="#f1f5f9", outline=disabled_color)
            self.create_text(self._bw // 2, self._bh // 2,
                             text=self._text, fill=disabled_color, font=F_BTN_SM)
            return
        _rr(self, 1, 1, self._bw - 1, self._bh - 1, self._br,
            fill=self._color if hover else "#ffffff",
            outline=self._color)
        self.create_text(self._bw // 2, self._bh // 2,
                         text=self._text,
                         fill="#ffffff" if hover else self._color,
                         font=F_BTN_SM)

    def _click(self, _):
        if not self._enabled:
            return
        self._draw(False)
        if self._cmd:
            self._cmd()

    def set_text(self, text: str) -> None:
        self._text = text
        self._draw(False)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        try:
            self.configure(cursor="hand2" if self._enabled else "arrow")
        except tk.TclError:
            pass
        self._draw(False)


# ─── Ícones (estilo Lucide, desenhados no Canvas — sem dependência de SVG) ─────

class _Icon(tk.Canvas):
    """Ícone vetorial minimalista no estilo Lucide (traço fino, cantos suaves).

    Desenhado direto no Canvas para não depender de renderização de SVG no
    executável empacotado. Ícones disponíveis: printer, key, receipt, server,
    sliders, plug.
    """

    def __init__(self, parent, name: str, size: int = 16,
                 color: str = C_PRIMARY, bg: Optional[str] = None, **kw):
        super().__init__(parent, width=size, height=size,
                         bg=bg or _safe_bg(parent), highlightthickness=0, bd=0, **kw)
        self._draw(name, size, color)

    def _draw(self, name: str, size: int, color: str) -> None:
        s = size / 24.0                       # escala a partir do viewBox 24×24
        w = max(2, round(size / 10))          # espessura do traço

        def line(x1, y1, x2, y2):
            self.create_line(x1 * s, y1 * s, x2 * s, y2 * s, fill=color,
                             width=w, capstyle=tk.ROUND, joinstyle=tk.ROUND)

        def rect(x1, y1, x2, y2, fill=""):
            self.create_rectangle(x1 * s, y1 * s, x2 * s, y2 * s,
                                  outline=color, width=w, fill=fill)

        def circle(cx, cy, r, fill=""):
            self.create_oval((cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s,
                             outline=color, width=w, fill=fill)

        def dot(cx, cy, r):
            self.create_oval((cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s,
                             outline=color, fill=color)

        bg = self.cget("bg")

        if name == "printer":
            line(6, 8, 6, 3); line(18, 8, 18, 3); line(6, 3, 18, 3)   # folha superior
            rect(3, 8, 21, 17)                                         # corpo
            rect(6, 14, 18, 21, fill=bg)                               # bandeja de saída
            dot(16.5, 11, 0.8)                                         # LED
        elif name == "key":
            circle(7.5, 15.5, 3.2)
            line(9.8, 13.2, 21, 2)
            line(15.5, 5.5, 18, 8)
            line(18.5, 2.5, 21, 5)
        elif name == "receipt":
            rect(6, 2, 18, 22)
            line(9, 7, 15, 7); line(9, 11, 15, 11); line(9, 15, 13, 15)
        elif name == "server":
            rect(3, 4, 21, 10); dot(6.5, 7, 0.9); line(15, 7, 18, 7)
            rect(3, 14, 21, 20); dot(6.5, 17, 0.9); line(15, 17, 18, 17)
        elif name == "sliders":
            line(4, 8, 20, 8);  circle(9, 8, 2, fill=bg)
            line(4, 16, 20, 16); circle(15, 16, 2, fill=bg)
        elif name == "plug":
            line(12, 2, 12, 6)
            rect(7, 6, 17, 13)
            line(10, 6, 10, 3); line(14, 6, 14, 3)
            line(12, 13, 12, 20); circle(12, 21, 1.2)


# ─── Janela principal ─────────────────────────────────────────────────────────

class ConfigWindow:
    """Janela de configuração. Singleton gerenciado externamente."""

    _instance: Optional["ConfigWindow"] = None

    @classmethod
    def show(
        cls,
        tk_root: tk.Tk,
        current_config: dict,
        on_save: Optional[Callable[[dict], None]] = None,
        on_test_print: Optional[Callable[[str], None]] = None,
        on_test_connection: Optional[Callable] = None,
        connection_status: str = "disconnected",
        on_reconnect: Optional[Callable] = None,
    ) -> None:
        if cls._instance is not None:
            try:
                cls._instance._window.lift()
                cls._instance._window.focus_force()
                return
            except tk.TclError:
                cls._instance = None
        cls._instance = cls(
            tk_root, current_config, on_save,
            on_test_print, on_test_connection, connection_status,
            on_reconnect,
        )

    def __init__(
        self,
        tk_root: tk.Tk,
        current_config: dict,
        on_save: Optional[Callable[[dict], None]] = None,
        on_test_print: Optional[Callable[[str], None]] = None,
        on_test_connection: Optional[Callable] = None,
        connection_status: str = "disconnected",
        on_reconnect: Optional[Callable] = None,
    ):
        self._on_save = on_save
        self._on_test_print = on_test_print
        self._on_test_connection = on_test_connection
        self._on_reconnect = on_reconnect
        self._config = current_config
        self._logo_photo = None
        self._icon_photo = None

        self._adv_open = False

        self._window = tk.Toplevel(tk_root)
        self._window.title("Configurações · Agente de Impressão")
        self._window.resizable(True, True)
        self._window.configure(bg=C_BG)
        self._window.protocol("WM_DELETE_WINDOW", self._close)

        self._apply_icon()
        self._build(connection_status)
        self._load()

        # Rolagem + geometria adaptadas à tela (funciona em totens pequenos)
        self._window.update_idletasks()
        self._bind_mousewheel()

        sw = self._window.winfo_screenwidth()
        sh = self._window.winfo_screenheight()
        # Tamanho mínimo que ainda cabe em telas pequenas, sem colapsar a UI.
        self._window.minsize(min(380, sw - 20), min(320, sh - 40))
        self._fit_geometry(center=True)
        self._window.focus_force()

    # ── Ícone da janela ───────────────────────────────────────────────────────

    def _apply_icon(self) -> None:
        base = _base_dir()
        for name in WINDOW_ICON_CANDIDATES:
            path = os.path.join(base, name)
            if os.path.isfile(path):
                try:
                    from PIL import Image, ImageTk
                    img = Image.open(path).convert("RGBA").resize(
                        (32, 32), Image.Resampling.LANCZOS
                    )
                    self._icon_photo = ImageTk.PhotoImage(img)
                    self._window.iconphoto(True, self._icon_photo)
                    return
                except Exception as e:
                    logger.debug("Ícone da janela: %s", e)

    # ── Construção da UI ──────────────────────────────────────────────────────

    def _build(self, status: str) -> None:
        self._build_header()
        self._build_status(status)
        self._build_footer()           # reserva espaço no bottom ANTES do canvas expandir
        self._build_scrollable_content()

    def _build_scrollable_content(self) -> None:
        self._scroll_outer = tk.Frame(self._window, bg=C_BG)
        self._scroll_outer.pack(fill=tk.BOTH, expand=True)

        self._canvas = tk.Canvas(self._scroll_outer, bg=C_BG, highlightthickness=0, bd=0)
        self._vscroll = ttk.Scrollbar(self._scroll_outer, orient="vertical",
                                      command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vscroll.set)

        # A scrollbar é empacotada sob demanda (só quando o conteúdo transborda).
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._scroll_inner = tk.Frame(self._canvas, bg=C_BG)
        self._cw_id = self._canvas.create_window((0, 0), window=self._scroll_inner, anchor="nw")

        self._scroll_inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self._build_content(self._scroll_inner)

    def _on_inner_configure(self, _event: Optional[tk.Event] = None) -> None:
        self._update_scrollregion()
        self._update_scrollbar()

    def _on_canvas_configure(self, event: tk.Event) -> None:
        # Limita a largura do conteúdo e centraliza em telas largas.
        width = min(event.width, MAX_CONTENT_W)
        x = max(0, (event.width - width) // 2)
        self._canvas.coords(self._cw_id, x, 0)
        self._canvas.itemconfig(self._cw_id, width=width)
        self._update_scrollregion()
        self._update_scrollbar()

    def _update_scrollregion(self) -> None:
        # Região de rolagem fixada em 0..largura (sem o deslocamento horizontal
        # da centralização). Usar bbox("all") aqui herdaria o offset e faria o
        # conteúdo "sumir" (fundo cinza) ao restaurar a janela maximizada.
        content_h = self._scroll_inner.winfo_reqheight()
        cw = max(self._canvas.winfo_width(), 1)
        self._canvas.configure(scrollregion=(0, 0, cw, content_h))

    def _update_scrollbar(self) -> None:
        """Mostra a scrollbar apenas quando o conteúdo não cabe na viewport."""
        try:
            need = self._scroll_inner.winfo_reqheight() > self._canvas.winfo_height() + 1
        except tk.TclError:
            return
        mapped = self._vscroll.winfo_ismapped()
        if need and not mapped:
            self._vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        elif not need and mapped:
            self._vscroll.pack_forget()

    def _on_mousewheel(self, event: tk.Event) -> None:
        # Só rola quando há conteúdo transbordando (evita "pulos" quando cabe tudo).
        if self._scroll_inner.winfo_reqheight() <= self._canvas.winfo_height():
            return
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _bind_mousewheel(self) -> None:
        """Liga a roda do mouse em cada widget da área rolável.

        Binding por-widget (em vez de bind_all via Enter/Leave) evita o bug em
        que entrar num filho dispara <Leave> no canvas e desliga a rolagem.
        A seção avançada já é construída no init (só não é empacotada), então
        também fica coberta aqui.
        """
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._recursive_bind(self._scroll_inner)

    def _recursive_bind(self, widget: tk.Widget) -> None:
        widget.bind("<MouseWheel>", self._on_mousewheel)
        for child in widget.winfo_children():
            self._recursive_bind(child)

    def _build_header(self) -> None:
        hdr = tk.Frame(self._window, bg=C_CARD)
        hdr.pack(fill=tk.X)

        inner = tk.Frame(hdr, bg=C_CARD)
        inner.pack(fill=tk.X, padx=20, pady=14)

        logo_path = os.path.join(_base_dir(), LOGO_FILE)
        if os.path.isfile(logo_path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(logo_path).convert("RGBA")
                lh = 36
                lw = max(1, int(img.width * lh / img.height))
                img = img.resize((lw, lh), Image.Resampling.LANCZOS)
                self._logo_photo = ImageTk.PhotoImage(img)
                tk.Label(inner, image=self._logo_photo, bg=C_CARD).pack(
                    side=tk.LEFT, padx=(0, 16)
                )
            except Exception as e:
                logger.debug("Logo: %s", e)

        info = tk.Frame(inner, bg=C_CARD)
        info.pack(side=tk.LEFT, anchor="center")
        tk.Label(info, text="Configurações", bg=C_CARD, fg=C_PRIMARY,
                 font=F_HERO).pack(anchor="w")
        tk.Label(info, text="Agente de Impressão · Meu Atendimento Virtual",
                 bg=C_CARD, fg=C_MUTED, font=F_SUB).pack(anchor="w")

        tk.Label(inner, text=f"v{config.APP_VERSION}", bg=C_CARD, fg=C_BORDER,
                 font=F_SUB).pack(side=tk.RIGHT, anchor="s")

    def _build_status(self, status: str) -> None:
        wrap = tk.Frame(self._window, bg=C_BG)
        wrap.pack(fill=tk.X, padx=16, pady=(12, 0))

        outer, card = _card_frames(wrap)
        outer.pack(fill=tk.X)

        row = tk.Frame(card, bg=C_CARD)
        row.pack(fill=tk.X, padx=14, pady=10)

        self._dot = tk.Canvas(row, width=10, height=10,
                              bg=C_CARD, highlightthickness=0)
        self._dot.pack(side=tk.LEFT, pady=1)

        self._status_lbl = tk.Label(row, bg=C_CARD, font=F_STATUS)
        self._status_lbl.pack(side=tk.LEFT, padx=(8, 0))

        # Botão para forçar reconexão manual (visível e sempre à mão).
        self._reconnect_btn = _OBtn(row, "↻  Reconectar", self._reconnect,
                                    color=C_PRIMARY, w=118, h=28)
        self._reconnect_btn.pack(side=tk.RIGHT)
        _Icon(row, "plug", size=14, color=C_MUTED, bg=C_CARD).pack(
            side=tk.RIGHT, padx=(0, 8))

        self._render_status(status)

    def _reconnect(self) -> None:
        """Aciona uma reconexão manual e dá feedback imediato no status."""
        self._render_status("reconnecting")
        if self._on_reconnect:
            self._on_reconnect()
        elif self._on_test_connection:
            self._on_test_connection()

    def _build_content(self, parent: tk.Widget) -> None:
        wrap = tk.Frame(parent, bg=C_BG)
        wrap.pack(fill=tk.BOTH, padx=16, pady=12)

        # ─── Área visível ao cliente comum ──────────────────────────────────

        # Autenticação
        outer, auth = self._section_card(wrap, "AUTENTICAÇÃO", icon="key")
        outer.pack(fill=tk.X, pady=(0, 10))
        self._token_var = tk.StringVar()
        self._token_entry = self._entry_row(auth, "Token de acesso", self._token_var, show="*")
        self._show_token_var = tk.BooleanVar(value=False)
        show_row = tk.Frame(auth, bg=C_CARD)
        show_row.pack(fill=tk.X, padx=14, pady=(4, 10))
        tk.Checkbutton(
            show_row, text="Mostrar token", variable=self._show_token_var,
            command=self._toggle_token, bg=C_CARD, fg=C_MUTED, font=F_SUB,
            activebackground=C_CARD, bd=0, cursor="hand2", highlightthickness=0,
        ).pack(anchor="e")

        # Impressora
        outer, prn = self._section_card(wrap, "IMPRESSORA", icon="printer")
        outer.pack(fill=tk.X, pady=(0, 10))
        self._printer_var = tk.StringVar()
        self._printer_combo = self._combo_row(prn, "Dispositivo", self._printer_var, [])
        self._printer_combo.configure(state="normal")
        rrow = tk.Frame(prn, bg=C_CARD)
        rrow.pack(fill=tk.X, padx=14, pady=(6, 10))
        _OBtn(rrow, "↺  Atualizar lista", self._refresh_printers,
              color=C_MUTED, w=142, h=26).pack(side=tk.RIGHT)

        # Comprovante
        outer, rec = self._section_card(wrap, "COMPROVANTE", icon="receipt")
        outer.pack(fill=tk.X, pady=(0, 10))
        self._receipt_model_var = tk.StringVar()
        self._receipt_combo = self._combo_row(rec, "Modelo de layout", self._receipt_model_var,
                                              list(config.RECEIPT_MODEL_LABELS.values()))
        tk.Frame(rec, bg=C_CARD, height=8).pack()

        # ─── Link discreto "Avançado" ───────────────────────────────────────
        # Quase invisível: cinza claro, sem card. A maioria dos clientes nunca
        # precisa abrir; suporte expande quando necessário.
        self._adv_toggle = tk.Label(
            wrap, text="⚙  Configurações avançadas  ▾",
            bg=C_BG, fg=C_MUTED, font=F_SUB, cursor="hand2",
        )
        self._adv_toggle.pack(anchor="w", pady=(4, 2))
        self._adv_toggle.bind("<Button-1>", lambda _e: self._toggle_advanced())
        self._adv_toggle.bind("<Enter>", lambda _e: self._adv_toggle.configure(fg=C_PRIMARY))
        self._adv_toggle.bind("<Leave>", lambda _e: self._adv_toggle.configure(fg=C_MUTED))

        # ─── Container avançado (oculto por padrão) ──────────────────────────
        self._adv_container = tk.Frame(wrap, bg=C_BG)

        # Servidor
        outer, srv = self._section_card(self._adv_container, "SERVIDOR", icon="server")
        outer.pack(fill=tk.X, pady=(4, 10))
        self._env_var = tk.StringVar()
        self._env_combo = self._combo_row(srv, "Ambiente", self._env_var,
                                          list(config.ENVIRONMENT_LABELS.values()))
        self._env_combo.bind("<<ComboboxSelected>>", self._on_env_change)
        self._url_var = tk.StringVar()
        self._url_entry = self._entry_row(srv, "URL do servidor", self._url_var)
        tk.Frame(srv, bg=C_CARD, height=8).pack()

        # Opções
        outer, opt = self._section_card(self._adv_container, "OPÇÕES", icon="sliders")
        outer.pack(fill=tk.X, pady=(0, 10))
        self._auto_connect_var = tk.BooleanVar()
        self._start_windows_var = tk.BooleanVar()
        for var, label in (
            (self._auto_connect_var,  "Conectar automaticamente ao iniciar"),
            (self._start_windows_var, "Iniciar com o Windows automaticamente"),
        ):
            r = tk.Frame(opt, bg=C_CARD)
            r.pack(fill=tk.X, padx=14, pady=(8, 0))
            tk.Checkbutton(
                r, text=label, variable=var, bg=C_CARD, fg=C_TEXT,
                font=F_LABEL, bd=0, cursor="hand2",
                activebackground=C_CARD, highlightthickness=0,
            ).pack(anchor="w")
        tk.Frame(opt, bg=C_CARD, height=10).pack()

        # Logs (ferramenta de suporte)
        logs_row = tk.Frame(self._adv_container, bg=C_BG)
        logs_row.pack(fill=tk.X, pady=(0, 2))
        _OBtn(logs_row, "Exibir Logs", self._open_logs,
              color=C_MUTED, w=110, h=30).pack(side=tk.LEFT)

    def _toggle_advanced(self) -> None:
        self._adv_open = not self._adv_open
        if self._adv_open:
            self._adv_container.pack(fill=tk.X, after=self._adv_toggle)
            self._adv_toggle.configure(text="⚙  Ocultar configurações avançadas  ▴")
        else:
            self._adv_container.pack_forget()
            self._adv_toggle.configure(text="⚙  Configurações avançadas  ▾")
        self._relayout()

    def _relayout(self) -> None:
        """Recalcula rolagem e altura da janela após expandir/recolher seções."""
        self._window.update_idletasks()
        self._on_inner_configure()
        self._fit_geometry(center=False)

    def _fit_geometry(self, center: bool = False) -> None:
        """Ajusta tamanho/posição da janela à tela, sem estourar totens pequenos.

        A altura acompanha o conteúdo, limitada à tela disponível; o excedente
        fica acessível via rolagem. O rodapé (side=BOTTOM) permanece sempre
        visível. Em ``center=False`` preserva a posição atual, apenas evitando
        que a janela ultrapasse a base da tela.
        """
        self._window.update_idletasks()
        sw = self._window.winfo_screenwidth()
        sh = self._window.winfo_screenheight()

        w = min(DEFAULT_W, sw - 40)

        # Altura ideal = partes fixas (header+status+footer) + conteúdo rolável.
        content_h = self._scroll_inner.winfo_reqheight()
        fixed_h   = self._window.winfo_reqheight() - self._scroll_outer.winfo_reqheight()
        ideal_h   = fixed_h + content_h

        max_h = sh - 80
        min_h = min(360, max_h)
        h = max(min_h, min(ideal_h, max_h))

        if center:
            x = (sw - w) // 2
            y = max(0, (sh - h) // 2)
        else:
            x = self._window.winfo_x()
            y = self._window.winfo_y()
            if y + h > sh - 20:            # não deixa passar da base da tela
                y = max(0, sh - 20 - h)

        self._window.geometry(f"{w}x{h}+{x}+{y}")

    def _build_footer(self) -> None:
        # side=BOTTOM garante que o footer sempre fica visível,
        # mesmo quando o canvas com expand=True toma o restante do espaço.
        footer = tk.Frame(self._window, bg=C_CARD)
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Frame(self._window, bg=C_BORDER, height=1).pack(side=tk.BOTTOM, fill=tk.X)

        row = tk.Frame(footer, bg=C_CARD)
        row.pack(fill=tk.X, padx=16, pady=12)

        # Direita: ações (empacotado em ordem inversa para pack(side=RIGHT))
        _Btn( row, "Salvar",           self._save,            w=82,  h=34).pack(side=tk.RIGHT)
        self._test_print_btn = _OBtn(row, "Testar Impressão", self._test_print, w=122, h=34)
        self._test_print_btn.pack(side=tk.RIGHT, padx=(0, 6))
        _OBtn(row, "Testar Conexão",   self._test_connection, w=116, h=34).pack(side=tk.RIGHT, padx=(0, 6))

    def _open_logs(self) -> None:
        LogsWindow.show(self._window)

    # ── Helpers de layout ─────────────────────────────────────────────────────

    def _section_card(self, parent: tk.Widget, title: str, icon: Optional[str] = None):
        """Retorna (outer_to_pack, card_frame) com strip de título e ícone."""
        outer, card = _card_frames(parent)

        strip = tk.Frame(card, bg=C_PRIMARY_LIGHT)
        strip.pack(fill=tk.X)
        if icon:
            _Icon(strip, icon, size=16, color=C_PRIMARY, bg=C_PRIMARY_LIGHT).pack(
                side=tk.LEFT, padx=(14, 0), pady=6)
            tk.Label(strip, text=title, bg=C_PRIMARY_LIGHT, fg=C_PRIMARY,
                     font=F_SECTION, padx=8, pady=6).pack(side=tk.LEFT)
        else:
            tk.Label(strip, text=title, bg=C_PRIMARY_LIGHT, fg=C_PRIMARY,
                     font=F_SECTION, padx=14, pady=6).pack(side=tk.LEFT)

        return outer, card

    def _combo_row(self, card: tk.Widget, label: str,
                   var: tk.StringVar, values: list) -> ttk.Combobox:
        row = tk.Frame(card, bg=C_CARD)
        row.pack(fill=tk.X, padx=14, pady=(10, 0))

        tk.Label(row, text=label, bg=C_CARD, fg=C_MUTED,
                 font=F_LABEL, width=16, anchor="w").pack(side=tk.LEFT)

        style = ttk.Style()
        style.configure("Mod.TCombobox", padding=(6, 4))
        combo = ttk.Combobox(row, textvariable=var, values=values,
                             state="readonly", width=26, font=F_INPUT,
                             style="Mod.TCombobox")
        combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
        return combo

    def _entry_row(self, card: tk.Widget, label: str,
                   var: tk.StringVar, show: str = "") -> tk.Entry:
        row = tk.Frame(card, bg=C_CARD)
        row.pack(fill=tk.X, padx=14, pady=(10, 0))

        tk.Label(row, text=label, bg=C_CARD, fg=C_MUTED,
                 font=F_LABEL, width=16, anchor="w").pack(side=tk.LEFT)

        # Border frame simulates input border with focus highlight
        border = tk.Frame(row, bg=C_BORDER, padx=1, pady=1)
        border.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

        ef = tk.Frame(border, bg=C_INPUT_BG)
        ef.pack(fill=tk.X)

        entry = tk.Entry(ef, textvariable=var, bg=C_INPUT_BG, fg=C_TEXT,
                         font=F_INPUT, bd=0, highlightthickness=0,
                         insertbackground=C_PRIMARY)
        if show:
            entry.configure(show=show)
        entry.pack(fill=tk.X, padx=8, pady=5)

        entry.bind("<FocusIn>",  lambda e: border.configure(bg=C_PRIMARY))
        entry.bind("<FocusOut>", lambda e: border.configure(bg=C_BORDER))
        return entry

    # ── Status ────────────────────────────────────────────────────────────────

    def _render_status(self, status: str) -> None:
        colors = {
            "connected":    C_SUCCESS,
            "disconnected": C_ERROR,
            "connecting":   C_WARNING,
            "reconnecting": C_WARNING,
        }
        labels = {
            "connected":    "Conectado",
            "disconnected": "Desconectado",
            "connecting":   "Conectando...",
            "reconnecting": "Reconectando...",
        }
        c = colors.get(status, "#94a3b8")
        self._dot.delete("all")
        self._dot.create_oval(1, 1, 9, 9, fill=c, outline=c)
        self._status_lbl.configure(text=labels.get(status, status), fg=c)

    def update_status(self, status: str) -> None:
        try:
            self._render_status(status)
        except tk.TclError:
            pass

    # ── Lógica de formulário ──────────────────────────────────────────────────

    def _load(self) -> None:
        env_key = self._config.get("environment", "producao_br")
        self._env_var.set(config.ENVIRONMENT_LABELS.get(env_key, "Produção Brasil"))
        self._url_var.set(self._config.get("server_url", ""))
        self._update_url_state()

        self._token_var.set(config.get_auth_token(self._config))

        self._refresh_printers()
        p = self._config.get("printer_name", "")
        if p:
            self._printer_var.set(p)

        receipt = self._config.get("receipt_model", "default")
        self._receipt_model_var.set(
            config.RECEIPT_MODEL_LABELS.get(receipt, config.RECEIPT_MODEL_LABELS["default"])
        )
        self._auto_connect_var.set(self._config.get("auto_connect", True))
        self._start_windows_var.set(self._config.get("start_with_windows", True))

    def _on_env_change(self, _=None) -> None:
        self._update_url_state()

    def _update_url_state(self) -> None:
        label = self._env_var.get()
        is_custom = label == config.ENVIRONMENT_LABELS.get("custom", "Personalizado")
        self._url_entry.configure(state="normal" if is_custom else "disabled")
        if not is_custom:
            key = self._label_to_key(label)
            url = config.ENVIRONMENTS.get(key, "")
            if url:
                self._url_var.set(url)

    def _label_to_key(self, label: str) -> str:
        for k, v in config.ENVIRONMENT_LABELS.items():
            if v == label:
                return k
        return "producao_br"

    def _receipt_key_from_label(self, label: str) -> str:
        for k, v in config.RECEIPT_MODEL_LABELS.items():
            if v == label:
                return k
        return "default"

    def _toggle_token(self) -> None:
        self._token_entry.configure(show="" if self._show_token_var.get() else "*")

    def _refresh_printers(self) -> None:
        printers = printer_service.list_printers()
        self._printer_combo["values"] = printers
        if printers and not self._printer_var.get():
            self._printer_var.set(printers[0])

    def _save(self) -> None:
        env_label = self._env_var.get()
        env_key   = self._label_to_key(env_label)
        cfg = dict(self._config)
        cfg["environment"]      = env_key
        cfg["server_url"]       = self._url_var.get().strip()
        cfg["printer_name"]     = self._printer_var.get().strip()
        cfg["auto_connect"]     = self._auto_connect_var.get()
        cfg["start_with_windows"] = self._start_windows_var.get()
        cfg["receipt_model"]    = self._receipt_key_from_label(self._receipt_model_var.get())
        config.set_auth_token(cfg, self._token_var.get().strip())
        config.save_config(cfg)
        self._config = cfg
        logger.info(
            "Configurações salvas pelo usuário (ambiente: %s, impressora: %s). Aplicando e reconectando...",
            env_label or "-", cfg["printer_name"] or "nenhuma",
        )
        if self._on_save:
            self._on_save(cfg)
        messagebox.showinfo(
            "Configurações salvas",
            "As configurações foram salvas com sucesso!",
            parent=self._window,
        )

    def _test_print(self) -> None:
        if getattr(self, "_testing_print", False):
            return
        p = self._printer_var.get().strip()
        if not p:
            messagebox.showwarning("Impressão", "Selecione uma impressora.", parent=self._window)
            return

        self._testing_print = True
        btn = getattr(self, "_test_print_btn", None)
        if btn is not None:
            try:
                btn.set_text("Testando...")
                btn.set_enabled(False)
            except tk.TclError:
                pass

        def _restore_btn():
            self._testing_print = False
            if btn is not None:
                try:
                    btn.set_text("Testar Impressão")
                    btn.set_enabled(True)
                except tk.TclError:
                    pass

        def _run():
            try:
                if self._on_test_print:
                    result = self._on_test_print(p)
                    ok, msg = result if result is not None else (None, None)
                else:
                    ok, msg = printer_service.test_print(p)
                if ok is not None:
                    try:
                        self._window.after(0, lambda o=ok, m=msg: (
                            messagebox.showinfo("Impressão", m, parent=self._window) if o
                            else messagebox.showerror("Impressão", m, parent=self._window)
                        ))
                    except tk.TclError:
                        pass
            except Exception as exc:
                try:
                    self._window.after(0, lambda e=str(exc):
                        messagebox.showerror("Impressão", f"Erro: {e}", parent=self._window)
                    )
                except tk.TclError:
                    pass
            finally:
                try:
                    self._window.after(0, _restore_btn)
                except tk.TclError:
                    pass

        import threading
        threading.Thread(target=_run, daemon=True).start()

    def _test_connection(self) -> None:
        if self._on_test_connection:
            self._on_test_connection()
            messagebox.showinfo(
                "Testar Conexão",
                "Tentando conectar ao servidor.\nO status acima será atualizado em instantes.",
                parent=self._window,
            )
        else:
            messagebox.showinfo("Conexão", "Função não configurada.", parent=self._window)

    def _close(self) -> None:
        ConfigWindow._instance = None
        self._window.destroy()


# ─── Janela de Logs ───────────────────────────────────────────────────────────

class LogsWindow:
    """Janela que exibe os logs do agente em tempo real."""

    _instance: Optional["LogsWindow"] = None

    @classmethod
    def show(cls, parent: tk.Widget) -> None:
        if cls._instance is not None:
            try:
                cls._instance._window.lift()
                cls._instance._window.focus_force()
                cls._instance._refresh()
                return
            except tk.TclError:
                cls._instance = None
        cls._instance = cls(parent)

    # Intervalo de atualização em tempo real (ms).
    _TICK_MS = 500

    def __init__(self, parent: tk.Widget):
        self._window = tk.Toplevel(parent)
        self._window.title("Logs · Agente de Impressão")
        self._window.configure(bg=C_BG)
        self._window.resizable(True, True)
        self._window.protocol("WM_DELETE_WINDOW", self._close)

        # Índice absoluto do último registro já renderizado (leitura incremental).
        self._seen = 0
        self._tick_job: Optional[str] = None

        self._build()

        self._window.update_idletasks()
        # Ajusta à tela (funciona em totens menores que 720×520).
        sw = self._window.winfo_screenwidth()
        sh = self._window.winfo_screenheight()
        w = min(720, sw - 40)
        h = min(520, sh - 60)
        self._window.minsize(min(420, sw - 20), min(300, sh - 40))
        self._window.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        self._window.focus_force()
        self._refresh()          # carga inicial completa
        self._schedule_tick()    # atualização incremental em tempo real

    def _build(self) -> None:
        # Cabeçalho
        hdr = tk.Frame(self._window, bg=C_PRIMARY)
        hdr.pack(fill=tk.X)
        inner = tk.Frame(hdr, bg=C_PRIMARY)
        inner.pack(fill=tk.X, padx=20, pady=14)
        tk.Label(inner, text="Logs do Sistema", bg=C_PRIMARY, fg="#ffffff",
                 font=F_HERO).pack(anchor="w")
        tk.Label(inner, text="Histórico de eventos e erros do agente",
                 bg=C_PRIMARY, fg="#8ca0d0", font=F_SUB).pack(anchor="w")

        # Área de texto
        body = tk.Frame(self._window, bg=C_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        outer, card = _card_frames(body)
        outer.pack(fill=tk.BOTH, expand=True)

        text_frame = tk.Frame(card, bg="#1e2a4a")
        text_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        scrollbar_y = ttk.Scrollbar(text_frame, orient="vertical")
        scrollbar_x = ttk.Scrollbar(text_frame, orient="horizontal")

        self._text = tk.Text(
            text_frame,
            bg="#1e2a4a", fg="#e2e8f0",
            font=("Consolas", 9),
            wrap=tk.NONE,
            bd=0, highlightthickness=0,
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
            state="disabled",
            selectbackground=C_PRIMARY,
        )
        scrollbar_y.configure(command=self._text.yview)
        scrollbar_x.configure(command=self._text.xview)

        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self._text.pack(fill=tk.BOTH, expand=True)

        # Cores por nível (configuradas uma única vez).
        self._text.tag_configure("ERROR",   foreground="#f87171")
        self._text.tag_configure("WARNING", foreground="#fbbf24")
        self._text.tag_configure("INFO",    foreground="#86efac")
        self._text.tag_configure("DEBUG",   foreground="#94a3b8")

        # Rodapé
        tk.Frame(self._window, bg=C_BORDER, height=1).pack(fill=tk.X)
        footer = tk.Frame(self._window, bg=C_CARD)
        footer.pack(fill=tk.X)

        live = tk.Frame(footer, bg=C_CARD)
        live.pack(side=tk.LEFT, padx=16, pady=12)
        self._live_dot = tk.Canvas(live, width=9, height=9, bg=C_CARD, highlightthickness=0)
        self._live_dot.create_oval(1, 1, 8, 8, fill=C_SUCCESS, outline=C_SUCCESS)
        self._live_dot.pack(side=tk.LEFT, pady=1)
        tk.Label(live, text="ao vivo", bg=C_CARD, fg=C_MUTED, font=F_SUB).pack(
            side=tk.LEFT, padx=(6, 12))
        self._count_lbl = tk.Label(live, text="", bg=C_CARD, fg=C_MUTED, font=F_SUB)
        self._count_lbl.pack(side=tk.LEFT)

        btn_row = tk.Frame(footer, bg=C_CARD)
        btn_row.pack(side=tk.RIGHT, padx=16, pady=12)
        _OBtn(btn_row, "Limpar", self._clear, color=C_ERROR, w=80, h=34).pack(side=tk.LEFT, padx=(0, 6))
        _OBtn(btn_row, "Atualizar", self._refresh, color=C_MUTED, w=90, h=34).pack(side=tk.LEFT, padx=(0, 6))
        _Btn(btn_row, "Copiar Logs", self._copy, w=110, h=34).pack(side=tk.LEFT)

    @staticmethod
    def _line_tag(line: str) -> str:
        if "[ERROR   ]" in line or "[ERROR]" in line:
            return "ERROR"
        if "[WARNING ]" in line or "[WARNING]" in line:
            return "WARNING"
        if "[DEBUG   ]" in line or "[DEBUG]" in line:
            return "DEBUG"
        return "INFO"

    def _at_bottom(self) -> bool:
        """True se a rolagem está (quase) no fim — para auto-scroll inteligente."""
        try:
            return self._text.yview()[1] >= 0.999
        except tk.TclError:
            return True

    def _append_lines(self, lines: list, autoscroll: bool) -> None:
        if not lines:
            return
        self._text.configure(state="normal")
        for line in lines:
            self._text.insert(tk.END, line + "\n", self._line_tag(line))
        self._text.configure(state="disabled")
        if autoscroll:
            self._text.see(tk.END)

    def _refresh(self) -> None:
        """Carga completa (abertura, botão Atualizar e após Limpar)."""
        try:
            import log_buffer
            total, lines = log_buffer.buffer.get_since(0)
            self._text.configure(state="normal")
            self._text.delete("1.0", tk.END)
            self._text.configure(state="disabled")
            if lines:
                self._append_lines(lines, autoscroll=True)
                self._count_lbl.configure(text=f"{len(lines)} linha(s)")
            else:
                self._text.configure(state="normal")
                self._text.insert(tk.END, "Nenhum log registrado ainda.")
                self._text.configure(state="disabled")
                self._count_lbl.configure(text="0 linha(s)")
            self._seen = total
        except Exception:
            pass

    def _tick(self) -> None:
        """Atualização incremental em tempo real: adiciona só as linhas novas."""
        try:
            import log_buffer
            total, new = log_buffer.buffer.get_since(self._seen)
            if new:
                stick = self._at_bottom()
                self._append_lines(new, autoscroll=stick)
                self._seen = total
                current = int(self._text.index("end-1c").split(".")[0])
                self._count_lbl.configure(text=f"{current} linha(s)")
        except Exception:
            pass

    def _schedule_tick(self) -> None:
        try:
            self._tick()
            self._tick_job = self._window.after(self._TICK_MS, self._schedule_tick)
        except tk.TclError:
            pass

    def _copy(self) -> None:
        try:
            import log_buffer
            logs = log_buffer.buffer.get_logs()
            self._window.clipboard_clear()
            self._window.clipboard_append(logs)
            messagebox.showinfo("Logs", "Logs copiados para a área de transferência!", parent=self._window)
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível copiar: {e}", parent=self._window)

    def _clear(self) -> None:
        if messagebox.askyesno("Limpar Logs", "Deseja limpar todos os logs?", parent=self._window):
            import log_buffer
            log_buffer.buffer.clear()
            self._seen = log_buffer.buffer.total()
            self._text.configure(state="normal")
            self._text.delete("1.0", tk.END)
            self._text.insert(tk.END, "Nenhum log registrado ainda.")
            self._text.configure(state="disabled")
            self._count_lbl.configure(text="0 linha(s)")

    def _close(self) -> None:
        if self._tick_job is not None:
            try:
                self._window.after_cancel(self._tick_job)
            except tk.TclError:
                pass
            self._tick_job = None
        LogsWindow._instance = None
        self._window.destroy()
