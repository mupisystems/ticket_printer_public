"""
Serviço de impressão: descoberta de impressoras Windows e impressão via ESC/POS.
"""

import logging
from escpos.printer import Win32Raw
from ticket_formatter import format_ticket, validate_print_data

logger = logging.getLogger(__name__)

try:
    import win32print
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    logger.warning("win32print não disponível — descoberta de impressoras desabilitada")


def list_printers() -> list[str]:
    if not WIN32_AVAILABLE:
        return []
    try:
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        printers = win32print.EnumPrinters(flags, None, 2)
        return [p["pPrinterName"] for p in printers]
    except Exception as e:
        logger.error("Erro ao listar impressoras: %s", e)
        return []


def _get_printer(printer_name: str) -> Win32Raw:
    return Win32Raw(printer_name, profile="TM-T20II")


def print_ticket(printer_name: str, data: dict) -> tuple[bool, str]:
    """
    Imprime um ticket na impressora especificada.

    Returns:
        (success, message)
    """
    valid, error = validate_print_data(data)
    if not valid:
        logger.warning("Dados de impressão inválidos: %s", error)
        return False, error

    try:
        printer = _get_printer(printer_name)
    except Exception as e:
        msg = f"Erro ao conectar à impressora '{printer_name}': {e}"
        logger.error(msg)
        return False, msg

    try:
        format_ticket(printer, data)
        printer.close()
        logger.info("Ticket impresso com sucesso (código: %s)", data.get("code", "?"))
        return True, "Ticket impresso com sucesso"
    except Exception as e:
        msg = f"Erro ao imprimir: {e}"
        logger.error(msg)
        try:
            printer.close()
        except Exception:
            pass
        return False, msg


def test_print(printer_name: str) -> tuple[bool, str]:
    test_data = {
        "header": "=== TESTE DE IMPRESSÃO ===",
        "code": "T001",
        "services": "Teste",
        "created_date": "2024-01-01 00:00",
        "footer": "Impressão de teste OK",
    }
    return print_ticket(printer_name, test_data)
