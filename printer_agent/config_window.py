"""
Janela de configuração (tkinter) para o agente de impressão.
Usa Toplevel vinculado ao root principal. Singleton.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

import config
import printer_service

logger = logging.getLogger(__name__)


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
        self._window.title("Meu Atendimento - Configurações de Impressão")
        self._window.resizable(False, False)
        self._window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui(connection_status)
        self._load_values()
        self._window.focus_force()

    def _build_ui(self, connection_status: str) -> None:
        main_frame = ttk.Frame(self._window, padding=20)
        main_frame.grid(row=0, column=0, sticky="nsew")

        # Status da conexão
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding=10)
        status_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        status_text = {"connected": "Conectado", "disconnected": "Desconectado", "connecting": "Conectando..."}.get(
            connection_status, connection_status
        )
        status_color = {"connected": "green", "disconnected": "red", "connecting": "orange"}.get(
            connection_status, "gray"
        )
        self._status_label = tk.Label(
            status_frame, text=f"  {status_text}", fg=status_color, font=("Arial", 11, "bold")
        )
        self._status_label.grid(row=0, column=0, sticky="w")

        # Ambiente
        env_frame = ttk.LabelFrame(main_frame, text="Servidor", padding=10)
        env_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(env_frame, text="Ambiente:").grid(row=0, column=0, sticky="w", pady=2)
        self._env_var = tk.StringVar()
        env_labels = list(config.ENVIRONMENT_LABELS.values())
        self._env_combo = ttk.Combobox(
            env_frame, textvariable=self._env_var, values=env_labels, state="readonly", width=30
        )
        self._env_combo.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=2)
        self._env_combo.bind("<<ComboboxSelected>>", self._on_env_change)

        ttk.Label(env_frame, text="URL do servidor:").grid(row=1, column=0, sticky="w", pady=2)
        self._url_var = tk.StringVar()
        self._url_entry = ttk.Entry(env_frame, textvariable=self._url_var, width=40)
        self._url_entry.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=2)

        # Token
        auth_frame = ttk.LabelFrame(main_frame, text="Autenticação", padding=10)
        auth_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(auth_frame, text="Token:").grid(row=0, column=0, sticky="w", pady=2)
        self._token_var = tk.StringVar()
        self._token_entry = ttk.Entry(auth_frame, textvariable=self._token_var, show="*", width=40)
        self._token_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=2)

        self._show_token_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            auth_frame, text="Mostrar token", variable=self._show_token_var, command=self._toggle_token
        ).grid(row=1, column=1, sticky="w", padx=(10, 0))

        # Impressora
        printer_frame = ttk.LabelFrame(main_frame, text="Impressora", padding=10)
        printer_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(printer_frame, text="Impressora:").grid(row=0, column=0, sticky="w", pady=2)
        self._printer_var = tk.StringVar()
        self._printer_combo = ttk.Combobox(
            printer_frame, textvariable=self._printer_var, width=35
        )
        self._printer_combo.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=2)
        ttk.Button(printer_frame, text="Atualizar", command=self._refresh_printers, width=10).grid(
            row=0, column=2, padx=(5, 0), pady=2
        )

        # Auto-connect
        self._auto_connect_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Conectar automaticamente ao iniciar", variable=self._auto_connect_var).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )

        # Botões
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=5, column=0, columnspan=2, sticky="ew")

        ttk.Button(btn_frame, text="Salvar", command=self._save).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(btn_frame, text="Testar Impressão", command=self._test_print).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="Testar Conexão", command=self._test_connection).grid(row=0, column=2, padx=5)

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
        else:
            messagebox.showinfo("Conexão", "Função de teste de conexão não configurada.", parent=self._window)

    def _on_close(self) -> None:
        ConfigWindow._instance = None
        self._window.destroy()

    def update_status(self, status: str) -> None:
        status_text = {"connected": "Conectado", "disconnected": "Desconectado", "connecting": "Conectando..."}.get(
            status, status
        )
        status_color = {"connected": "green", "disconnected": "red", "connecting": "orange"}.get(status, "gray")
        try:
            self._status_label.configure(text=f"  {status_text}", fg=status_color)
        except tk.TclError:
            pass
