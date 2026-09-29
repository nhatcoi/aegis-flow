"""Colour tokens and the extra stylesheet layered on top of qdarktheme."""
from __future__ import annotations

ACCENT = "#4f8cff"

TOKENS = {
    "dark": {"bg": "#16181d", "panel": "#1b1d23", "border": "#2a2e38", "text": "#e6e8ee", "muted": "#8a93a6",
             "pass": "#4cc38a", "fail": "#ff6b6b", "warn": "#f5b94c", "idle": "#5b6475"},
    "light": {"bg": "#f6f7f9", "panel": "#ffffff", "border": "#dfe3ea", "text": "#1d2330", "muted": "#6b7385",
              "pass": "#1f9d61", "fail": "#d64545", "warn": "#b7791f", "idle": "#a0a7b5"},
}


def stylesheet(mode: str) -> str:
    t = TOKENS[mode]
    return f"""
    QWidget {{ font-size: 13px; }}
    QToolBar {{ spacing: 8px; padding: 4px 8px; border: none; border-bottom: 1px solid {t['border']}; }}
    QLabel#brand {{ font-size: 14px; font-weight: 600; color: {t['text']}; padding-right: 6px; }}
    QLabel#section {{ color: {t['muted']}; font-size: 11px; font-weight: 600; letter-spacing: 1px;
                      padding: 10px 2px 4px 2px; }}
    QLabel#metric {{ color: {t['muted']}; }}
    QPushButton#primary {{ background: {ACCENT}; color: white; font-weight: 600; border: none;
                           padding: 6px 14px; border-radius: 6px; }}
    QPushButton#primary:disabled {{ background: {t['idle']}; }}
    QListWidget, QTableWidget, QTextBrowser, QPlainTextEdit {{ border: 1px solid {t['border']}; border-radius: 6px; }}
    QTableWidget {{ gridline-color: {t['border']}; }}
    QHeaderView::section {{ padding: 4px 6px; font-weight: 600; }}
    QTabBar::tab {{ padding: 6px 14px; }}
    QSplitter::handle {{ background: {t['border']}; }}
    QSplitter::handle:horizontal {{ width: 1px; }}
    QSplitter::handle:vertical {{ height: 1px; }}
    """
