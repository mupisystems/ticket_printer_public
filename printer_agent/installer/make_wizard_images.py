"""
Gera as imagens do assistente de instalacao (Inno Setup 6, WizardStyle=modern)
no estilo da marca (indigo #334398 -> #243080).

Saida em installer/assets/ (pasta gerada, fora do git):
  wizard-large-<L>x<A>.bmp  -> WizardImageFile      (lateral das paginas Boas-vindas/Concluido)
  wizard-small-<N>.bmp      -> WizardSmallImageFile (canto superior direito das demais paginas)

Um arquivo por escala de DPI (100% a 250%), nos tamanhos de area recomendados
pela documentacao do Inno Setup 6.6+; o Setup escolhe o que melhor se ajusta.
Todos sao BMP 24 bits (sem canal alfa).

Uso (na pasta printer_agent):
  python installer\\make_wizard_images.py [--preview arquivo.png]
"""

from __future__ import annotations

import argparse
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # pasta printer_agent
ASSETS_DIR = os.path.join(HERE, "assets")
LOGO_PATH = os.path.join(ROOT, "logo.png")

# Area da imagem no Inno Setup 6.6+ (fonte, WizardSizePercent e
# WizardKeepAspectRatio padrao) para 100/125/150/175/200/225/250% de DPI.
LARGE_SIZES = [(202, 386), (269, 515), (336, 643), (403, 772), (430, 824), (498, 953), (534, 1022)]
SMALL_SIZES = [58, 77, 97, 116, 124, 143, 159]

BRAND = (0x33, 0x43, 0x98)
BRAND_DARK = (0x24, 0x30, 0x80)
BRAND_DEEP = (0x1A, 0x23, 0x63)
WHITE = (255, 255, 255)
PAPER_SHADE = (0xE6, 0xE9, 0xF5)
BODY_LIGHT = (0xF4, 0xF6, 0xFC)
BODY_SHADE = (0xD9, 0xDE, 0xF0)
INK_GREY = (0xB4, 0xBB, 0xD8)
LED_GREEN = (0x34, 0xD3, 0x99)
HEADER_BG = WHITE  # fundo do cabecalho do assistente "modern" (tema claro)

SS_LARGE = 3  # supersampling (desenha maior e reduz com LANCZOS)
SS_SMALL = 8

FONTS_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


# --------------------------------------------------------------------------- utilitarios

def load_font(candidates: tuple[str, ...], size: int) -> ImageFont.ImageFont:
    for name in candidates:
        path = os.path.join(FONTS_DIR, name)
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def font_bold(size: int):
    return load_font(("segoeuib.ttf", "seguisb.ttf", "arialbd.ttf"), size)


def font_semibold(size: int):
    return load_font(("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"), size)


def font_regular(size: int):
    return load_font(("segoeui.ttf", "arial.ttf"), size)


def rgba(color: tuple[int, int, int], alpha: float) -> tuple[int, int, int, int]:
    return (*color, max(0, min(255, round(alpha * 255))))


def new_layer(size: tuple[int, int]) -> Image.Image:
    return Image.new("RGBA", size, (0, 0, 0, 0))


def composite(base: Image.Image, layer: Image.Image) -> Image.Image:
    return Image.alpha_composite(base, layer)


def gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int],
             diagonal: float = 0.3) -> Image.Image:
    """Degrade top->bottom com leve componente horizontal (diagonal 0..1)."""
    w, h = size
    vert = Image.linear_gradient("L").resize((w, h), Image.BILINEAR)
    horiz = Image.linear_gradient("L").rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
    horiz = horiz.resize((w, h), Image.BILINEAR)
    mask = Image.blend(vert, horiz, diagonal)
    return Image.composite(Image.new("RGBA", size, (*bottom, 255)), Image.new("RGBA", size, (*top, 255)), mask)


def white_logo(height_px: int) -> Image.Image | None:
    """Logo da marca recolorido para branco (usa so o alfa do logo.png)."""
    if not os.path.isfile(LOGO_PATH):
        return None
    logo = Image.open(LOGO_PATH).convert("RGBA")
    logo = logo.crop(logo.getchannel("A").getbbox())
    w = round(logo.width * height_px / logo.height)
    alpha = logo.getchannel("A").resize((w, height_px), Image.LANCZOS)
    out = Image.new("RGBA", (w, height_px), (*WHITE, 0))
    out.putalpha(alpha)
    return out


