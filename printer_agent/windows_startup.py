"""
Gerencia inicializacao automatica do agente no Windows (chave Run do usuario).
"""

from __future__ import annotations

import sys
import winreg

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "MeuAtendimentoPrinterAgent"


def _build_command() -> str | None:
    """
    Monta comando para iniciar o agente no login do usuario.
    Prioriza executavel congelado (PyInstaller).
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --background'

    # Em modo script, evita registrar startup porque dependeria de ambiente Python local.
    return None


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, RUN_VALUE_NAME)
            return bool(str(value).strip())
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_enabled(enabled: bool) -> tuple[bool, str]:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                command = _build_command()
                if not command:
                    return False, "Inicialização automática requer o executável gerado (dist\\printer_agent.exe)."
                winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, command)
                return True, "Inicialização automática habilitada."

            try:
                winreg.DeleteValue(key, RUN_VALUE_NAME)
            except FileNotFoundError:
                pass
            return True, "Inicialização automática desabilitada."
    except OSError as e:
        return False, f"Falha ao atualizar inicialização automática: {e}"
