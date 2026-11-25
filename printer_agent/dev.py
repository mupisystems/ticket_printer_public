"""
Modo desenvolvimento: roda o agente e reinicia automaticamente quando
algum arquivo .py (ou da interface em ui/) for salvo. Use: python dev.py

Dica: PRINTER_AGENT_DEBUG=1 abre as ferramentas de desenvolvedor da janela.
Para mexer só no visual, sirva a pasta ui/ e abra index.html?mock no navegador.
"""

import os
import subprocess
import sys
import time


def _script_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _py_mtimes() -> dict:
    """Retorna dict path -> mtime dos .py do agente e dos arquivos da interface."""
    base = _script_dir()
    candidates = [os.path.join(base, n) for n in os.listdir(base) if n.endswith(".py")]
    ui_dir = os.path.join(base, "ui")
    if os.path.isdir(ui_dir):
        candidates += [os.path.join(ui_dir, n) for n in os.listdir(ui_dir)
                       if n.endswith((".html", ".css", ".js"))]
    out = {}
    for path in candidates:
        try:
            out[path] = os.path.getmtime(path)
        except OSError:
            pass
    return out


def main() -> None:
    base = _script_dir()
    main_py = os.path.join(base, "main.py")
    if not os.path.isfile(main_py):
        print("main.py não encontrado.")
        sys.exit(1)

    last_mtimes = _py_mtimes()
    proc = subprocess.Popen(
        [sys.executable, main_py],
        cwd=base,
        stdin=subprocess.DEVNULL,
    )
    print("Agente iniciado. Salve um .py para reiniciar automaticamente. Ctrl+C para encerrar.")

    try:
        while True:
            time.sleep(1.2)
            if proc.poll() is not None:
                print("Processo encerrado.")
                break
            new_mtimes = _py_mtimes()
            if new_mtimes != last_mtimes:
                print("Arquivos alterados — reiniciando...")
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                last_mtimes = _py_mtimes()
                proc = subprocess.Popen(
                    [sys.executable, main_py],
                    cwd=base,
                    stdin=subprocess.DEVNULL,
                )
                print("Agente reiniciado.")
    except KeyboardInterrupt:
        print("\nEncerrando...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("Até mais.")


if __name__ == "__main__":
    main()
