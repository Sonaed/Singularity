#!/usr/bin/env python3
"""Bridge headless de Singularity pour le transport Existence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from static_export import ExportSettings, export_image


def convert_image_file(source: str, destination: str, quality: int = 82, output_format: str | None = None) -> dict:
    """Static export without loading Singularity's Qt interface."""
    fmt = output_format or Path(destination).suffix.lstrip(".") or "webp"
    return export_image(source, destination, ExportSettings(format=fmt, quality=quality))


ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / "existence-manifest.json").read_text(encoding="utf-8"))


def response(request: dict, ok: bool, **body) -> dict:
    return {"protocol": "existence.singularity.v1", "request_id": request.get("request_id"), "ok": ok, **body}


def handle(request: dict) -> dict:
    message = str(request.get("message", request.get("type", "")))
    payload = request.get("payload") or {}
    if message == "handshake":
        return response(request, True, handshake=True, app="singularity", manifest=MANIFEST, transport="process-json-lines")
    if message == "ping":
        return response(request, True, message="pong", app="singularity")
    if message in {"describe", "get_state"}:
        return response(request, True, app="singularity", manifest=MANIFEST)
    if message == "close":
        return response(request, True, lifecycle_state="closed")
    if message != "process_resource":
        return response(request, False, error=f"unsupported message: {message}", accepted_messages=["process_resource", "send_resource"])
    source = payload.get("physical_path") or payload.get("source")
    destination = payload.get("destination")
    if source and destination:
        try:
            report = convert_image_file(source, destination, int(payload.get("quality", 82)), payload.get("format"))
            return response(request, True, processed=True, resource=payload.get("resource", ""), destination=report["destination"], report=report)
        except (OSError, ValueError, RuntimeError) as exc:
            return response(request, False, error=str(exc))
    return response(request, True, processed=False, disposition="deferred", resource=payload.get("resource", ""))


for line in sys.stdin:
    try:
        request = json.loads(line)
        result = handle(request if isinstance(request, dict) else {})
    except (ValueError, TypeError) as exc:
        result = {"protocol": "existence.singularity.v1", "ok": False, "error": str(exc)}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()