def dither(img: Image.Image, sigma: float = 1.6) -> Image.Image:
    """Ruido muito leve para evitar faixas (banding) no degrade em 24 bits."""
    noise = Image.effect_noise(img.size, sigma).convert("RGB")
    return ImageChops.add(img, noise, scale=1.0, offset=-128)


# --------------------------------------------------------------------------- ilustracao

def zigzag_top(x0: float, x1: float, y: float, teeth: int, depth: float) -> list[tuple[float, float]]:
    step = (x1 - x0) / teeth
    pts = []
    for i in range(teeth + 1):
        pts.append((x0 + i * step, y))
        if i < teeth:
            pts.append((x0 + i * step + step / 2, y - depth))
    return pts


def draw_printer(layer: Image.Image, x0: float, y0: float, u: float, ticket_h: float,
                 detailed: bool, number_font=None, label_font=None,
                 palette: str = "light") -> None:
    """
    Impressora termica vista de frente, com a senha saindo pela fenda superior.
    (x0, y0) = canto superior esquerdo do corpo; u = pixels por unidade
    (corpo = 100 x 46 unidades); ticket_h = altura do ticket acima do corpo (unidades).
    """
    d = ImageDraw.Draw(layer)

    def R(x, y, x2, y2):
        return (x0 + x * u, y0 + y * u, x0 + x2 * u, y0 + y2 * u)

    def P(x, y):
        return (x0 + x * u, y0 + y * u)

    if palette == "light":
        body, shade, slot, paper, ink = BODY_LIGHT, BODY_SHADE, BRAND_DEEP, WHITE, BRAND
    else:  # glifo em uma cor (para fundo claro)
        body, shade, slot, paper, ink = BRAND, BRAND_DARK, BRAND_DEEP, WHITE, BRAND

    # --- ticket (desenhado antes do corpo: sai "de dentro" da impressora)
    tx0, tx1 = 19, 81
    ttop = -ticket_h
    teeth = 7 if detailed else 5
    tooth = 3.2 if detailed else 4.2
    outline = [(tx0, 4), (tx0, ttop)] + zigzag_top(tx0, tx1, ttop, teeth, -tooth)[1:-1] + [(tx1, ttop), (tx1, 4)]
    d.polygon([P(x, y) for x, y in outline], fill=paper)

    if detailed:
        # leve sombra na base do papel, perto da fenda
        d.rectangle(R(tx0, -7, tx1, 2), fill=PAPER_SHADE)
        cx = (tx0 + tx1) / 2
        if label_font is not None:
            d.text(P(cx, ttop + 11), "SENHA", font=label_font, fill=INK_GREY, anchor="mm")
        if number_font is not None:
            d.text(P(cx, ttop + 27), "A042", font=number_font, fill=ink, anchor="mm")
        # separador tracejado
        y = ttop + 41
        x = tx0 + 7
        while x < tx1 - 7:
            d.rounded_rectangle(R(x, y, min(x + 3.4, tx1 - 7), y + 1.4), radius=0.7 * u, fill=INK_GREY)
            x += 5.6
        # linhas de texto
        for i, (a, b) in enumerate(((27, 73), (32, 68))):
            yy = y + 7 + i * 6.5
            if yy + 2.4 < -9:
                d.rounded_rectangle(R(a, yy, b, yy + 2.4), radius=1.2 * u, fill=PAPER_SHADE)
    else:
        # glifo simplificado: 3 linhas no ticket
        lines = ((29, 71), (29, 63), (29, 67))
        for i, (a, b) in enumerate(lines):
            yy = ttop + 10 + i * 9
            if yy + 4.5 < 0:
                d.rounded_rectangle(R(a, yy, b, yy + 4.5), radius=2.25 * u, fill=ink)

    # --- corpo
    d.rounded_rectangle(R(0, 0, 100, 46), radius=11 * u, fill=body)
    # faixa inferior (base) mais escura
    base = new_layer(layer.size)
    bd = ImageDraw.Draw(base)
    bd.rounded_rectangle(R(0, 0, 100, 46), radius=11 * u, fill=shade)
    cut = Image.new("L", layer.size, 0)
    ImageDraw.Draw(cut).rectangle(R(-1, 34, 101, 47), fill=255)
    base.putalpha(ImageChops.multiply(base.getchannel("A"), cut))
    layer.alpha_composite(base)
    d = ImageDraw.Draw(layer)

    # fenda de saida do papel
    d.rounded_rectangle(R(13, 3.2, 87, 8.2), radius=2.5 * u, fill=slot)

    if detailed:
        # botoes e LED de status
        d.rounded_rectangle(R(12, 20, 30, 24.5), radius=2.25 * u, fill=BODY_SHADE)
        d.rounded_rectangle(R(34, 20, 44, 24.5), radius=2.25 * u, fill=BODY_SHADE)
        d.ellipse(R(80, 18.6, 87.4, 26), fill=LED_GREEN)
    else:
        d.ellipse(R(78, 17, 88, 27), fill=LED_GREEN if palette == "light" else WHITE)


