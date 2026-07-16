"""
Cliente WebSocket com auto-reconnect e autenticação por primeira mensagem.
"""

import json
import asyncio
import logging
import os
import time
from typing import Callable, Optional

import websockets
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

import config
import printer_service

logger = logging.getLogger(__name__)

MAX_MESSAGE_SIZE = 64 * 1024  # 64KB
VALID_SERVER_TYPES = {"auth_ok", "auth_error", "print", "ping"}

# Deduplicação de jobs: evita imprimir o mesmo job_id duas vezes quando o
# servidor re-envia jobs pendentes após uma reconexão do WebSocket.
# O cache é persistido em disco para sobreviver a crashes e reinicializações.
_PRINTED_JOB_TTL = 300  # segundos que um job_id fica registrado como impresso
_printed_job_ids: dict[str, float] = {}

# Jobs em impressão neste exato momento. Protege contra o mesmo job chegar
# por duas conexões simultâneas (ex.: durante uma troca de conexão): o cache
# de "já impresso" só é preenchido DEPOIS da impressão, então sem esta trava
# os dois processariam o job em paralelo e o ticket sairia duas vezes.
_inflight_job_ids: set[str] = set()


def _cache_path() -> str:
    return os.path.join(config.get_config_dir(), "printed_jobs_cache.json")


def _load_job_cache() -> None:
    path = _cache_path()
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        now = time.time()
        for job_id, ts in data.items():
            if now - ts <= _PRINTED_JOB_TTL:
                _printed_job_ids[job_id] = ts
    except Exception as e:
        logger.warning("Erro ao carregar cache de jobs impressos: %s", e)


def _save_job_cache() -> None:
    try:
        with open(_cache_path(), "w", encoding="utf-8") as f:
            json.dump(_printed_job_ids, f)
    except Exception as e:
        logger.warning("Erro ao salvar cache de jobs impressos: %s", e)


def _is_duplicate_job(job_id: str) -> bool:
    if not job_id or job_id == "unknown":
        return False
    now = time.time()
    expired = [k for k, ts in list(_printed_job_ids.items()) if now - ts > _PRINTED_JOB_TTL]
    for k in expired:
        del _printed_job_ids[k]
    return job_id in _printed_job_ids


def _register_printed_job(job_id: str) -> None:
    if job_id and job_id != "unknown":
        _printed_job_ids[job_id] = time.time()
        _save_job_cache()


_load_job_cache()


