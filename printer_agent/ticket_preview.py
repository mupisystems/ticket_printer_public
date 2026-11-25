"""
Prévia fiel do comprovante.

Gera os MESMOS comandos ESC/POS que vão para a impressora (com dados de
exemplo) e os interpreta como uma impressora térmica: 80 mm (papel de 640
pontos, área útil de 576) ou 58 mm (464 e 384), fonte A 12×24, fonte B 9×17,
ampliações por duplicação de pontos. O resultado é uma imagem PNG do ticket como sai no papel.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import time
from datetime import datetime
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

import ticket_formatter as tf

logger = logging.getLogger(__name__)

PAPER_DOTS = {"80": 640, "58": 464}   # largura física da bobina a 203 dpi (8 pontos = 1 mm)
FONT_A = (12, 24)
FONT_B = (9, 17)
LINE_GAP = 6                      # espaçamento padrão (30 pontos para fonte de 24)
TOP = 14

SAMPLE = {
    "header": "Bem-vindo!",
    "code": "A042",
    "services": "Caixa",
    "footer": "Aguarde ser chamado. Obrigado!",
}
DEFAULT_QR = "https://painel.meuatendimentovirtual.com.br/acompanhe/A042"
SAMPLE_FILE = "ticket_sample.json"
_EC_LEVELS = {48: "L", 49: "M", 50: "Q", 51: "H"}

@lru_cache(maxsize=1)
def _codepages() -> dict:
    """ESC t n → codec do Python, conforme o perfil usado na impressão (TM-T20II)."""
    import codecs
    pages = {0: "cp437", 2: "cp850", 3: "cp860", 13: "cp857", 16: "cp1252", 19: "cp858"}
    try:
        from escpos.capabilities import get_profile
        for num, name in get_profile("TM-T20II").profile_data["codePages"].items():
            try:
                codecs.lookup(name)
                pages[int(num)] = name.lower()
            except LookupError:
                pass
    except Exception:
        logger.debug("Tabelas de caracteres padrão na prévia", exc_info=True)
    return pages


@lru_cache(maxsize=None)
def _font(bold: bool, small: bool):
    windir = os.environ.get("WINDIR", r"C:\Windows")
    name = "consolab.ttf" if bold else "consola.ttf"
    try:
        return ImageFont.truetype(os.path.join(windir, "Fonts", name), 14 if small else 20)
    except OSError:
        return ImageFont.load_default()


@lru_cache(maxsize=4096)
def _glyph(ch: str, bold: bool, small: bool, rev: bool, w: int, h: int) -> Image.Image:
    cw, chh = FONT_B if small else FONT_A
    img = Image.new("L", (cw, chh), 0 if rev else 255)
    if ch.strip():
        ImageDraw.Draw(img).text((cw / 2, chh / 2), ch, font=_font(bold, small),
                                 fill=255 if rev else 0, anchor="mm")
    if w > 1 or h > 1:
        img = img.resize((cw * w, chh * h), Image.NEAREST)   # ampliação por pontos
    return img


def _parse(data: bytes) -> list:
    """Converte o fluxo ESC/POS em eventos: linhas de texto, QR, imagem, corte."""
    st = dict(align=0, bold=False, w=1, h=1, rev=False, small=False, sp=None, cp="cp437")
    qr = {"data": "", "size": 3, "ec": "L"}
    events, cur = [], []

    def flush():
        nonlocal cur
        events.append(("line", cur, st["align"], st["sp"], st["h"]))
        cur = []

    def reset():
        st.update(align=0, bold=False, w=1, h=1, rev=False, small=False, sp=None)

    i, n = 0, len(data)
    while i < n:
        c = data[i]
        nxt = data[i + 1] if i + 1 < n else 0
        arg = data[i + 2] if i + 2 < n else 0
        if c == 0x1B:                                   # ESC
            if nxt == 0x40:   reset(); i += 2
            elif nxt == 0x32: st["sp"] = None; i += 2
            elif nxt in (0x34, 0x35): i += 2             # itálico (não suportado na Epson)
            elif nxt == 0x33: st["sp"] = arg; i += 3
            elif nxt == 0x61: st["align"] = arg % 48; i += 3
            elif nxt == 0x45: st["bold"] = bool(arg & 1); i += 3
            elif nxt == 0x4D: st["small"] = bool(arg & 1); i += 3
            elif nxt == 0x74: st["cp"] = _codepages().get(arg, st["cp"]); i += 3
            elif nxt == 0x21:
                st["bold"] = bool(arg & 0x08)
                st["h"] = 2 if arg & 0x10 else 1
                st["w"] = 2 if arg & 0x20 else 1
                st["small"] = bool(arg & 0x01)
                i += 3
            elif nxt == 0x64:
                if cur:
                    flush()
                for _ in range(arg):
                    flush()
                i += 3
            else:
                i += 3
        elif c == 0x1D:                                 # GS
            if nxt == 0x21:
                st["w"], st["h"] = (arg >> 4) + 1, (arg & 0x0F) + 1; i += 3
            elif nxt == 0x42:
                st["rev"] = bool(arg & 1); i += 3
            elif nxt == 0x56:
                if cur:
                    flush()
                events.append(("cut",))
                break
            elif nxt == 0x28 and arg == 0x6B:           # GS ( k — QR Code
                length = data[i + 3] + data[i + 4] * 256
                fn = data[i + 6]
                if fn == 0x43:                           # tamanho do módulo
                    qr["size"] = data[i + 7]
                elif fn == 0x45:                         # correção de erro
                    qr["ec"] = _EC_LEVELS.get(data[i + 7], "L")
                elif fn == 0x50:                         # armazena os dados
                    qr["data"] = data[i + 8:i + 5 + length].decode("latin-1", "replace")
                elif fn == 0x51:                         # imprime
                    events.append(("qr", st["align"], qr["data"], qr["size"], qr["ec"]))
                i += 5 + length
            elif nxt == 0x76 and arg == 0x30:           # GS v 0 — imagem raster
                xl, xh, yl, yh = data[i + 4:i + 8]
                bw, bh = xl + xh * 256, yl + yh * 256
                events.append(("raster", bw, bh, data[i + 8:i + 8 + bw * bh], st["align"]))
                i += 8 + bw * bh
            else:
                i += 3
        elif c == 0x1C:                                 # FS (kanji) — ignora
            i += 3 if nxt in (0x21, 0x43) else 2
        elif c == 0x0A:
            flush(); i += 1
        elif c < 0x20:
            i += 1
        else:
            cur.append((bytes([c]).decode(st["cp"], "replace"), dict(st))); i += 1
    if cur:
        flush()
    return events


def _qr_image(content: str, module: int, ec: str, printable: int) -> Image.Image:
    """QR Code como a impressora desenha (módulos de ``module`` pontos, sem borda)."""
    try:
        import qrcode
        levels = {"L": qrcode.constants.ERROR_CORRECT_L, "M": qrcode.constants.ERROR_CORRECT_M,
                  "Q": qrcode.constants.ERROR_CORRECT_Q, "H": qrcode.constants.ERROR_CORRECT_H}
        code = qrcode.QRCode(error_correction=levels.get(ec, levels["L"]),
                             box_size=max(1, module), border=0)
        code.add_data(content or " ")
        code.make(fit=True)
        img = code.make_image(fill_color="black", back_color="white").convert("L")
        if img.width > printable:
            img = img.resize((printable, printable), Image.NEAREST)
        return img
    except Exception:
        img = Image.new("L", (180, 180), 255)                 # sem a biblioteca: marcador simples
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 179, 179], outline=0, width=3)
        d.text((90, 90), "QR", font=_font(True, False), fill=0, anchor="mm")
        return img


def render_bytes(data: bytes, paper: str = "80") -> Image.Image:
    """Desenha o ticket a partir dos comandos ESC/POS na bobina informada."""
    printable = tf.paper_info(paper)["dots"]
    full = PAPER_DOTS.get(paper, PAPER_DOTS["80"])
    margin = (full - printable) // 2

    def _x_for(align: int, width: int) -> int:
        if align == 1:
            return margin + (printable - width) // 2
        if align == 2:
            return margin + printable - width
        return margin

    canvas = Image.new("L", (full, 6000), 255)
    y = TOP
    for ev in _parse(data):
        kind = ev[0]
        if kind == "cut":
            break
        if kind == "qr":
            img = _qr_image(*ev[2:], printable)
            canvas.paste(img, (_x_for(ev[1], img.width), y))
            y += img.height + 8
            continue
        if kind == "raster":
            _, bw, bh, bits, align = ev
            img = Image.frombytes("1", (bw * 8, bh), bytes(bits)).convert("L")
            img = Image.eval(img, lambda v: 255 - v)
            canvas.paste(img, (_x_for(align, bw * 8), y))
            y += bh
            continue
        _, segs, align, sp, cur_h = ev
        if not segs:                                    # linha em branco
            y += FONT_A[1] * cur_h + LINE_GAP
            continue
        # quebra automática na largura útil, como a impressora faz
        rows, row, width = [], [], 0
        for ch, s in segs:
            cw = (FONT_B if s["small"] else FONT_A)[0] * s["w"]
            if row and width + cw > printable:
                rows.append(row)
                row, width = [], 0
            row.append((ch, s))
            width += cw
        rows.append(row)
        for row in rows:
            row_w = sum((FONT_B if s["small"] else FONT_A)[0] * s["w"] for _, s in row)
            row_h = max((FONT_B if s["small"] else FONT_A)[1] * s["h"] for _, s in row)
            x = _x_for(align, row_w)
            for ch, s in row:
                g = _glyph(ch, s["bold"], s["small"], s["rev"], s["w"], s["h"])
                canvas.paste(g, (x, y + row_h - g.height))
                x += g.width
            y += row_h + LINE_GAP if sp is None else max(sp, row_h)
    return canvas.crop((0, 0, full, max(y + 10, 120)))


def ticket_bytes(model: str, data: dict, logo: bytes = b"", paper: str | None = None) -> bytes:
    """Mesmos comandos que print_ticket enviaria para o modelo informado."""
    if model == "thermal_classic":
        return tf.build_thermal_classic_bytes(data, logo, paper)
    if model in tf.RAW_LAYOUTS:
        return tf.build_layout_bytes(data, model, logo, paper)
    from escpos.printer import Dummy      # modelo padrão usa a python-escpos
    dummy = Dummy(profile="TM-T20II")
    tf.format_ticket(dummy, data, logo)
    return dummy.output


# ─── Amostra da conta (cabeçalho, rodapé e QR Code reais) ────────────────────
#
# O servidor não informa na conexão se a conta imprime QR Code. O agente
# aprende com o primeiro ticket recebido (ou com o servidor, se um dia ele
# enviar essa configuração na autenticação) e as prévias passam a usar esses
# dados. Fica em %APPDATA%\MeuAtendimento\ticket_sample.json.

def _sample_path() -> str:
    import config
    return os.path.join(config.get_config_dir(), SAMPLE_FILE)


def load_sample() -> dict | None:
    try:
        with open(_sample_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def save_sample(data: dict, source: str) -> tuple[dict, bool]:
    """Guarda o formato do ticket da conta. Retorna (amostra, mudou?)."""
    qr = data.get("qrcode")
    record = {
        "source": source,                                   # "ticket" ou "servidor"
        "header": str(data.get("header") or "")[:100],
        "footer": str(data.get("footer") or "")[:100],
        "services": str(data.get("services") or "")[:200],
        "has_qr": bool(qr),
        "qrcode": qr[:500] if isinstance(qr, str) else "",
    }
    old = load_sample() or {}
    # Serviço e conteúdo do QR mudam a cada senha: só o formato conta como mudança.
    changed = any(old.get(k) != record[k] for k in ("source", "header", "footer", "has_qr"))
    if changed:
        record["received_at"] = time.time()
        try:
            with open(_sample_path(), "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False)
        except OSError as e:
            logger.debug("Não foi possível salvar a amostra do ticket: %s", e)
        return record, True
    return old, False


def sample_info() -> dict:
    s = load_sample()
    if not s:
        return {"source": None, "has_qr": False}
    return {k: s.get(k) for k in ("source", "has_qr", "header", "footer", "received_at")}


def sample_data(with_qr: bool | None = None) -> dict:
    """Dados do exemplo: fictícios, completados com o formato real da conta."""
    data = dict(SAMPLE)
    s = load_sample()
    if s:
        for key in ("header", "footer", "services"):
            if s.get(key):
                data[key] = s[key]
    use_qr = with_qr if with_qr is not None else bool(s and s.get("has_qr"))
    if use_qr:
        data["qrcode"] = (s or {}).get("qrcode") or DEFAULT_QR
    data["created_date"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    return data


@lru_cache(maxsize=64)
def _preview_png(model: str, stamp: str, logo_version: str, with_qr: bool,
                 sample_version: str, paper: str) -> tuple[bytes, int, int]:
    import config
    import ticket_logo
    cfg = dict(config.load_config(), paper_width=paper)
    logo = ticket_logo.raster_bytes(cfg) if logo_version != "none" else b""
    img = render_bytes(ticket_bytes(model, sample_data(with_qr), logo, paper), paper)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue(), img.width, img.height


def preview_data_url(model: str, with_qr: bool | None = None, paper: str | None = None) -> dict:
    """PNG (data URL) do ticket de exemplo no modelo informado (logo e QR atuais)."""
    import config
    import ticket_logo
    sample = load_sample() or {}
    if with_qr is None:
        with_qr = bool(sample.get("has_qr"))
    stamp = datetime.now().strftime("%Y%m%d%H%M")      # a data do exemplo muda a cada minuto
    cfg = config.load_config()
    paper = str(paper or cfg.get("paper_width") or tf.DEFAULT_PAPER)
    if paper not in tf.PAPERS:
        paper = tf.DEFAULT_PAPER
    png, width, height = _preview_png(model, stamp, ticket_logo.version(dict(cfg, paper_width=paper)),
                                      bool(with_qr), str(sample.get("received_at", "none")), paper)
    return {
        "ok": True,
        "image": "data:image/png;base64," + base64.b64encode(png).decode("ascii"),
        "width": width,
        "height": height,
    }
