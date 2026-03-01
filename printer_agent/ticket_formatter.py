"""
Formata dados do ticket em comandos ESC/POS e sanitiza campos de entrada.
Suporta dois modelos: padrão (escpos) e clássico térmico (raw ESC/POS 80mm).
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


def format_ticket(printer, data: dict) -> None:
    """
    Formata e envia um ticket para a impressora via ESC/POS.

    Args:
        printer: instância de escpos.printer (já conectada)
        data: dicionário com campos do ticket
    """
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


# Tamanho do módulo do QR no modelo clássico (1-16; maior = QR maior na impressora)
QR_MODULE_SIZE = 8


def _escpos_qrcode_bytes(data: str) -> bytes:
    """Gera bytes ESC/POS para imprimir QR code (dados sem acentos)."""
    data_clean = _remove_accents(data)
    try:
        data_encoded = data_clean.encode("cp860", errors="ignore")
    except Exception:
        data_encoded = data_clean.encode("utf-8", errors="ignore")
    pL = len(data_encoded) + 3
    pH = 0x00
    store_cmd = b"\x1D\x28\x6B" + bytes([pL & 0xFF, pH, 49, 80, 48]) + data_encoded
    size_byte = max(1, min(16, QR_MODULE_SIZE))
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


def format_ticket_thermal_classic(printer_name: str, data: dict) -> tuple[bool, str]:
    """
    Imprime ticket no modelo clássico térmico (80mm): SENHA em destaque primeiro,
    depois header, data, serviços, footer; opcionalmente QR code.
    Usa comandos ESC/POS brutos (cp860) e win32print.
    """
    if not WIN32PRINT_AVAILABLE:
        return False, "win32print não disponível"

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

    commands = b""
    commands += b"\x1B\x40"  # Initialize

    # SENHA em destaque (duplo tamanho, negrito, centralizado)
    commands += b"\x1B\x21\x30"  # Double height + width
    commands += b"\x1B\x45\x01"  # Bold
    commands += b"\x1B\x61\x01"  # Center
    commands += b"SENHA: " + enc(code) + b"\r\n"
    commands += b"\x1B\x21\x00"
    commands += b"\x1B\x45\x00"

    commands += b"\x1B\x61\x01"
    commands += (b"=" * 42) + b"\r\n"

    # Header (duplo, negrito, centralizado)
    if header:
        commands += b"\x1B\x21\x30"
        commands += b"\x1B\x45\x01"
        commands += b"\x1B\x61\x01"
        commands += enc(header) + b"\r\n"
        commands += b"\x1B\x21\x00"
        commands += b"\x1B\x45\x00"

    commands += b"\x1B\x61\x01"
    commands += (b"-" * 42) + b"\r\n"

    # Serviços (esquerda, negrito no label, quebra em 40 chars)
    commands += b"\x1B\x61\x00"  # Left
    commands += b"\x1B\x45\x01"
    commands += b"SERVICOS:\r\n"
    commands += b"\x1B\x45\x00"
    for line in _wrap_text(services, 40):
        commands += b" " + enc(line) + b"\r\n"
    commands += b"\r\n"

    if qrcode_data:
        commands += _escpos_qrcode_bytes(qrcode_data)
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

    if _send_escpos_raw(printer_name, commands):
        logger.info("Ticket impresso (modelo clássico, código: %s)", code)
        return True, "Ticket impresso com sucesso"
    return False, "Falha ao enviar para impressora"
