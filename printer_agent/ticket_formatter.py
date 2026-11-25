"""
Formata dados do ticket em comandos ESC/POS e sanitiza campos de entrada.
Modelos: padrão/reduzido (escpos), clássico térmico (raw ESC/POS 80mm) e os
extras compacto, senha gigante, faixa escura e moldura (raw, RAW_LAYOUTS).
"""

import re
import logging
import unicodedata

logger = logging.getLogger(__name__)

try:
    import win32print
    WIN32PRINT_AVAILABLE = True
except ImportError:
    WIN32PRINT_AVAILABLE = False

# Limites de comprimento por campo
FIELD_LIMITS = {
    "header": 100,
    "code": 50,
    "services": 200,
    "created_date": 50,
    "footer": 100,
    "qrcode": 500,
}

# Campos obrigatórios em uma mensagem de impressão
REQUIRED_FIELDS = {"created_date", "code", "services", "header", "footer"}

# Regex para caracteres de controle (0x00-0x1F exceto \n \r \t)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitize_field(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        value = str(value)
    value = _CONTROL_CHARS.sub("", value)
    limit = FIELD_LIMITS.get(field_name, 200)
    return value[:limit]


def validate_print_data(data: dict) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "Dados de impressão devem ser um dicionário"
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        return False, f"Campos obrigatórios ausentes: {', '.join(sorted(missing))}"
    for field in REQUIRED_FIELDS:
        if not isinstance(data[field], str):
            return False, f"Campo '{field}' deve ser string"
    return True, ""


def format_ticket(printer, data: dict, logo: bytes = b"") -> None:
    """
    Formata e envia um ticket para a impressora via ESC/POS.

    Args:
        printer: instância de escpos.printer (já conectada)
        data: dicionário com campos do ticket
        logo: comandos ESC/POS do logo (ticket_logo.raster_bytes), opcional
    """
    if logo:
        printer._raw(logo)
    header = sanitize_field(data["header"], "header")
    code = sanitize_field(data["code"], "code")
    services = sanitize_field(data["services"], "services")
    created_date = sanitize_field(data["created_date"], "created_date")
    footer = sanitize_field(data["footer"], "footer")
    qrcode_data = data.get("qrcode")

    # Modelo reduzido: texto bem grande (3x3; máx. comum em térmicas)
    # Header
    printer.set(align="center", bold=False, width=3, height=3)
    printer.textln(header)
    printer.textln("")

    # Código (destaque)
    printer.set(align="center", bold=True, width=3, height=3)
    printer.textln(f"Código: {code}")
    printer.textln("")

    # Serviços
    printer.set(align="center", bold=False, width=3, height=3)
    printer.textln(f"Serviços: {services}")
    printer.textln("")

    # Data
    printer.set(align="center", bold=False, width=3, height=3)
    printer.textln(f"Data: {created_date}")
    printer.textln("")

    # Footer
    printer.set(align="center", bold=False, width=3, height=3)
    printer.textln(footer)
    printer.textln("")

    # QR Code (se presente)
    if qrcode_data:
        qrcode_data = sanitize_field(qrcode_data, "qrcode")
        printer.set(align="center")
        printer.qr(qrcode_data, size=6)
        printer.textln("")

    # Corte de papel
    printer.cut()


# --- Modelo clássico térmico (SENHA primeiro, 80mm, raw ESC/POS) ---

def _remove_accents(text: str) -> str:
    """Remove acentos para compatibilidade com impressoras térmicas (cp860)."""
    if not text:
        return text
    try:
        nfd = unicodedata.normalize("NFD", text)
        return "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    except Exception:
        return text