# --------------------------------------------------------------------------- imagem grande

def render_large(w: int, h: int) -> Image.Image:
    ss = SS_LARGE
    W, H = w * ss, h * ss
    k = W / 202.0  # escala relativa ao tamanho de 100%

    img = gradient((W, H), BRAND, BRAND_DARK, diagonal=0.28)

    # formas sutis ao fundo
    shapes = new_layer((W, H))
    sd = ImageDraw.Draw(shapes)
    sd.ellipse((W * 0.42, -H * 0.20, W * 1.55, H * 0.39), fill=rgba(WHITE, 0.055))
    sd.ellipse((-W * 0.70, H * 0.60, W * 0.55, H * 1.25), fill=rgba(WHITE, 0.045))
    img = composite(img, shapes)

    ring = new_layer((W, H))
    rd = ImageDraw.Draw(ring)
    rd.ellipse((W * 0.62, H * 0.70, W * 1.30, H * 1.06), outline=rgba(WHITE, 0.10), width=max(2, round(3 * k)))
    rd.ellipse((-W * 0.20, H * 0.235, W * 0.16, H * 0.424), outline=rgba(WHITE, 0.08), width=max(2, round(2 * k)))
    img = composite(img, ring)

    # grade de pontos discreta
    dots = new_layer((W, H))
    dd = ImageDraw.Draw(dots)
    r = 1.15 * k
    for row in range(4):
        for col in range(5):
            cx = W * 0.735 + col * 9 * k
            cy = H * 0.262 + row * 9 * k
            dd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rgba(WHITE, 0.22))
    img = composite(img, dots)

    # logo branco
    logo = white_logo(round(34 * k))
    if logo is not None:
        img.alpha_composite(logo, (round((W - logo.width) / 2), round(H * 0.085)))

    # ilustracao da impressora
    u = 1.18 * k
    pw = 100 * u
    px0 = (W - pw) / 2
    py0 = H * 0.585

    glow = new_layer((W, H))
    gd = ImageDraw.Draw(glow)
    gcx, gcy, gr = W / 2, py0 - 12 * u, 78 * k
    gd.ellipse((gcx - gr, gcy - gr, gcx + gr, gcy + gr), fill=rgba(WHITE, 0.13))
    glow = glow.filter(ImageFilter.GaussianBlur(26 * k))
    img = composite(img, glow)

    shadow = new_layer((W, H))
    shd = ImageDraw.Draw(shadow)
    shd.ellipse((px0 + 2 * u, py0 + 40 * u, px0 + 98 * u, py0 + 56 * u), fill=rgba(BRAND_DEEP, 0.55))
    shadow = shadow.filter(ImageFilter.GaussianBlur(5 * k))
    img = composite(img, shadow)

    art = new_layer((W, H))
    draw_printer(art, px0, py0, u, ticket_h=72, detailed=True,
                 number_font=font_bold(round(17.5 * u)), label_font=font_semibold(round(6.2 * u)))
    img = composite(img, art)

    # textos
    td = ImageDraw.Draw(img)
    td.text((W / 2, H * 0.835), "Agente de Impressão", font=font_semibold(round(16.5 * k)),
            fill=WHITE, anchor="mm")
    td.text((W / 2, H * 0.885), "Meu Atendimento Virtual", font=font_regular(round(11 * k)),
            fill=rgba(WHITE, 0.72), anchor="mm")

    out = img.convert("RGB").resize((w, h), Image.LANCZOS)
    return dither(out)