class PrinterWebSocketClient:
    def __init__(
        self,
        ws_url: str,
        auth_token: str,
        printer_name: str,
        on_connected: Optional[Callable] = None,
        on_disconnected: Optional[Callable] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_auth_failed: Optional[Callable[[str], None]] = None,
        on_print_result: Optional[Callable[[str, bool, str], None]] = None,
        on_reconnecting: Optional[Callable] = None,
    ):
        self.ws_url = ws_url
        self.auth_token = auth_token
        self.printer_name = printer_name
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._on_error = on_error
        self._on_auth_failed = on_auth_failed
        self._on_print_result = on_print_result
        self._on_reconnecting = on_reconnecting
        self._running = False
        self._backoff = 1
        self._max_backoff = 30
        self._ws = None
        self._authenticated = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._running = True
        # Guarda a task para que stop() possa cancelar até um handshake em
        # andamento (connect() antes de self._ws existir). Sem isso, um
        # cliente antigo podia completar a conexão após o stop() e virar uma
        # conexão "zumbi" — causando impressão duplicada de cada job.
        self._task = asyncio.current_task()
        while self._running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except ConnectionClosed as e:
                if e.code == 1011 and not self._authenticated:
                    reason = ""
                    if getattr(e, "rcvd", None) and getattr(e.rcvd, "reason", None):
                        reason = (e.rcvd.reason or "").strip()
                    if not reason:
                        reason = (getattr(e, "reason", None) or "").strip()
                    extra = f" Motivo do servidor: {reason}." if reason else ""
                    message = (
                        "Conexão encerrada pelo servidor durante autenticação (1011). "
                        "Verifique URL/token ou o backend." + extra
                    )
                    logger.error(message)
                    self._running = False
                    self._safe_call(self._on_auth_failed, message)
                    self._notify_disconnected()
                    break
                if e.code == 1011:
                    logger.warning(
                        "Servidor encerrou conexão com erro interno (1011). "
                        "Verifique backend, URL configurada e token."
                    )
                else:
                    logger.warning("Conexão WebSocket encerrada (código %s): %s", e.code, e)
                await self._handle_drop()
            except (asyncio.TimeoutError, TimeoutError):
                logger.warning(
                    "Tempo esgotado aguardando resposta do servidor (autenticação/handshake). "
                    "Servidor pode estar lento ou indisponível."
                )
                await self._handle_drop()
            except Exception as e:
                # Alguns erros trazem mensagem vazia; usa o tipo como fallback.
                logger.warning("Conexão perdida: %s", e or type(e).__name__)
                await self._handle_drop()

    async def _handle_drop(self) -> None:
        """Trata uma queda de conexão: sinaliza estado e aguarda o backoff.

        Se ainda vamos tentar de novo, o estado é "reconnecting" (visível na
        UI e nos logs). Só quando paramos de vez o estado vira "disconnected".
        """
        if self._running:
            self._notify_reconnecting()
            logger.info("Reconectando em %ds...", self._backoff)
            await asyncio.sleep(self._backoff)
            self._backoff = min(self._backoff * 2, self._max_backoff)
        else:
            self._notify_disconnected()

    async def stop(self) -> None:
        self._running = False
        # Cancela a task do loop de conexão — inclusive um handshake em
        # andamento que ainda não atribuiu self._ws.
        task = self._task
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._notify_disconnected()

    async def _connect_and_listen(self) -> None:
        self._authenticated = False
        async with connect(
            self.ws_url,
            max_size=MAX_MESSAGE_SIZE,
            ping_interval=30,
            ping_timeout=10,
        ) as ws:
            self._ws = ws

            # Autenticação via primeira mensagem
            await ws.send(json.dumps({"type": "auth", "token": self.auth_token}))

            # Aguarda resposta de auth
            auth_response = await asyncio.wait_for(ws.recv(), timeout=10)
            auth_msg = self._parse_message(auth_response)
            if auth_msg is None:
                raise ConnectionError("Resposta de autenticação inválida")

            if auth_msg.get("type") == "auth_error":
                error_msg = auth_msg.get("message", "Token inválido")
                logger.error("Autenticação rejeitada: %s", error_msg)
                self._running = False  # Para de reconectar
                self._safe_call(self._on_auth_failed, error_msg)
                return

            if auth_msg.get("type") != "auth_ok":
                raise ConnectionError(f"Resposta inesperada: {auth_msg.get('type')}")

            # stop() pode ter sido chamado durante o handshake — não seguir
            # com uma conexão que já foi substituída (evita cliente zumbi).
            if not self._running:
                return

            # Autenticado com sucesso
            self._authenticated = True
            logger.info("Conectado e autenticado em %s", self.ws_url)
            self._backoff = 1  # Reset backoff
            self._notify_connected()

            # Loop de mensagens
            async for raw_message in ws:
                await self._handle_message(raw_message)

    async def _handle_message(self, raw: str) -> None:
        msg = self._parse_message(raw)
        if msg is None:
            return

        msg_type = msg.get("type")
        if msg_type not in VALID_SERVER_TYPES:
            logger.debug("Tipo de mensagem desconhecido ignorado: %s", msg_type)
            return

        if msg_type == "ping":
            await self._ws.send(json.dumps({"type": "pong"}))

        elif msg_type == "print":
            await self._handle_print(msg)

    async def _handle_print(self, msg: dict) -> None:
        job_id = msg.get("id", "unknown")

        if _is_duplicate_job(job_id):
            logger.warning("Job %s já impresso — ignorando duplicata do servidor", job_id)
            await self._send_result(job_id, "success", "Já impresso")
            return

        # Job já em impressão por outra conexão/mensagem — não duplicar.
        has_real_id = bool(job_id) and job_id != "unknown"
        if has_real_id and job_id in _inflight_job_ids:
            logger.warning("Job %s já em impressão — ignorando duplicata simultânea", job_id)
            await self._send_result(job_id, "success", "Já em impressão")
            return

        data = msg.get("data")

        if not isinstance(data, dict):
            await self._send_result(job_id, "error", "Campo 'data' ausente ou inválido")
            return

        if has_real_id:
            _inflight_job_ids.add(job_id)
        try:
            # Impressão em thread separada para não bloquear o event loop
            loop = asyncio.get_event_loop()
            success, message, reached_spooler = await loop.run_in_executor(
                None, printer_service.print_ticket, self.printer_name, data
            )

            # Registra o job se dados foram enviados ao spooler, mesmo em caso
            # de falha de detecção — evita duplicata quando o servidor reenviar
            # o mesmo job_id (o ticket pode já ter sido impresso fisicamente).
            if success or reached_spooler:
                _register_printed_job(job_id)
        finally:
            if has_real_id:
                _inflight_job_ids.discard(job_id)

        status = "success" if success else "error"
        await self._send_result(job_id, status, message)
        self._safe_call(self._on_print_result, job_id, success, message)

    async def _send_result(self, job_id: str, status: str, message: str) -> None:
        response = {
            "type": "print_result",
            "id": job_id,
            "status": status,
            "message": message,
        }
        try:
            await self._ws.send(json.dumps(response))
        except Exception as e:
            logger.error("Erro ao enviar resultado: %s", e)

    def _parse_message(self, raw: str) -> Optional[dict]:
        try:
            msg = json.loads(raw)
            if not isinstance(msg, dict):
                logger.warning("Mensagem não é um dicionário JSON")
                return None
            return msg
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Mensagem JSON inválida: %s", e)
            return None

    @staticmethod
    def _safe_call(cb, *args) -> None:
        """Invoca um callback de UI sem deixar exceções derrubarem a conexão."""
        if not cb:
            return
        try:
            cb(*args)
        except Exception:
            logger.debug("Erro em callback de status (ignorado)", exc_info=True)

    def _notify_connected(self) -> None:
        self._safe_call(self._on_connected)

    def _notify_disconnected(self) -> None:
        self._safe_call(self._on_disconnected)

    def _notify_reconnecting(self) -> None:
        if self._on_reconnecting:
            self._safe_call(self._on_reconnecting)
        else:
            self._safe_call(self._on_disconnected)

    def update_config(self, ws_url: str, auth_token: str, printer_name: str) -> None:
        self.ws_url = ws_url
        self.auth_token = auth_token
        self.printer_name = printer_name
