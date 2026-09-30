"""Entry point for the AegisFlow desktop application."""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


if __name__ == "__main__":
    from gui.qt_app import main

    main()
