"""Testable static-image export pipeline for Singularity 26.1.

No Qt dependency: the GUI, CLI and Existence adapter use the exact same
conversion, collision and report behavior.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

FORMATS = {"webp", "jpeg", "png"}


@dataclass(frozen=True)
class ExportSettings:
    format: str = "webp"
    quality: int = 80
    max_width: int = 2560
    max_height: int = 1440
    dpi: int = 72
    background: str = "white"

    def normalized(self) -> "ExportSettings":
        fmt = self.format.lower().replace("jpg", "jpeg")
        if fmt not in FORMATS:
            raise ValueError(f"Unsupported static export format: {self.format}")
        return ExportSettings(fmt, max(1, min(100, int(self.quality))),
                              max(1, int(self.max_width)), max(1, int(self.max_height)),
                              max(1, int(self.dpi)), self.background)


def _prepare(image: Image.Image, settings: ExportSettings) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    width, height = image.size
    if width > settings.max_width or height > settings.max_height:
        factor = min(settings.max_width / width, settings.max_height / height)
        image = image.resize((max(1, round(width * factor)), max(1, round(height * factor))), Image.Resampling.LANCZOS)
    alpha = image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info)
    if settings.format == "jpeg":
        if alpha:
            background = Image.new("RGBA", image.size, settings.background)
            background.alpha_composite(image.convert("RGBA"))
            image = background.convert("RGB")
        else:
            image = image.convert("RGB")
    else:
        image = image.convert("RGBA" if alpha else "RGB")
    return image


def export_image(source: str | Path, destination: str | Path, settings: ExportSettings = ExportSettings()) -> dict[str, Any]:
    settings = settings.normalized()
    source, destination = Path(source), Path(destination)
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    before = source.stat().st_size
    with Image.open(source) as original:
        image = _prepare(original, settings)
        size = image.size
        suffix = {"webp": ".webp", "jpeg": ".jpg", "png": ".png"}[settings.format]
        if destination.suffix.lower() != suffix:
            destination = destination.with_suffix(suffix)
        descriptor, temp_name = tempfile.mkstemp(prefix=f".{destination.stem}-", suffix=destination.suffix, dir=destination.parent)
        os.close(descriptor)
        temporary = Path(temp_name)
        try:
            options: dict[str, Any] = {"dpi": (settings.dpi, settings.dpi)}
            if settings.format == "webp": options.update(format="WEBP", quality=settings.quality, method=6)
            elif settings.format == "jpeg": options.update(format="JPEG", quality=settings.quality, optimize=True, progressive=True)
            else: options.update(format="PNG", optimize=True, compress_level=9)
            image.save(temporary, **options)
            os.replace(temporary, destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    after = destination.stat().st_size
    return {"source": str(source), "destination": str(destination), "format": settings.format,
            "size": list(size), "before_bytes": before, "after_bytes": after,
            "saved_bytes": before - after, "settings": asdict(settings)}


def unique_destination(folder: str | Path, source: str | Path, fmt: str) -> Path:
    folder, source = Path(folder), Path(source)
    extension = {"webp": ".webp", "jpeg": ".jpg", "png": ".png"}[fmt]
    candidate = folder / (source.stem + extension)
    index = 2
    while candidate.exists():
        candidate = folder / f"{source.stem}-{index}{extension}"
        index += 1
    return candidate


def write_report(folder: str | Path, records: list[dict[str, Any]], errors: list[dict[str, str]], settings: ExportSettings) -> Path:
    folder = Path(folder)
    report = {"format": "singularity.export-report.v1", "created_at": datetime.now(timezone.utc).isoformat(),
              "settings": asdict(settings.normalized()), "success": len(records), "errors": errors,
              "before_bytes": sum(x["before_bytes"] for x in records), "after_bytes": sum(x["after_bytes"] for x in records),
              "files": records}
    target = folder / "singularity-export-report.json"
    fd, temp_name = tempfile.mkstemp(prefix=".report-", suffix=".json", dir=folder)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    os.replace(temp_name, target)
    return target


class Presets:
    """Small JSON store with a built-in web, print-preview and archive set."""
    BUILTIN = {
        "WebP web": ExportSettings("webp", 80, 2560, 1440, 72),
        "JPEG boutique": ExportSettings("jpeg", 88, 3000, 3000, 72),
        "PNG net": ExportSettings("png", 100, 4096, 4096, 72),
    }

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "Existence/singularity/presets.json"

    def load(self) -> dict[str, ExportSettings]:
        result = dict(self.BUILTIN)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for name, values in raw.get("presets", {}).items(): result[name] = ExportSettings(**values).normalized()
        except (OSError, ValueError, TypeError): pass
        return result

    def save(self, name: str, settings: ExportSettings) -> None:
        if not name.strip(): raise ValueError("Preset name is required")
        current = {key: asdict(value) for key, value in self.load().items() if key not in self.BUILTIN}
        current[name.strip()] = asdict(settings.normalized())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".presets-", suffix=".json", dir=self.path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as handle: json.dump({"format": "singularity.presets.v1", "presets": current}, handle, indent=2)
        os.replace(temporary, self.path)