def _send_escpos_raw(printer_name: str, commands: bytes) -> bool:
    """Envia comandos ESC/POS brutos para a impressora via win32print."""
    if not WIN32PRINT_AVAILABLE:
        logger.error("win32print não disponível — modelo clássico não suportado")
        return False
    try:
        hprinter = win32print.OpenPrinter(printer_name)
        try:
            win32print.StartDocPrinter(hprinter, 1, ("ESCPOS Print", None, "RAW"))
            win32print.StartPagePrinter(hprinter)
            win32print.WritePrinter(hprinter, commands)
            win32print.EndPagePrinter(hprinter)
            win32print.EndDocPrinter(hprinter)
            return True
        finally:
            win32print.ClosePrinter(hprinter)
    except Exception as e:
        logger.error("Erro ao enviar ESC/POS: %s", e)
        return False


# Largura da bobina: colunas usadas pelos modelos (fonte A), colunas da fonte
# menor (B) e pontos imprimíveis. Em 80 mm cabem 48 colunas; os modelos usam 42.
PAPERS = {
    "80": {"cols": 42, "small_cols": 56, "dots": 576},
    "58": {"cols": 32, "small_cols": 42, "dots": 384},
}
DEFAULT_PAPER = "80"


def paper_info(paper: str | None) -> dict:
    return PAPERS.get(str(paper or DEFAULT_PAPER), PAPERS[DEFAULT_PAPER])


# Tamanho do módulo do QR no modelo clássico (1-16; maior = QR maior na impressora)
QR_MODULE_SIZE = 8


def _qr_module_size(data: bytes, dots: int) -> int:
    """Maior módulo (até QR_MODULE_SIZE) em que o QR cabe na largura da bobina."""
    try:
        import qrcode
        code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0)
        code.add_data(data)
        code.make(fit=True)
        fits = dots // code.modules_count
    except Exception:
        fits = QR_MODULE_SIZE if dots >= PAPERS["80"]["dots"] else 5
    return max(1, min(16, QR_MODULE_SIZE, fits))


def _escpos_qrcode_bytes(data: str, paper: str | None = None) -> bytes:
    """Gera bytes ESC/POS para imprimir QR code (dados sem acentos)."""
    data_clean = _remove_accents(data)
    try:
        data_encoded = data_clean.encode("cp860", errors="ignore")
    except Exception:
        data_encoded = data_clean.encode("utf-8", errors="ignore")
    length = len(data_encoded) + 3
    store_cmd = b"\x1D\x28\x6B" + bytes([length & 0xFF, length >> 8, 49, 80, 48]) + data_encoded
    size_byte = _qr_module_size(data_encoded, paper_info(paper)["dots"])
    return (
        b"\x1B\x61\x01"  # Center
        + b"\x1D\x28\x6B\x03\x00\x31\x43" + bytes([size_byte])  # QR module size (maior = QR maior)
        + b"\x1D\x28\x6B\x03\x00\x31\x45\x31"  # Error correction L
        + store_cmd
        + b"\x1D\x28\x6B\x03\x00\x31\x51\x30"  # Print QR
    )


