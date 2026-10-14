#!/usr/bin/env python3
"""TM search service — runs under Python 3.11 (Hermes venv) with full ML support.

Called from the OL MCP server (Python 3.13, where sentence-transformers
is unavailable) via subprocess.

Usage:
    python3 tm_service.py <tmx_path> <source_text> <src_lang> <tgt_lang> [threshold]

Returns JSON on stdout.
"""

import sys, os, json

HERMES_PYTHON = "/home/renanzai/.hermes/hermes-agent/venv/bin/python3"
OL_SRC = "/mnt/d/Hermes-Workspace/01-Projects/Omni_Localizer/src"
OL_SP = "/mnt/d/Hermes-Workspace/01-Projects/Omni_Localizer/.venv/lib/python3.13/site-packages"

TM_SCRIPT = r"""
import sys, os, json

# Critical: Hermes Python 3.11 packages first, THEN OL Python 3.13 packages
# This ensures numpy loaded from Python 3.11, not 3.13
hermes_sp = "/home/renanzai/.hermes/hermes-agent/venv/lib/python3.11/site-packages"
ol_sp = "{ol_sp}"

# OL source path
sys.path.insert(0, "{ol_src}")

# Add packages in correct order: Hermes first (3.11), then specific OL ones
# We need hypomnema/lxml from OL venv, but numpy/sentence-transformers from Hermes venv
# Strategy: add Hermes SP first (with numpy, sentence-transformers, etc.)
#           then add only specific OL packages for hypomnema support

sys.path.insert(0, hermes_sp)

# Add OL sp but remove numpy (let Hermes 3.11 numpy take precedence)
import itertools
for p in os.listdir(ol_sp):
    full = os.path.join(ol_sp, p)
    # Skip numpy — it's a native extension incompatible between 3.11 and 3.13
    if p.startswith("numpy") or p == "numpy":
        continue
    if p.startswith("numpy_") or p.startswith("numpy."):
        continue
    if full not in sys.path:
        sys.path.append(full)

# Now imports
from ol_tm.service import TMService

# Pre-load sentence-transformers model (first call may download)
def search(tmx_path, source_text, src_lang, tgt_lang, threshold):
    try:
        svc = TMService(tmx_path)
        matches = svc.search(source_text, threshold=threshold,
                            src_lang=src_lang, tgt_lang=tgt_lang)
        results = [
            {{
                "source": m.source,
                "target": m.target,
                "score": round(m.similarity, 4),
                "language_pair": m.language_pair,
            }}
            for m in matches
        ]
        return {{
            "success": True,
            "matches": results,
            "count": len(results),
        }}
    except Exception as e:
        return {{
            "success": False,
            "error": str(e),
            "matches": [],
            "count": 0,
        }}

if __name__ == "__main__":
    tmx_path = sys.argv[1]
    source_text = sys.argv[2]
    src_lang = sys.argv[3]
    tgt_lang = sys.argv[4]
    threshold = float(sys.argv[5]) if len(sys.argv) > 5 else 0.85

    result = search(tmx_path, source_text, src_lang, tgt_lang, threshold)
    print(json.dumps(result, ensure_ascii=False))
""".format(ol_src=OL_SRC, ol_sp=OL_SP)

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: tm_service.py <tmx_path> <source_text> [src_lang] [tgt_lang] [threshold]"}))
        sys.exit(1)

    tmx_path = sys.argv[1]
    source_text = sys.argv[2]
    src_lang = sys.argv[3] if len(sys.argv) > 3 else "en"
    tgt_lang = sys.argv[4] if len(sys.argv) > 4 else "zh"
    threshold = float(sys.argv[5]) if len(sys.argv) > 5 else 0.85

    cmd = [HERMES_PYTHON, "-c", TM_SCRIPT, tmx_path, source_text, src_lang, tgt_lang, str(threshold)]
    env = os.environ.copy()
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["HF_HUB_OFFLINE"] = "1"
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)

    if result.returncode != 0:
        error_msg = result.stderr[:500] if result.stderr else "Unknown error"
        print(json.dumps({"success": False, "error": error_msg}))
        sys.exit(result.returncode)

    print(result.stdout.strip())

if __name__ == "__main__":
    import subprocess
    main()
