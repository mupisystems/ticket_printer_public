"""
System tray icon com indicação de status e menu de contexto.
"""

import logging
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

# Cores de status para o ícone
COLORS = {
    "connected": "#22c55e",     # verde
    "disconnected": "#ef4444",  # vermelho
    "connecting": "#f59e0b",    # amarelo
}

STATUS_LABELS = {
    "connected": "Conectado",
    "disconnected": "Desconectado",
    "connecting": "Conectando...",
}


def _create_icon_image(color: str) -> Image.Image:
    """Cria um ícone circular simples com a cor do status."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=color,
        outline="#1e293b",
        width=2,
    )
    return img


class TrayIcon:
    def __init__(
        self,
        on_open_config: Optional[Callable] = None,
        on_reconnect: Optional[Callable] = None,
        on_test_print: Optional[Callable] = None,
        on_exit: Optional[Callable] = None,
    ):
        self._on_open_config = on_open_config
        self._on_reconnect = on_reconnect
        self._on_test_print = on_test_print
        self._on_exit = on_exit
        self._status = "disconnected"
        self._icon: Optional[pystray.Icon] = None

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(
                lambda _: f"Status: {STATUS_LABELS.get(self._status, self._status)}",
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Configurações", self._handle_open_config),
            pystray.MenuItem("Reconectar", self._handle_reconnect),
            pystray.MenuItem("Impressão de Teste", self._handle_test_print),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", self._handle_exit),
        )

    def start(self) -> None:
        """Inicia o ícone na bandeja (bloqueia a thread)."""
        self._icon = pystray.Icon(
            name="MeuAtendimento Printer",
            icon=_create_icon_image(COLORS["disconnected"]),
            title="Meu Atendimento - Impressão",
            menu=self._build_menu(),
        )
        self._icon.run()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    def set_status(self, status: str) -> None:
        self._status = status
        if self._icon:
            color = COLORS.get(status, COLORS["disconnected"])
            self._icon.icon = _create_icon_image(color)
            self._icon.title = f"Meu Atendimento - {STATUS_LABELS.get(status, status)}"
            self._icon.update_menu()

    def _handle_open_config(self, icon, item) -> None:
        if self._on_open_config:
            self._on_open_config()

    def _handle_reconnect(self, icon, item) -> None:
        if self._on_reconnect:
            self._on_reconnect()

    def _handle_test_print(self, icon, item) -> None:
        if self._on_test_print:
            self._on_test_print()

    def _handle_exit(self, icon, item) -> None:
        if self._on_exit:
            self._on_exit()
        self.stop()