def _wrap_text(text: str, line_chars: int = 40) -> list[str]:
    """Quebra texto em linhas de no máximo line_chars caracteres."""
    words = _remove_accents(text).split()
    lines = []
    line = ""
    for word in words:
        if len(line + " " + word) <= line_chars:
            line = (line + " " + word).strip() if line else word
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def build_thermal_classic_bytes(data: dict, logo: bytes = b"", paper: str | None = None) -> bytes:
    """
    Comandos do modelo clássico térmico (80 ou 58 mm): SENHA em destaque primeiro,
    depois header, data, serviços, footer; opcionalmente QR code.
    ESC/POS bruto (cp860), sem acentos.
    """
    header = sanitize_field(data["header"], "header")
    code = sanitize_field(data["code"], "code")
    services = sanitize_field(data["services"], "services")
    created_date = sanitize_field(data["created_date"], "created_date")
    footer = sanitize_field(data["footer"], "footer")
    qrcode_data = data.get("qrcode")
    if qrcode_data:
        qrcode_data = sanitize_field(qrcode_data, "qrcode")

    def enc(s: str) -> bytes:
        try:
            return _remove_accents(s).encode("cp860", errors="ignore")
        except Exception:
            return _remove_accents(s).encode("utf-8", errors="ignore")

    cols = paper_info(paper)["cols"]
    commands = b""
    commands += b"\x1B\x40"  # Initialize
    commands += logo         # logo opcional no topo

    # SENHA em destaque (duplo tamanho, negrito, centralizado)
    commands += b"\x1B\x21\x30"  # Double height + width
    commands += b"\x1B\x45\x01"  # Bold
    commands += b"\x1B\x61\x01"  # Center
    commands += b"SENHA: " + enc(code) + b"\r\n"
    commands += b"\x1B\x21\x00"
    commands += b"\x1B\x45\x00"

    commands += b"\x1B\x61\x01"
    commands += (b"=" * cols) + b"\r\n"

    # Header (duplo, negrito, centralizado)
    if header:
        commands += b"\x1B\x21\x30"
        commands += b"\x1B\x45\x01"
        commands += b"\x1B\x61\x01"
        commands += enc(header) + b"\r\n"
        commands += b"\x1B\x21\x00"
        commands += b"\x1B\x45\x00"

    commands += b"\x1B\x61\x01"
    commands += (b"-" * cols) + b"\r\n"

    # Serviços (esquerda, negrito no label, com quebra de linha)
    commands += b"\x1B\x61\x00"  # Left
    commands += b"\x1B\x45\x01"
    commands += b"SERVICOS:\r\n"
    commands += b"\x1B\x45\x00"
    for line in _wrap_text(services, cols - 2):
        commands += b" " + enc(line) + b"\r\n"
    commands += b"\r\n"

    if qrcode_data:
        commands += _escpos_qrcode_bytes(qrcode_data, paper)
        commands += b"\r\n\r\n"

    if footer:
        commands += b"\x1B\x61\x01"
        commands += b"\x1B\x34"  # Italic
        commands += enc(footer) + b"\r\n"
        commands += b"\x1B\x35"

    # Data/hora no final (centralizado)
    commands += b"\r\n"
    commands += b"\x1B\x61\x01"
    commands += b"Data: " + enc(created_date) + b"\r\n"

    commands += b"\r\n\r\n\r\n\r\n\r\n"
    if qrcode_data:
        commands += b"\r\n\r\n\r\n"
    commands += b"\x1D\x56\x01"  # Partial cut
    return commands


def format_ticket_thermal_classic(printer_name: str, data: dict, logo: bytes = b"",
                                  paper: str | None = None) -> tuple[bool, str]:
    """Imprime o ticket no modelo clássico térmico via win32print."""
    if not WIN32PRINT_AVAILABLE:
        return False, "win32print não disponível"

    commands = build_thermal_classic_bytes(data, logo, paper)
    code = sanitize_field(data["code"], "code")
    if _send_escpos_raw(printer_name, commands):
        logger.info("Ticket impresso (modelo clássico, código: %s)", code)
        return True, "Ticket impresso com sucesso"
    return False, "Falha ao enviar para impressora"


# --- Modelos extras (ESC/POS bruto, 80 ou 58 mm) ---------------------------
#
# compact     — texto menor e sem espaços sobrando (economiza papel)
# big_number  — senha enorme, para ler de longe
# inverted    — faixas escuras (impressão invertida) no topo e no rodapé
# framed      — informações dentro de uma moldura de traços
#
# Em 80 mm usam 42 colunas (mesma régua do modelo clássico, cabe com folga nas
# 48 da impressora); em 58 mm, as 32 disponíveis. Ver PAPERS.


def _enc(text: str) -> bytes:
    try:
        return _remove_accents(text).encode("cp860", errors="ignore")
    except Exception:
        return _remove_accents(text).encode("utf-8", errors="ignore")


