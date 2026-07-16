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
        # Total acumulado de registros já emitidos (nunca decresce, mesmo
        # quando a deque descarta os mais antigos). Permite leitura
        # incremental em tempo real pela janela de logs.
        self._total = 0

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._records.append(self.format(record))
            self._total += 1
        except Exception:
            pass

    def get_logs(self) -> str:
        return "\n".join(self._records)

    def total(self) -> int:
        return self._total

    def get_since(self, seen: int) -> tuple[int, list[str]]:
        """Retorna (novo_total, linhas_novas) desde o índice absoluto ``seen``.

        Usado para atualização incremental: a janela guarda o último total
        exibido e pede apenas o que chegou depois, evitando redesenhar tudo.
        """
        held = len(self._records)
        start = self._total - held          # índice absoluto do 1º registro mantido
        offset = max(0, seen - start)
        if offset >= held:
            return self._total, []
        return self._total, list(self._records)[offset:]

    def clear(self) -> None:
        self._records.clear()
        # Mantém _total como contador monotônico da sessão; a janela
        # reinicia sua contagem via total() após limpar.


buffer = _LogBuffer()


def install() -> None:
    """Registra o buffer no logger raiz. Chamar uma vez no início do processo."""
    root = logging.getLogger()
    if buffer not in root.handlers:
        root.addHandler(buffer)