# --------------------------------------------------------------------------- imagem pequena

def render_small(s: int) -> Image.Image:
    ss = SS_SMALL
    S = s * ss
    img = Image.new("RGBA", (S, S), (*HEADER_BG, 255))

    inset = S * 0.055
    radius = S * 0.23
    tile_box = (inset, inset, S - inset, S - inset)

    # sombra suave do bloco
    shadow = new_layer((S, S))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (tile_box[0], tile_box[1] + S * 0.025, tile_box[2], tile_box[3] + S * 0.025),
        radius=radius, fill=rgba(BRAND_DEEP, 0.28))
    shadow = shadow.filter(ImageFilter.GaussianBlur(S * 0.022))
    img = composite(img, shadow)

    # bloco indigo com degrade
    tile = gradient((S, S), BRAND, BRAND_DARK, diagonal=0.35)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle(tile_box, radius=radius, fill=255)
    img.paste(tile, (0, 0), mask)

    # brilho sutil no canto superior
    shine = new_layer((S, S))
    ImageDraw.Draw(shine).ellipse((S * 0.30, -S * 0.55, S * 1.35, S * 0.42), fill=rgba(WHITE, 0.09))
    shine.putalpha(ImageChops.multiply(shine.getchannel("A"), mask))
    img = composite(img, shine)

    # glifo da impressora em branco
    art = new_layer((S, S))
    u = S * 0.0061
    ticket_h = 36
    total_h = (ticket_h + 46) * u
    px0 = (S - 100 * u) / 2
    py0 = (S - total_h) / 2 + ticket_h * u + S * 0.01
    draw_printer(art, px0, py0, u, ticket_h=ticket_h, detailed=False, palette="light")
    img = composite(img, art)

    return img.convert("RGB").resize((s, s), Image.LANCZOS)


# --------------------------------------------------------------------------- main

def build_preview(larges: list[Image.Image], smalls: list[Image.Image]) -> Image.Image:
    """Folha de contato: imagens grandes lado a lado + simulacao do cabecalho."""
    pad = 16
    hmax = max(i.height for i in larges)
    width = max(sum(i.width for i in larges), sum(i.width * 4 for i in smalls)) + pad * (len(larges) + 1)
    sm_h = max(i.height for i in smalls) + 2 * pad
    sheet = Image.new("RGB", (width, hmax + 2 * pad + sm_h + 90), (236, 238, 244))
    x = pad
    for im in larges:
        sheet.paste(im, (x, pad))
        x += im.width + pad
    # cabecalho simulado (fundo branco, imagem pequena a direita)
    y = hmax + 2 * pad
    x = pad
    for im in smalls:
        header = Image.new("RGB", (im.width * 4, im.height + 16), WHITE)
        header.paste(im, (header.width - im.width - 8, 8))
        sheet.paste(header, (x, y))
        x += header.width + pad
    return sheet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=ASSETS_DIR, help="pasta de saida (padrao: installer/assets)")
    parser.add_argument("--preview", help="salva tambem uma folha de contato PNG neste caminho")
    args = parser.parse_args()

    if not os.path.isfile(LOGO_PATH):
        print(f"AVISO: logo nao encontrado em {LOGO_PATH}; imagem grande sera gerada sem logo.", file=sys.stderr)

    os.makedirs(args.out, exist_ok=True)
    larges, smalls = [], []
    for w, h in LARGE_SIZES:
        im = render_large(w, h)
        im.save(os.path.join(args.out, f"wizard-large-{w}x{h}.bmp"), format="BMP")
        larges.append(im)
    for s in SMALL_SIZES:
        im = render_small(s)
        im.save(os.path.join(args.out, f"wizard-small-{s}.bmp"), format="BMP")
        smalls.append(im)

    if args.preview:
        build_preview(larges, smalls).save(args.preview)
        print(f"Previa: {args.preview}")

    print(f"OK: {len(larges)} imagens grandes e {len(smalls)} pequenas em {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
