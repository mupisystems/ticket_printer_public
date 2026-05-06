"""
Serviço de impressão: descoberta de impressoras Windows e impressão via ESC/POS.
Suporta dois modelos de comprovante: padrão e clássico térmico (80mm).
"""

import logging
import time
import config
from escpos.printer import Win32Raw
from ticket_formatter import (
    format_ticket,
    format_ticket_thermal_classic,
    validate_print_data,
)

logger = logging.getLogger(__name__)

try:
    import win32print
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    logger.warning("win32print não disponível — descoberta de impressoras desabilitada")


def _check_printer_status(printer_name: str) -> tuple[bool, str]:
    """Verifica se a impressora está pronta via GetPrinter. Retorna (pronta, motivo_se_não)."""
    if not WIN32_AVAILABLE:
        return True, ""
    try:
        hprinter = win32print.OpenPrinter(printer_name)
        try:
            info = win32print.GetPrinter(hprinter, 2)
            status = info["Status"]
            attrs  = info.get("Attributes", 0)
            if attrs & win32print.PRINTER_ATTRIBUTE_PAUSED:
                return False, "impressora em pausa"
            if status & 0x00000080:  # PRINTER_STATUS_OFFLINE
                return False, "impressora offline"
            if status & 0x00000002:  # PRINTER_STATUS_ERROR
                return False, "impressora em estado de erro"
        finally:
            win32print.ClosePrinter(hprinter)
    except Exception as e:
        logger.debug("Verificação de status da impressora: %s", e)
    return True, ""


def _pending_job_ids(printer_name: str) -> set[int]:
    """Retorna IDs dos jobs ainda não impressos/deletados na fila."""
    if not WIN32_AVAILABLE:
        return set()
    # Flags de conclusão: PRINTED | DELETED | DELETING | COMPLETE
    done_flags = 0x0080 | 0x0100 | 0x0004 | 0x1000
    ids: set[int] = set()
    try:
        hprinter = win32print.OpenPrinter(printer_name)
        try:
            for job in win32print.EnumJobs(hprinter, 0, 100, 1):
                if not (job.get("Status", 0) & done_flags):
                    ids.add(job["JobId"])
        finally:
            win32print.ClosePrinter(hprinter)
    except Exception as e:
        logger.debug("EnumJobs: %s", e)
    return ids


def _delete_jobs(printer_name: str, job_ids: set[int]) -> None:
    """Cancela jobs específicos da fila de impressão."""
    if not WIN32_AVAILABLE or not job_ids:
        return
    ctrl_delete = getattr(win32print, "JOB_CONTROL_DELETE", 5)
    try:
        hprinter = win32print.OpenPrinter(printer_name)
        try:
            for jid in job_ids:
                try:
                    win32print.SetJob(hprinter, jid, 0, None, ctrl_delete)
                except Exception:
                    pass
        finally:
            win32print.ClosePrinter(hprinter)
    except Exception as e:
        logger.debug("SetJob delete: %s", e)


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
    Usa o modelo de comprovante configurado (padrão ou clássico térmico).

    Returns:
        (success, message)
    """
    valid, error = validate_print_data(data)
    if not valid:
        logger.warning("Dados de impressão inválidos: %s", error)
        return False, error

    # Verifica status antes de enviar ao spooler — evita fila silenciosa
    ready, reason = _check_printer_status(printer_name)
    if not ready:
        msg = f"Impressora não disponível: {reason}"
        logger.error("Impressão bloqueada (%s): %s", printer_name, reason)
        return False, msg

    cfg = config.load_config()
    receipt_model = cfg.get("receipt_model", "default")

    # Snapshot antes de enviar ao spooler — detecta job preso quando impressora
    # está fisicamente desconectada (PRINTER_STATUS_OFFLINE não é confiável para USB)
    before = _pending_job_ids(printer_name)

    if receipt_model == "thermal_classic":
        ok, msg = format_ticket_thermal_classic(printer_name, data)
    else:
        try:
            printer = _get_printer(printer_name)
        except Exception as e:
            msg = f"Erro ao conectar à impressora '{printer_name}': {e}"
            logger.error(msg)
            return False, msg

        try:
            format_ticket(printer, data)
            printer.close()
            ok, msg = True, "Ticket impresso com sucesso"
        except Exception as e:
            msg = f"Erro ao imprimir: {e}"
            logger.error(msg)
            try:
                printer.close()
            except Exception:
                pass
            return False, msg

    if not ok:
        return False, msg

    # Aguarda a impressora processar e verifica se o job ficou preso na fila
    time.sleep(1.0)
    after = _pending_job_ids(printer_name)
    stuck = after - before
    if stuck:
        _delete_jobs(printer_name, stuck)
        logger.error(
            "Impressão falhou: %d job(s) ficaram na fila — impressora não respondeu (%s)",
            len(stuck), printer_name,
        )
        return False, "Impressora não processou o job. Verifique se está ligada e conectada."

    logger.info("Ticket impresso com sucesso (código: %s)", data.get("code", "?"))
    return True, "Ticket impresso com sucesso"


def test_print(printer_name: str) -> tuple[bool, str]:
    test_data = {
        "header": "=== TESTE DE IMPRESSÃO ===",
        "code": "T001",
        "services": "Teste",
        "created_date": "2024-01-01 00:00",
        "footer": "Impressão de teste OK",
    }
    ok, msg = print_ticket(printer_name, test_data)
    if ok:
        logger.info("Teste de impressão OK (%s)", printer_name)
        return True, "Impressão de teste realizada com sucesso!"
    if "não processou o job" in msg:
        return False, "A impressora não processou o teste.\nVerifique se está ligada, conectada e com papel."
    return False, msg
