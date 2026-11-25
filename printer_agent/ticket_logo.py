"""
Logo impresso no topo do comprovante.

A imagem enviada pelo usuário é guardada em %APPDATA%\\MeuAtendimento e
convertida para o que a impressora térmica consegue imprimir: só preto e
branco, na largura do papel. Logos de cores chapadas viram preto com corte
limpo; fotos e degradês viram pontilhado (Floyd–Steinberg).

O logo é enviado como imagem raster ESC/POS (GS v 0), centralizado.
"""

from __future__ import annotations

import base64
import io
import logging
import os

from PIL import Image, ImageOps

import config

logger = logging.getLogger(__name__)

# Largura máxima × altura máxima em pontos (8 pontos = 1 mm a 203 dpi), por bobina.
SIZES = {
    "80": {"small": (192, 120), "medium": (288, 180), "large": (400, 240)},   # 24, 36 e 50 mm
    "58": {"small": (144, 96), "medium": (216, 136), "large": (320, 192)},    # 18, 27 e 40 mm
}
DEFAULT_SIZE = "medium"
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


def _source_path() -> str:
    return os.path.join(config.get_config_dir(), "ticket_logo_source.png")


def _paper(cfg: dict) -> str:
    paper = str(cfg.get("paper_width") or "80")
    return paper if paper in SIZES else "80"


def _decode_upload(data_url: str) -> Image.Image:
    if not isinstance(data_url, str) or "," not in data_url:
        raise ValueError("Arquivo de imagem inválido.")
    raw = base64.b64decode(data_url.split(",", 1)[1])
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("Imagem muito grande (máximo 8 MB).")
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as e:
        raise ValueError("Não foi possível abrir a imagem. Use PNG ou JPG.") from e
    return img


def _to_printable(src: Image.Image, size: str, paper: str = "80") -> Image.Image:
    """Converte a imagem para 1 bit no tamanho escolhido para a bobina."""
    sizes = SIZES.get(paper, SIZES["80"])
    max_w, max_h = sizes.get(size, sizes[DEFAULT_SIZE])

    # Transparência vira fundo branco
    rgba = src.convert("RGBA")
    flat = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    flat.alpha_composite(rgba)
    gray = flat.convert("L")

    # Remove as margens brancas em volta do desenho
    bbox = gray.point(lambda v: 255 if v < 235 else 0).getbbox()
    if not bbox:
        raise ValueError("A imagem está em branco.")
    gray = gray.crop(bbox)

    # Ajusta ao tamanho (aumenta ou reduz mantendo a proporção)
    scale = min(max_w / gray.width, max_h / gray.height)
    new_size = (max(8, round(gray.width * scale)), max(8, round(gray.height * scale)))
    gray = gray.resize(new_size, Image.LANCZOS)
    gray = ImageOps.autocontrast(gray, cutoff=1)

    # Cores chapadas (logos): corte limpo. Degradês/fotos: pontilhado.
    hist = gray.histogram()
    midtones = sum(hist[48:208]) / max(1, gray.width * gray.height)
    if midtones < 0.25:
        return gray.point(lambda v: 0 if v < 150 else 255).convert("1", dither=Image.NONE)
    return gray.convert("1")


def set_logo(data_url: str, size: str = DEFAULT_SIZE) -> None:
    """Guarda a imagem enviada e gera a versão para impressão."""
    img = _decode_upload(data_url)
    img.thumbnail((1600, 1600))                    # guarda um original de tamanho razoável
    _to_printable(img, size)                       # valida antes de gravar
    if img.mode not in ("RGB", "RGBA", "L", "LA"):
        img = img.convert("RGBA")
    img.save(_source_path(), format="PNG")
    logger.info("Logo do comprovante atualizado (%dx%d, tamanho %s)", img.width, img.height, size)


def set_size(size: str) -> None:
    if size not in SIZES["80"]:
        raise ValueError("Tamanho inválido.")


def remove_logo() -> None:
    try:
        os.remove(_source_path())
    except FileNotFoundError:
        pass
    logger.info("Logo do comprovante removido")


def is_active(cfg: dict) -> bool:
    return bool(cfg.get("logo_enabled")) and os.path.isfile(_source_path())


def version(cfg: dict) -> str:
    """Identifica o logo atual (muda quando ele é trocado/redimensionado/desligado)."""
    if not is_active(cfg):
        return "none"
    stat = os.stat(_source_path())
    return f"{stat.st_mtime_ns}-{stat.st_size}-{cfg.get('logo_size', DEFAULT_SIZE)}-{_paper(cfg)}"


_image_cache: dict = {"key": None, "img": None}


def _printable(cfg: dict) -> Image.Image:
    """Logo em preto e branco no tamanho/bobina da configuração (com cache)."""
    key = version(cfg)
    if _image_cache["key"] != key:
        with Image.open(_source_path()) as src:
            img = _to_printable(src, cfg.get("logo_size", DEFAULT_SIZE), _paper(cfg))
        _image_cache.update(key=key, img=img)
    return _image_cache["img"]


_raster_cache: dict = {"key": None, "data": b""}


def raster_bytes(cfg: dict | None = None) -> bytes:
    """Comandos ESC/POS do logo (centralizado + uma linha de respiro), ou b''."""
    cfg = cfg if cfg is not None else config.load_config()
    key = version(cfg)
    if key == "none":
        return b""
    if _raster_cache["key"] == key:
        return _raster_cache["data"]
    img = _printable(cfg)
    width_bytes = (img.width + 7) // 8
    padded = Image.new("1", (width_bytes * 8, img.height), 1)
    padded.paste(img, (0, 0))
    # No modo "1" do Pillow o bit 1 é branco; na impressora o bit 1 é preto.
    bits = ImageOps.invert(padded.convert("L")).convert("1").tobytes()
    data = (
        b"\x1B\x61\x01"                                         # centraliza
        + b"\x1D\x76\x30\x00"                                   # GS v 0 — imagem raster
        + bytes([width_bytes & 0xFF, width_bytes >> 8, img.height & 0xFF, img.height >> 8])
        + bits
        + b"\r\n"
    )
    _raster_cache.update(key=key, data=data)
    return data


def info(cfg: dict) -> dict:
    """Dados do logo para a interface (miniatura em preto e branco, como imprime)."""
    if not is_active(cfg):
        return {"enabled": False, "size": cfg.get("logo_size", DEFAULT_SIZE)}
    img = _printable(cfg)
    buf = io.BytesIO()
    img.convert("L").save(buf, format="PNG")
    return {
        "enabled": True,
        "size": cfg.get("logo_size", DEFAULT_SIZE),
        "image": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii"),
        "width_mm": round(img.width / 8),
        "height_mm": round(img.height / 8),
    }
