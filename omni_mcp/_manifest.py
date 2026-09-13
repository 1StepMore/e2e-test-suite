"""Mutation transparency (gap X-03) for the suite orchestrator.

``omni_mcp.translate_file`` shells out to the three module CLIs and writes the
final artifact into its workspace.  It reports ``{outputs: [{path, sha256,
bytes}], sidecars: [...]}`` so an agent can verify the bytes that landed on
disk rather than trusting a path string.  Hash logic mirrors
``orf.mcp.manifest`` (the two packages ship independently and cannot import
each other).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

DEFAULT_SIDECAR_NAMES: tuple[str, ...] = ("images.json", "images.zip")


def file_entry(path: str | Path) -> dict[str, object]:
    """Return ``{path, sha256, bytes}``; a missing file is ``sha256: None``."""
    p = Path(path)
    try:
        data = p.read_bytes()
    except OSError:
        return {"path": str(p), "sha256": None, "bytes": 0}
    return {
        "path": str(p),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def written_files(
    output_path: str | Path | None,
    sidecar_names: tuple[str, ...] = DEFAULT_SIDECAR_NAMES,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Return ``(outputs, sidecars)`` manifests for a finished mutation."""
    if not output_path:
        return [], []
    outputs = [file_entry(output_path)]
    parent = Path(output_path).parent
    sidecars = [
        file_entry(parent / name)
        for name in sidecar_names
        if (parent / name).is_file()
    ]
    return outputs, sidecars
