"""
System tray icon com logo e menu de contexto.
"""

import logging
import os
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

# Cor principal da marca
PRIMARY_COLOR = "#334398"

# Cores de status (para fallback quando logo não existe)
COLORS = {
    "connected": "#22c55e",
    "disconnected": "#ef4444",
    "connecting": "#f59e0b",
}

STATUS_LABELS = {
    "connected": "Conectado",
    "disconnected": "Desconectado",
    "connecting": "Conectando...",
}

TRAY_ICON_SIZE = 64


def _tray_icon_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "OG Meu Atendimento Virtual (4).png")


def _create_icon_image(color: str) -> Image.Image:
    """Cria um ícone circular com a cor (fallback quando não há logo)."""
    size = TRAY_ICON_SIZE
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


def _load_tray_icon() -> Image.Image:
    """Carrega o ícone para a bandeja; se não existir, usa ícone na cor principal."""
    path = _tray_icon_path()
    if os.path.isfile(path):
        try:
            img = Image.open(path).convert("RGBA")
            img = img.resize((TRAY_ICON_SIZE, TRAY_ICON_SIZE), Image.Resampling.LANCZOS)
            return img
        except Exception as e:
            logger.warning("Não foi possível carregar o logo da bandeja: %s", e)
    return _create_icon_image(PRIMARY_COLOR)


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
        """Inicia o ícone na bandeja (bloqueia a thread). Usa o logo quando disponível."""
        self._icon = pystray.Icon(
            name="Impressão",
            icon=_load_tray_icon(),
            title="Impressão",
            menu=self._build_menu(),
        )
        self._icon.run()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    def set_status(self, status: str) -> None:
        self._status = status
        if self._icon:
            self._icon.title = f"Impressão — {STATUS_LABELS.get(status, status)}"
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
