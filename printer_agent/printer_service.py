"""
Serviço de impressão: descoberta de impressoras Windows e impressão via ESC/POS.
Suporta dois modelos de comprovante: padrão e clássico térmico (80mm).
"""

import logging
import threading
import time
import config
from escpos.printer import Win32Raw
from ticket_formatter import (
    format_ticket,
    format_ticket_thermal_classic,
    validate_print_data,
)

logger = logging.getLogger(__name__)

# Garante que apenas uma impressão ocorra por vez (test print + job real podem
# coexistir em threads distintas e corromper a fila um do outro).
_print_lock = threading.Lock()

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
            logger.debug("printer_status(%s) status=0x%x attrs=0x%x", printer_name, status, attrs)
            # Valor hardcoded (0x1) para não depender da constante do win32print
            # que pode não estar disponível no EXE bundled pelo PyInstaller.
            if attrs & 0x00000001:  # PRINTER_ATTRIBUTE_PAUSED
                return False, "impressora em pausa"
            if status & 0x00000080:  # PRINTER_STATUS_OFFLINE
                return False, "impressora offline"
            if status & 0x00000002:  # PRINTER_STATUS_ERROR
                return False, "impressora em estado de erro"
            if status & 0x00001000:  # PRINTER_STATUS_NOT_AVAILABLE
                return False, "impressora não disponível"
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
    """Cancela jobs específicos da fila de impressão (tenta CANCEL e DELETE)."""
    if not WIN32_AVAILABLE or not job_ids:
        return
    ctrl_cancel = getattr(win32print, "JOB_CONTROL_CANCEL", 3)
    ctrl_delete = getattr(win32print, "JOB_CONTROL_DELETE", 5)
    try:
        hprinter = win32print.OpenPrinter(printer_name)
        try:
            for jid in job_ids:
                for ctrl in (ctrl_cancel, ctrl_delete):
                    try:
                        win32print.SetJob(hprinter, jid, 0, None, ctrl)
                    except Exception:
                        pass
        finally:
            win32print.ClosePrinter(hprinter)
    except Exception as e:
        logger.debug("SetJob delete: %s", e)


def _all_job_ids(printer_name: str) -> set[int]:
    """Retorna IDs de TODOS os jobs visíveis na fila (inclusive em DELETING)."""
    if not WIN32_AVAILABLE:
        return set()
    ids: set[int] = set()
    try:
        hprinter = win32print.OpenPrinter(printer_name)
        try:
            for job in win32print.EnumJobs(hprinter, 0, 100, 1):
                ids.add(job["JobId"])
        finally:
            win32print.ClosePrinter(hprinter)
    except Exception as e:
        logger.debug("EnumJobs (all): %s", e)
    return ids


def _find_new_job(printer_name: str, before_ids: set[int], timeout: float = 1.5) -> int | None:
    """Aguarda um novo job aparecer na fila após o envio. Retorna o ID ou None se timeout."""
    if not WIN32_AVAILABLE:
        return None
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.15)
        current = _all_job_ids(printer_name)
        new = current - before_ids
        if new:
            return next(iter(new))
    return None


def _poll_job_result(printer_name: str, job_id: int, timeout: float = 8.0) -> tuple[bool, str]:
    """
    Acompanha um job específico até status terminal ou timeout.
    Detecta OFFLINE/ERROR nos flags do job E no status da impressora após conclusão.
    Retorna (ok, motivo).
    """
    if not WIN32_AVAILABLE:
        return True, "ok"
    # ERROR | OFFLINE | PAPEROUT | BLOCKED_DEVQ | USER_INTERVENTION
    error_mask = 0x0002 | 0x0020 | 0x0040 | 0x0200 | 0x0400
    # PRINTED | DELETED | COMPLETE
    done_mask = 0x0080 | 0x0100 | 0x1000
    job_finished = False
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            hprinter = win32print.OpenPrinter(printer_name)
            try:
                jobs = win32print.EnumJobs(hprinter, 0, 100, 1)
                job  = next((j for j in jobs if j["JobId"] == job_id), None)
            finally:
                win32print.ClosePrinter(hprinter)
        except Exception as e:
            logger.debug("_poll_job_result EnumJobs: %s", e)
            job_finished = True
            break
        if job is None:
            job_finished = True
            break
        status = job.get("Status", 0)
        logger.debug("_poll_job_result job=%d status=0x%04x", job_id, status)
        if status & error_mask:
            return False, f"status=0x{status:04x}"
        if status & done_mask:
            job_finished = True
            break
        time.sleep(0.3)

    if not job_finished:
        return False, "timeout"

    # Job concluído ou desaparecido — no EXE alguns drivers USB marcam o job como
    # PRINTED antes de gravar na porta física; o erro aparece no status da impressora.
    time.sleep(0.3)
    ready, reason = _check_printer_status(printer_name)
    logger.debug("_poll_job_result pós-job (%s): ready=%s reason=%s", printer_name, ready, reason)
    if not ready:
        return False, f"printer: {reason}"
    return True, "done"