def _fit_size(text: str, max_size: int, cols: int) -> int:
    """Maior ampliação (1..max_size) em que o texto cabe numa linha."""
    size = max_size
    while size > 1 and len(text) * size > cols:
        size -= 1
    return size


class _EscPos:
    """Montador simples de comandos ESC/POS (texto sem acentos, cp860)."""

    def __init__(self, paper: str | None = None) -> None:
        self.buf = bytearray(b"\x1B\x40")                     # inicializa
        self.paper = paper
        info = paper_info(paper)
        self.cols, self.small_cols = info["cols"], info["small_cols"]

    def align(self, where: str) -> "_EscPos":
        self.buf += b"\x1B\x61" + bytes([{"left": 0, "center": 1, "right": 2}[where]])
        return self

    def bold(self, on: bool = True) -> "_EscPos":
        self.buf += b"\x1B\x45" + bytes([1 if on else 0])
        return self

    def size(self, width: int = 1, height: int = 1) -> "_EscPos":
        self.buf += b"\x1D\x21" + bytes([((width - 1) << 4) | (height - 1)])
        return self

    def reverse(self, on: bool = True) -> "_EscPos":
        self.buf += b"\x1D\x42" + bytes([1 if on else 0])    # branco sobre preto
        return self

    def small(self, on: bool = True) -> "_EscPos":
        self.buf += b"\x1B\x4D" + bytes([1 if on else 0])    # fonte B (menor)
        return self

    def spacing(self, dots: int | None = None) -> "_EscPos":
        """Espaço entre linhas em pontos (None = padrão da impressora)."""
        self.buf += b"\x1B\x32" if dots is None else b"\x1B\x33" + bytes([dots])
        return self

    def text(self, text: str) -> "_EscPos":
        self.buf += _enc(text)
        return self

    def line(self, text: str = "") -> "_EscPos":
        self.buf += _enc(text) + b"\r\n"
        return self

    def lines(self, text: str, width: int | None = None) -> "_EscPos":
        for part in _wrap_text(text, width or self.cols) or [""]:
            self.line(part)
        return self

    def rule(self, char: str = "-") -> "_EscPos":
        return self.line(char * self.cols)

    def feed(self, n: int = 1) -> "_EscPos":
        self.buf += b"\r\n" * n
        return self

    def qr(self, data: str) -> "_EscPos":
        self.buf += _escpos_qrcode_bytes(data, self.paper) + b"\r\n"
        return self

    def cut(self, feed: int = 5) -> "_EscPos":
        self.feed(feed)                                        # leva o papel até a guilhotina
        self.buf += b"\x1D\x56\x01"                            # corte parcial
        return self

    def build(self) -> bytes:
        return bytes(self.buf)


def _big_code(t: _EscPos, code: str, max_size: int) -> None:
    size = _fit_size(code, max_size, t.cols)
    t.size(size, size).bold().line(code).bold(False).size(1, 1)


def _layout_compact(t: _EscPos, f: dict) -> None:
    t.align("center")
    if f["header"]:
        t.bold().lines(f["header"]).bold(False)
    label = f"SENHA {f['code']}"
    if len(label) * 2 > t.cols:
        label = f["code"]
    _big_code(t, label, 2)
    t.lines(f"{f['services']} - {f['created_date']}")
    if f["footer"]:
        t.small().lines(f["footer"], t.small_cols).small(False)
    if f["qrcode"]:
        t.qr(f["qrcode"])
    t.cut(feed=4)


def _layout_big_number(t: _EscPos, f: dict) -> None:
    t.align("center")
    if f["header"]:
        t.bold().lines(f["header"]).bold(False).feed(1)
    t.line("SUA SENHA")
    _big_code(t, f["code"], 5)
    t.feed(1).rule("-")
    t.size(1, 2).lines(f["services"]).size(1, 1)
    t.line(f["created_date"])
    if f["footer"]:
        t.feed(1).lines(f["footer"])
    if f["qrcode"]:
        t.feed(1).qr(f["qrcode"])
    t.cut()


