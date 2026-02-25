"""
Cliente WebSocket com auto-reconnect e autenticação por primeira mensagem.
"""

import json
import asyncio
import logging
from typing import Callable, Optional

import websockets
from websockets.asyncio.client import connect

import printer_service

logger = logging.getLogger(__name__)

MAX_MESSAGE_SIZE = 64 * 1024  # 64KB
VALID_SERVER_TYPES = {"auth_ok", "auth_error", "print", "ping"}


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
    ):
        self.ws_url = ws_url
        self.auth_token = auth_token
        self.printer_name = printer_name
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._on_error = on_error
        self._on_auth_failed = on_auth_failed
        self._running = False
        self._backoff = 1
        self._max_backoff = 30
        self._ws = None

    async def start(self) -> None:
        self._running = True
        while self._running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Conexão perdida: %s", e)
                self._notify_disconnected()
                if self._running:
                    logger.info("Reconectando em %ds...", self._backoff)
                    await asyncio.sleep(self._backoff)
                    self._backoff = min(self._backoff * 2, self._max_backoff)

    async def stop(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()

    async def _connect_and_listen(self) -> None:
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
                if self._on_auth_failed:
                    self._on_auth_failed(error_msg)
                return

            if auth_msg.get("type") != "auth_ok":
                raise ConnectionError(f"Resposta inesperada: {auth_msg.get('type')}")

            # Autenticado com sucesso
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
        data = msg.get("data")

        if not isinstance(data, dict):
            await self._send_result(job_id, "error", "Campo 'data' ausente ou inválido")
            return

        # Impressão em thread separada para não bloquear o event loop
        loop = asyncio.get_event_loop()
        success, message = await loop.run_in_executor(
            None, printer_service.print_ticket, self.printer_name, data
        )

        status = "success" if success else "error"
        await self._send_result(job_id, status, message)

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

    def _notify_connected(self) -> None:
        if self._on_connected:
            self._on_connected()

    def _notify_disconnected(self) -> None:
        if self._on_disconnected:
            self._on_disconnected()

    def update_config(self, ws_url: str, auth_token: str, printer_name: str) -> None:
        self.ws_url = ws_url
        self.auth_token = auth_token
        self.printer_name = printer_name
