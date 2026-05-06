"""Buffer de logs em memória — compartilhado entre main e config_window."""

import logging
from collections import deque

MAX_RECORDS = 1000

_FMT = logging.Formatter(
    "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class _LogBuffer(logging.Handler):
    def __init__(self, maxlen: int = MAX_RECORDS):
        super().__init__()
        self.setFormatter(_FMT)
        self._records: deque[str] = deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._records.append(self.format(record))
        except Exception:
            pass

    def get_logs(self) -> str:
        return "\n".join(self._records)

    def clear(self) -> None:
        self._records.clear()


buffer = _LogBuffer()


def install() -> None:
    """Registra o buffer no logger raiz. Chamar uma vez no início do processo."""
    root = logging.getLogger()
    if buffer not in root.handlers:
        root.addHandler(buffer)