def _band(t: _EscPos, text: str, tall: bool = True) -> None:
    """Faixa escura de largura total com o texto centralizado em branco."""
    height = 2 if tall else 1
    t.spacing(24 * height)            # linhas coladas: a faixa fica contínua
    for part in _wrap_text(text, t.cols - 4) or [""]:
        t.reverse().bold().size(1, height)
        t.line(part.center(t.cols))
        t.size(1, 1).bold(False).reverse(False)
    t.spacing(None)


def _layout_inverted(t: _EscPos, f: dict) -> None:
    t.align("center")
    _band(t, f["header"] or "ATENDIMENTO")
    t.feed(1).line("SENHA")
    _big_code(t, f["code"], 3)
    t.feed(1).align("left")
    t.bold().text("Servico: ").bold(False)
    if len("Servico: ") + len(f["services"]) <= t.cols or t.paper in (None, "80"):
        t.line(_remove_accents(f["services"]))
    else:
        t.line().lines(f["services"])
    t.bold().text("Data: ").bold(False).line(f["created_date"])
    t.align("center").feed(1)
    if f["footer"]:
        _band(t, f["footer"], tall=False)
    if f["qrcode"]:
        t.feed(1).qr(f["qrcode"])
    t.cut()


def _framed(t: _EscPos, text: str, align: str = "center") -> None:
    inner = t.cols - 4
    for part in _wrap_text(text, inner) or [""]:
        body = part.center(inner) if align == "center" else part.ljust(inner)
        t.line(f"| {body} |")


def _layout_framed(t: _EscPos, f: dict) -> None:
    strong = "+" + "=" * (t.cols - 2) + "+"
    light = "+" + "-" * (t.cols - 2) + "+"
    t.align("center").line(strong).bold()
    _framed(t, f["header"] or "ATENDIMENTO")
    t.bold(False).line(strong)
    t.feed(1).line("SENHA")
    _big_code(t, f["code"], 3)
    t.feed(1).line(light)
    _framed(t, f"Servico: {f['services']}", align="left")
    _framed(t, f"Data: {f['created_date']}", align="left")
    t.line(light)
    if f["footer"]:
        t.feed(1).lines(f["footer"])
    if f["qrcode"]:
        t.feed(1).qr(f["qrcode"])
    t.cut()


RAW_LAYOUTS = {
    "compact": _layout_compact,
    "big_number": _layout_big_number,
    "inverted": _layout_inverted,
    "framed": _layout_framed,
}


def build_layout_bytes(data: dict, model: str, logo: bytes = b"",
                       paper: str | None = None) -> bytes:
    """Gera os comandos ESC/POS de um modelo extra (sem enviar à impressora)."""
    fields = {name: sanitize_field(data[name], name)
              for name in ("header", "code", "services", "created_date", "footer")}
    qrcode_data = data.get("qrcode")
    fields["qrcode"] = sanitize_field(qrcode_data, "qrcode") if qrcode_data else ""
    ticket = _EscPos(paper)
    ticket.buf += logo                                     # logo opcional no topo
    RAW_LAYOUTS[model](ticket, fields)
    return ticket.build()


def format_ticket_layout(printer_name: str, data: dict, model: str, logo: bytes = b"",
                         paper: str | None = None) -> tuple[bool, str]:
    """Imprime o ticket num dos modelos extras (RAW_LAYOUTS)."""
    if not WIN32PRINT_AVAILABLE:
        return False, "win32print não disponível"
    commands = build_layout_bytes(data, model, logo, paper)
    if _send_escpos_raw(printer_name, commands):
        logger.info("Ticket impresso (modelo %s, código: %s)", model, data.get("code", "?"))
        return True, "Ticket impresso com sucesso"
    return False, "Falha ao enviar para impressora"
