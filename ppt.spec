# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(SPECPATH)
SRC = ROOT / "src"

datas = [
    (str(ROOT / "templates" / "Sunday_Template.pptx"), "templates"),
    (str(ROOT / "templates" / "Thumbnail_Template.pptx"), "templates"),
    (str(ROOT / "bible" / "gae_verses.json"), "bible"),
    (str(ROOT / "bible" / "responsive_reading" / "responsive_ko.json"), "bible/responsive_reading"),
    (str(ROOT / "bible" / "responsive_reading" / "responsive_en.json"), "bible/responsive_reading"),
]
binaries = []
hiddenimports = [
    "app_paths",
    "dotenv",
    "deep_translator",
    "deep_translator.google",
    "deep_translator.mymemory",
    "fitz",
    "gui_app",
    "kiwipiepy",
    "kiwipiepy_model",
    "korean_text",
    "hymn_merger",
    "hymn_resolver",
    "youth_sermon_merger",
    "bible_books",
    "bible_fetcher",
    "responsive_library",
    "responsive_merger",
    "responsive_parser",
    "scripture_merger",
    "sermon_verse_merger",
    "sermon_verse_parser",
    "scripture_parser",
    "ppt_com_text",
    "ppt_com_session",
    "ppt_builder",
    "thumbnail_builder",
    "pptx",
    "pythoncom",
    "translator",
    "week_generator",
    "win32com",
    "win32com.client",
]

for package in ("kiwipiepy", "kiwipiepy_model"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

datas += collect_data_files("kiwipiepy")
datas += collect_data_files("kiwipiepy_model")

a = Analysis(
    [str(SRC / "main_gui.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pandas", "matplotlib", "scipy", "IPython", "notebook"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="PPT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
