"""Entry point for Spec Verification Lab Desktop Application."""
import sys
from pathlib import Path

# Add current directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def run():
    if "--tk" in sys.argv:
        from gui.desktop_app import main as run_tk
        run_tk()
    else:
        try:
            from gui.qt_app import main as run_qt
            run_qt()
        except ImportError as e:
            print(f"[Warning] PyQt6 not available ({e}), falling back to Tkinter...")
            from gui.desktop_app import main as run_tk
            run_tk()


if __name__ == "__main__":
    run()
