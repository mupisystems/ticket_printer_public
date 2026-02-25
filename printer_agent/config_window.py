"""
Janela de configuração (tkinter) para o agente de impressão.
Layout moderno com logo e cor principal da marca.
"""

import logging
import os
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

import config
import printer_service

logger = logging.getLogger(__name__)

# Cor principal da marca
PRIMARY_COLOR = "#334398"
PRIMARY_DARK = "#2a3780"
BG_WINDOW = "#f5f5f5"
BG_CARD = "#ffffff"
LABEL_WIDTH_CHARS = 14
PAD_X = 12
PAD_Y = 8


def _logo_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "siga_new_logo.png")


def _label(parent: ttk.Frame, text: str, row: int) -> None:
    """Label alinhado com largura fixa para coluna 0."""
    lbl = ttk.Label(parent, text=text)
    lbl.grid(row=row, column=0, sticky="w", pady=(0, PAD_Y))
    parent.columnconfigure(0, minsize=120)


class ConfigWindow:
    """Janela de configuração como Toplevel. Singleton gerenciado externamente."""

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
    ) -> None:
        """Abre ou foca a janela (deve ser chamado da thread principal do tkinter)."""
        if cls._instance is not None:
            try:
                cls._instance._window.lift()
                cls._instance._window.focus_force()
                return
            except tk.TclError:
                cls._instance = None

        cls._instance = cls(
            tk_root, current_config, on_save, on_test_print, on_test_connection, connection_status
        )

    def __init__(
        self,
        tk_root: tk.Tk,
        current_config: dict,
        on_save: Optional[Callable[[dict], None]] = None,
        on_test_print: Optional[Callable[[str], None]] = None,
        on_test_connection: Optional[Callable] = None,
        connection_status: str = "disconnected",
    ):
        self._on_save = on_save
        self._on_test_print = on_test_print
        self._on_test_connection = on_test_connection
        self._config = current_config

        self._window = tk.Toplevel(tk_root)
        self._window.title("Configurações de Impressão")
        self._window.resizable(False, False)
        self._window.configure(bg=BG_WINDOW)
        self._window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._logo_photo = None  # referência para o logo (evitar GC)
        self._build_ui(connection_status)
        self._load_values()
        self._window.focus_force()

    def _build_ui(self, connection_status: str) -> None:
        # --- Cabeçalho com logo (fundo claro para o logo azul aparecer) ---
        header = tk.Frame(self._window, bg=BG_CARD, height=64)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        logo_path = _logo_path()
        if os.path.isfile(logo_path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(logo_path).convert("RGBA")
                h = 40
                w = max(1, int(img.width * h / img.height))
                img = img.resize((w, h), Image.Resampling.LANCZOS)
                self._logo_photo = ImageTk.PhotoImage(img)
                tk.Label(header, image=self._logo_photo, bg=BG_CARD).pack(side=tk.LEFT, padx=(20, 12), pady=12)
            except Exception as e:
                logger.debug("Logo não carregado: %s", e)

        tk.Label(
            header, text="Configurações de Impressão",
            bg=BG_CARD, fg=PRIMARY_COLOR, font=("Segoe UI", 14, "bold")
        ).pack(side=tk.LEFT, pady=16)

        # --- Conteúdo ---
        content = tk.Frame(self._window, bg=BG_WINDOW, padx=24, pady=20)
        content.pack(fill=tk.BOTH, expand=True)

        # Estilo ttk (cor principal nos botões e seções)
        style = ttk.Style()
        try:
            style.theme_use("clam")
            style.configure("TFrame", background=BG_WINDOW)
            style.configure("TLabelframe", background=BG_CARD, padding=14)
            style.configure("TLabelframe.Label", background=BG_CARD, foreground=PRIMARY_COLOR, font=("Segoe UI", 10, "bold"))
            style.configure("TButton", background=PRIMARY_COLOR, foreground="white", padding=(12, 6))
            style.map("TButton", background=[("active", PRIMARY_DARK)])
        except tk.TclError:
            pass

        # Status
        status_frame = ttk.LabelFrame(content, text="Status", padding=10)
        status_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        status_text = {"connected": "Conectado", "disconnected": "Desconectado", "connecting": "Conectando..."}.get(connection_status, connection_status)
        status_color = {"connected": "#16a34a", "disconnected": "#dc2626", "connecting": "#ea580c"}.get(connection_status, "#64748b")
        self._status_label = tk.Label(
            status_frame, text=f"  {status_text}", fg=status_color, font=("Segoe UI", 11, "bold"),
            bg=BG_CARD
        )
        self._status_label.grid(row=0, column=0, sticky="w")

        # Servidor
        env_frame = ttk.LabelFrame(content, text="Servidor", padding=14)
        env_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        _label(env_frame, "Ambiente:", 0)
        self._env_var = tk.StringVar()
        env_labels = list(config.ENVIRONMENT_LABELS.values())
        self._env_combo = ttk.Combobox(env_frame, textvariable=self._env_var, values=env_labels, state="readonly", width=32)
        self._env_combo.grid(row=0, column=1, sticky="ew", padx=(PAD_X, 0), pady=(0, PAD_Y))
        self._env_combo.bind("<<ComboboxSelected>>", self._on_env_change)
        _label(env_frame, "URL do servidor:", 1)
        self._url_var = tk.StringVar()
        self._url_entry = ttk.Entry(env_frame, textvariable=self._url_var, width=42)
        self._url_entry.grid(row=1, column=1, sticky="ew", padx=(PAD_X, 0), pady=(0, PAD_Y))

        # Autenticação
        auth_frame = ttk.LabelFrame(content, text="Autenticação", padding=14)
        auth_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        _label(auth_frame, "Token:", 0)
        self._token_var = tk.StringVar()
        self._token_entry = ttk.Entry(auth_frame, textvariable=self._token_var, show="*", width=42)
        self._token_entry.grid(row=0, column=1, sticky="ew", padx=(PAD_X, 0), pady=(0, PAD_Y))
        self._show_token_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(auth_frame, text="Mostrar token", variable=self._show_token_var, command=self._toggle_token).grid(row=1, column=1, sticky="w", padx=(PAD_X, 0))

        # Modelo de comprovante
        receipt_frame = ttk.LabelFrame(content, text="Modelo de comprovante", padding=14)
        receipt_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        _label(receipt_frame, "Layout:", 0)
        self._receipt_model_var = tk.StringVar()
        receipt_labels = list(config.RECEIPT_MODEL_LABELS.values())
        self._receipt_combo = ttk.Combobox(receipt_frame, textvariable=self._receipt_model_var, values=receipt_labels, state="readonly", width=38)
        self._receipt_combo.grid(row=0, column=1, sticky="ew", padx=(PAD_X, 0), pady=(0, PAD_Y))

        # Impressora
        printer_frame = ttk.LabelFrame(content, text="Impressora", padding=14)
        printer_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        _label(printer_frame, "Impressora:", 0)
        self._printer_var = tk.StringVar()
        self._printer_combo = ttk.Combobox(printer_frame, textvariable=self._printer_var, width=35)
        self._printer_combo.grid(row=0, column=1, sticky="ew", padx=(PAD_X, 0), pady=(0, PAD_Y))
        ttk.Button(printer_frame, text="Atualizar", command=self._refresh_printers, width=10).grid(row=0, column=2, padx=(8, 0), pady=(0, PAD_Y))

        # Auto-connect
        self._auto_connect_var = tk.BooleanVar()
        ttk.Checkbutton(content, text="Conectar automaticamente ao iniciar", variable=self._auto_connect_var).grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 16))

        # Botões (estilo primário)
        btn_frame = tk.Frame(content, bg=BG_WINDOW)
        btn_frame.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        ttk.Button(btn_frame, text="Salvar", command=self._save).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="Testar Impressão", command=self._test_print).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Testar Conexão", command=self._test_connection).pack(side=tk.LEFT, padx=4)

        content.columnconfigure(1, weight=1)
        for f in (status_frame, env_frame, auth_frame, receipt_frame, printer_frame):
            f.columnconfigure(1, weight=1)

    def _load_values(self) -> None:
        env_key = self._config.get("environment", "producao_br")
        env_label = config.ENVIRONMENT_LABELS.get(env_key, "Produção Brasil")
        self._env_var.set(env_label)

        url = self._config.get("server_url", "")
        self._url_var.set(url)
        self._update_url_state()

        token = config.get_auth_token(self._config)
        self._token_var.set(token)

        self._refresh_printers()
        printer_name = self._config.get("printer_name", "")
        if printer_name:
            self._printer_var.set(printer_name)

        receipt_model = self._config.get("receipt_model", "default")
        self._receipt_model_var.set(
            config.RECEIPT_MODEL_LABELS.get(receipt_model, config.RECEIPT_MODEL_LABELS["default"])
        )

        self._auto_connect_var.set(self._config.get("auto_connect", True))

    def _on_env_change(self, event=None) -> None:
        self._update_url_state()

    def _update_url_state(self) -> None:
        label = self._env_var.get()
        is_custom = label == config.ENVIRONMENT_LABELS.get("custom", "Personalizado")
        self._url_entry.configure(state="normal" if is_custom else "disabled")
        if not is_custom:
            env_key = self._label_to_key(label)
            url = config.ENVIRONMENTS.get(env_key, "")
            if url:
                self._url_var.set(url)

    def _label_to_key(self, label: str) -> str:
        for key, lbl in config.ENVIRONMENT_LABELS.items():
            if lbl == label:
                return key
        return "producao_br"

    def _receipt_key_from_label(self, label: str) -> str:
        for key, lbl in config.RECEIPT_MODEL_LABELS.items():
            if lbl == label:
                return key
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
        env_key = self._label_to_key(env_label)

        new_config = dict(self._config)
        new_config["environment"] = env_key
        new_config["server_url"] = self._url_var.get().strip()
        new_config["printer_name"] = self._printer_var.get().strip()
        new_config["auto_connect"] = self._auto_connect_var.get()
        new_config["receipt_model"] = self._receipt_key_from_label(self._receipt_model_var.get())
        config.set_auth_token(new_config, self._token_var.get().strip())
        config.save_config(new_config)
        self._config = new_config

        if self._on_save:
            self._on_save(new_config)

        messagebox.showinfo("Configurações", "Configurações salvas com sucesso!", parent=self._window)

    def _test_print(self) -> None:
        printer_name = self._printer_var.get().strip()
        if not printer_name:
            messagebox.showwarning("Impressão", "Selecione uma impressora.", parent=self._window)
            return
        if self._on_test_print:
            self._on_test_print(printer_name)
        else:
            success, msg = printer_service.test_print(printer_name)
            if success:
                messagebox.showinfo("Impressão", msg, parent=self._window)
            else:
                messagebox.showerror("Impressão", msg, parent=self._window)

    def _test_connection(self) -> None:
        if self._on_test_connection:
            self._on_test_connection()
            messagebox.showinfo(
                "Testar Conexão",
                "Tentando conectar ao servidor. O status acima será atualizado em instantes.",
                parent=self._window,
            )
        else:
            messagebox.showinfo("Conexão", "Função de teste de conexão não configurada.", parent=self._window)

    def _on_close(self) -> None:
        ConfigWindow._instance = None
        self._window.destroy()

    def update_status(self, status: str) -> None:
        status_text = {"connected": "Conectado", "disconnected": "Desconectado", "connecting": "Conectando..."}.get(
            status, status
        )
        status_color = {"connected": "#16a34a", "disconnected": "#dc2626", "connecting": "#ea580c"}.get(status, "#64748b")
        try:
            self._status_label.configure(text=f"  {status_text}", fg=status_color)
        except tk.TclError:
            pass
