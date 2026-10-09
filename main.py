"""FichaManual — resume y ordena manuales largos en una ficha clara."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fichamanual.gui import run_app

if __name__ == "__main__":
    run_app()