def _poll_printer_stable(printer_name: str, seconds: float = 0.8) -> tuple[bool, str]:
    """Verifica se a impressora permanece sem erros pelo período informado."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        time.sleep(0.25)
        ready, reason = _check_printer_status(printer_name)
        if not ready:
            return False, reason
    return True, ""


def _open_printer_admin(printer_name: str):
    """Abre handle da impressora com PRINTER_ALL_ACCESS (necessário para Pause/Purge)."""
    if not WIN32_AVAILABLE:
        return None
    access = getattr(win32print, "PRINTER_ALL_ACCESS", 0x000F000C)
    try:
        return win32print.OpenPrinter(printer_name, {"DesiredAccess": access})
    except Exception:
        # Fallback: abre sem flags específicas
        try:
            return win32print.OpenPrinter(printer_name)
        except Exception as e:
            logger.debug("OpenPrinter admin: %s", e)
            return None


def purge_print_queue(printer_name: str) -> bool:
    """
    Limpa toda a fila de impressão da impressora informada.

    Estratégia robusta para remover jobs presos quando a impressora estava
    desconectada (USB):
      1. Pausa a impressora (impede o spooler de continuar enviando)
      2. Cancela e deleta todos os jobs (inclusive os em estado DELETING)
      3. Chama PRINTER_CONTROL_PURGE para forçar limpeza no spooler
      4. Aguarda os jobs sumirem da fila
      5. Despausa a impressora
    """
    if not WIN32_AVAILABLE:
        return False

    ctrl_pause   = getattr(win32print, "PRINTER_CONTROL_PAUSE",   1)
    ctrl_resume  = getattr(win32print, "PRINTER_CONTROL_RESUME",  2)
    ctrl_purge   = getattr(win32print, "PRINTER_CONTROL_PURGE",   3)
    ctrl_cancel  = getattr(win32print, "JOB_CONTROL_CANCEL",      3)
    ctrl_delete  = getattr(win32print, "JOB_CONTROL_DELETE",      5)

    initial_jobs = _all_job_ids(printer_name)
    if not initial_jobs:
        return False

    logger.info("Limpando fila de impressão: %d job(s) (%s)",
                len(initial_jobs), printer_name)

    hprinter = _open_printer_admin(printer_name)
    if hprinter is None:
        return False

    try:
        # 1. Pausa a impressora
        try:
            win32print.SetPrinter(hprinter, 0, None, ctrl_pause)
        except Exception as e:
            logger.debug("Pause printer falhou: %s", e)

        # 2. Cancela + deleta cada job
        for jid in initial_jobs:
            for ctrl in (ctrl_cancel, ctrl_delete):
                try:
                    win32print.SetJob(hprinter, jid, 0, None, ctrl)
                except Exception:
                    pass

        # 3. Purge global no spooler
        try:
            win32print.SetPrinter(hprinter, 0, None, ctrl_purge)
        except Exception as e:
            logger.debug("SetPrinter PURGE falhou: %s", e)

        # 4. Aguarda jobs realmente sumirem (até 3s)
        deadline = time.time() + 3.0
        while time.time() < deadline:
            remaining = _all_job_ids(printer_name)
            if not remaining:
                break
            time.sleep(0.2)

        # 5. Despausa a impressora
        try:
            win32print.SetPrinter(hprinter, 0, None, ctrl_resume)
        except Exception as e:
            logger.debug("Resume printer falhou: %s", e)
    finally:
        try:
            win32print.ClosePrinter(hprinter)
        except Exception:
            pass

    final_jobs = _all_job_ids(printer_name)
    if final_jobs:
        logger.warning("Fila ainda contém %d job(s) após limpeza (%s)",
                       len(final_jobs), printer_name)
        return False

    logger.info("Fila de impressão limpa com sucesso (%s)", printer_name)
    return True


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


def print_ticket(printer_name: str, data: dict) -> tuple[bool, str, bool]:
    """
    Imprime um ticket na impressora especificada.
    Usa o modelo de comprovante configurado (padrão ou clássico térmico).

    Returns:
        (success, message, reached_spooler)
        reached_spooler=False → falha antes de qualquer envio ao spooler (seguro
        para o servidor retentar). reached_spooler=True → dados foram enviados ao
        spooler; mesmo que success=False, o ticket pode já ter sido impresso
        fisicamente, então o job_id deve ser registrado para evitar duplicata.
    """
    with _print_lock:
        valid, error = validate_print_data(data)
        if not valid:
            logger.warning("Dados de impressão inválidos: %s", error)
            return False, error, False

        # Verifica status antes de enviar ao spooler — evita fila silenciosa
        ready, reason = _check_printer_status(printer_name)
        if not ready:
            msg = f"Impressora não disponível: {reason}"
            logger.error("Impressão bloqueada (%s): %s", printer_name, reason)
            return False, msg, False

        cfg = config.load_config()
        receipt_model = cfg.get("receipt_model", "default")

        # Limpa jobs antigos presos de tentativas anteriores com impressora desconectada.
        if _all_job_ids(printer_name):
            purge_print_queue(printer_name)

        # Snapshot de todos os jobs antes de enviar (inclui concluídos/deletados para
        # identificar exatamente o job recém-enviado, independente do status).
        before_all = _all_job_ids(printer_name)

        if receipt_model == "thermal_classic":
            ok, msg = format_ticket_thermal_classic(printer_name, data)
        else:
            try:
                printer = _get_printer(printer_name)
            except Exception as e:
                msg = f"Erro ao conectar à impressora '{printer_name}': {e}"
                logger.error(msg)
                return False, msg, False

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
                purge_print_queue(printer_name)
                # Dados foram parcialmente enviados ao spooler — tratar como incerto.
                return False, msg, True

        if not ok:
            # Não é possível saber se o spooler foi tocado antes da falha
            # (StartDocPrinter pode ter sido chamado). Tratar como incerto.
            return False, msg, True

        # A partir daqui os dados foram enviados ao spooler. Qualquer falha
        # de detecção deve ser tratada como "possivelmente impresso" para evitar
        # duplicata caso o servidor reenvie o mesmo job_id.

        # Aguarda o driver tentar comunicar com a porta USB (falha aparece no status
        # da impressora ou do job imediatamente após a tentativa de escrita).
        time.sleep(0.4)

        # Verificação imediata após o envio — captura falha USB antes mesmo de
        # rastrear o job na fila. Resolve o caso do EXE onde o job some da fila
        # muito rápido (< 150ms) e só o status da impressora reflete o erro.
        ready_quick, reason_quick = _check_printer_status(printer_name)
        if not ready_quick:
            purge_print_queue(printer_name)
            logger.error("Impressora em erro logo após envio (%s): %s", printer_name, reason_quick)
            return False, "Impressora não respondeu. Verifique se está ligada e conectada.", True

        # Rastreia o job específico (timeout reduzido pois já esperamos 0.4s).
        # _poll_job_result também checa status da impressora ao final.
        new_job_id = _find_new_job(printer_name, before_all, timeout=1.1)
        if new_job_id is not None:
            job_ok, job_reason = _poll_job_result(printer_name, new_job_id)
            if not job_ok:
                purge_print_queue(printer_name)
                logger.error("Job %d falhou (%s): %s", new_job_id, printer_name, job_reason)
                if "timeout" in job_reason:
                    return False, "Impressora não processou o job. Verifique se está ligada e conectada.", True
                return False, "Impressora não respondeu. Verifique se está ligada e conectada.", True
        else:
            # Job não encontrado na fila — fallback: monitora status por mais 0.8s.
            stable_ok, stable_reason = _poll_printer_stable(printer_name, seconds=0.8)
            if not stable_ok:
                purge_print_queue(printer_name)
                logger.error("Falha pós-envio sem job detectado (%s): %s", printer_name, stable_reason)
                return False, "Impressora não respondeu. Verifique se está ligada e conectada.", True

        logger.info("Ticket impresso com sucesso (código: %s)", data.get("code", "?"))
        return True, "Ticket impresso com sucesso", True


def test_print(printer_name: str) -> tuple[bool, str]:
    # Garante que a fila esteja vazia antes do teste — evita imprimir jobs
    # presos de falhas anteriores (impressora que estava desconectada).
    purge_print_queue(printer_name)

    test_data = {
        "header": "=== TESTE DE IMPRESSÃO ===",
        "code": "T001",
        "services": "Teste",
        "created_date": "2024-01-01 00:00",
        "footer": "Impressão de teste OK",
    }
    ok, msg, _ = print_ticket(printer_name, test_data)
    if ok:
        logger.info("Teste de impressão OK (%s)", printer_name)
        return True, "Impressão de teste realizada com sucesso!"
    if "não processou o job" in msg or "não respondeu" in msg:
        return False, "A impressora não processou o teste.\nVerifique se está ligada, conectada e com papel."
    return False, msg
