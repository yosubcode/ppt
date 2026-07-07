"""PyInstaller entry point for the worship PPT GUI."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))


def _report_fatal_error(error: BaseException) -> None:
    from app_paths import get_app_root

    log_path = get_app_root() / "config" / "error.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(traceback.format_exc(), encoding="utf-8")

    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "WorshipPPT 오류",
            f"프로그램 시작 중 오류가 발생했습니다.\n\n{error}\n\n"
            f"자세한 내용: {log_path}",
        )
        root.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        from app_paths import ensure_app_dirs, load_app_env
        from gui_app import main

        ensure_app_dirs()
        load_app_env()
        main()
    except Exception as error:
        _report_fatal_error(error)
        raise SystemExit(1)
