"""
Gerenciamento de configuração persistente.
Armazena settings em %APPDATA%/MeuAtendimento/printer_config.json.
Token de autenticação cifrado com Windows DPAPI.
"""

import os
import json
import base64
import logging

logger = logging.getLogger(__name__)

try:
    import win32crypt
    DPAPI_AVAILABLE = True
except ImportError:
    DPAPI_AVAILABLE = False
    logger.warning("win32crypt não disponível — token será armazenado em texto puro")

ENVIRONMENTS = {
    "localhost": "ws://localhost:8000/ws/printer",
    "homologacao": "wss://testes.meuatendimentovirtual.com.br/ws/printer",
    "producao_br": "wss://painel.meuatendimentovirtual.com.br/ws/printer",
    "producao_us": "wss://dash.awaitra.com/ws/printer",
    "custom": None,
}

ENVIRONMENT_LABELS = {
    "localhost": "Localhost",
    "homologacao": "Homologação",
    "producao_br": "Produção - MeuAtendimentoVirtual",
    "producao_us": "Produção - Awaitra.com",
    "custom": "Personalizado",
}

RECEIPT_MODEL_LABELS = {
    "default": "Modelo reduzido",
    "thermal_classic": "Modelo destaque",
}

DEFAULT_CONFIG = {
    "environment": "producao_br",
    "server_url": "",
    "auth_token_encrypted": "",
    "printer_name": "",
    "auto_connect": True,
    "start_with_windows": True,
    "receipt_model": "default",
}


def get_config_dir() -> str:
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    config_dir = os.path.join(appdata, "MeuAtendimento")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


def get_config_path() -> str:
    return os.path.join(get_config_dir(), "printer_config.json")


def _encrypt_token(token: str) -> str:
    if not token:
        return ""
    if not DPAPI_AVAILABLE:
        return base64.b64encode(token.encode("utf-8")).decode("ascii")
    encrypted = win32crypt.CryptProtectData(
        token.encode("utf-8"), "PrinterAgentToken", None, None, None, 0
    )
    return base64.b64encode(encrypted).decode("ascii")


def _decrypt_token(encrypted: str) -> str:
    if not encrypted:
        return ""
    if not DPAPI_AVAILABLE:
        return base64.b64decode(encrypted).decode("utf-8")
    raw = base64.b64decode(encrypted)
    _, decrypted = win32crypt.CryptUnprotectData(raw, None, None, None, 0)
    return decrypted.decode("utf-8")


def load_config() -> dict:
    path = get_config_path()
    if not os.path.exists(path):
        return dict(DEFAULT_CONFIG)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        config = dict(DEFAULT_CONFIG)
        config.update(data)
        return config
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Erro ao carregar config: %s", e)
        return dict(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    path = get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    logger.info("Configuração salva em %s", path)


def get_auth_token(config: dict) -> str:
    try:
        return _decrypt_token(config.get("auth_token_encrypted", ""))
    except Exception as e:
        logger.error("Erro ao decifrar token: %s", e)
        return ""


def set_auth_token(config: dict, token: str) -> None:
    config["auth_token_encrypted"] = _encrypt_token(token)


def get_ws_url(config: dict) -> str:
    env = config.get("environment", "producao_br")
    if env == "custom":
        return config.get("server_url", "")
    return ENVIRONMENTS.get(env, ENVIRONMENTS["producao_br"])
