"""
Formata dados do ticket em comandos ESC/POS e sanitiza campos de entrada.
"""

import re
import logging

logger = logging.getLogger(__name__)

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

    # Header
    printer.set(align="center", bold=False, width=1, height=1)
    printer.textln(header)
    printer.textln("")

    # Código (destaque)
    printer.set(align="center", bold=True, width=2, height=2)
    printer.textln(f"Código: {code}")
    printer.textln("")

    # Serviços
    printer.set(align="center", bold=False, width=1, height=1)
    printer.textln(f"Serviços: {services}")
    printer.textln("")

    # Data
    printer.textln(f"Data: {created_date}")
    printer.textln("")

    # Footer
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
