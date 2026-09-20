"""Resolve application paths for development and PyInstaller builds."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_app_root() -> Path:
    """Directory for user data folders (input, output, hymns, etc.)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_bundle_root() -> Path:
    """Directory for bundled read-only resources inside the executable."""
    if is_frozen():
        return Path(sys._MEIPASS)
    return get_app_root()


def get_template_path() -> Path:
    local = get_app_root() / "templates" / "Sunday_Template.pptx"
    if local.exists():
        return local

    bundled = get_bundle_root() / "templates" / "Sunday_Template.pptx"
    if bundled.exists():
        return bundled

    return local


def get_thumbnail_template_path() -> Path:
    local = get_app_root() / "templates" / "Thumbnail_Template.pptx"
    if local.exists():
        return local

    bundled = get_bundle_root() / "templates" / "Thumbnail_Template.pptx"
    if bundled.exists():
        return bundled

    return local


def load_app_env() -> None:
    """Load optional API keys from config/.env next to the application."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    env_path = get_app_root() / "config" / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)


def ensure_app_dirs() -> None:
    """Create expected folders next to the app and seed the template if needed."""
    root = get_app_root()
    for name in (
        "input",
        "input2",
        "input_hyms",
        "output",
        "config",
        "hymns",
        "templates",
        "responsive_readings",
        "bible",
    ):
        (root / name).mkdir(parents=True, exist_ok=True)

    local_template = root / "templates" / "Sunday_Template.pptx"
    if not local_template.exists():
        bundled_template = get_bundle_root() / "templates" / "Sunday_Template.pptx"
        if bundled_template.exists():
            shutil.copy2(bundled_template, local_template)

    local_thumbnail = root / "templates" / "Thumbnail_Template.pptx"
    if not local_thumbnail.exists():
        bundled_thumbnail = get_bundle_root() / "templates" / "Thumbnail_Template.pptx"
        if bundled_thumbnail.exists():
            shutil.copy2(bundled_thumbnail, local_thumbnail)

    local_gae = root / "bible" / "gae_verses.json"
    if not local_gae.exists():
        bundled_gae = get_bundle_root() / "bible" / "gae_verses.json"
        if bundled_gae.exists():
            shutil.copy2(bundled_gae, local_gae)


def get_gae_verses_path() -> Path | None:
    """Prefer bible/gae_verses.json next to the app, then the bundled copy."""
    local = get_app_root() / "bible" / "gae_verses.json"
    if local.is_file():
        return local

    bundled = get_bundle_root() / "bible" / "gae_verses.json"
    if bundled.is_file():
        return bundled

    legacy = get_app_root() / "data" / "gae_verses.json"
    if legacy.is_file():
        return legacy

    return None


def get_input_hyms_dir() -> Path:
    return get_app_root() / "input_hyms"
