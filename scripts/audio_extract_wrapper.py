#!/usr/bin/env python3
"""OPP Audio/Video extraction using Python 3.11 (Hermes venv).

This script wraps OPP's AudioExtractor/VideoExtractor in a subprocess
that runs under Python 3.11 (Hermes venv) where faster-whisper and all
its ML dependencies are natively available.

Usage:
    python3 audio_extract.py <input_path> <output_dir>
"""

import sys, json, subprocess

HERMES_PYTHON = "/home/renanzai/.hermes/hermes-agent/venv/bin/python3"
OPP_SRC = "/mnt/d/Hermes-Workspace/01-Projects/Omni_Pre_Processor/src"

WRAPPER_SCRIPT = """
import sys, os, json
sys.path.insert(0, "{opp_src}")
os.environ.setdefault("HOME", "/home/renanzai")

input_path = sys.argv[1]
output_dir = sys.argv[2]
os.makedirs(output_dir, exist_ok=True)

from pathlib import Path
import whisper

ext = Path(input_path).suffix.lower()
model = whisper.load_model("tiny")

print(f"Transcribing {{input_path}}...", file=sys.stderr)
result = model.transcribe(str(input_path))
text = result.get("text", "").strip()

output_md = Path(output_dir) / f"{{Path(input_path).stem}}.md"
output_md.write_text(text, encoding="utf-8")

manifest = {{
    "file": str(input_path),
    "format": ext,
    "char_count": len(text),
    "language": result.get("language", "?"),
    "segments": len(result.get("segments", [])),
}}
json.dump(manifest, open(Path(output_dir) / "manifest.json", "w"), indent=2)
print(json.dumps(manifest))
""".format(opp_src=OPP_SRC)

def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input_path> <output_dir>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2]

    cmd = [HERMES_PYTHON, "-c", WRAPPER_SCRIPT, input_path, output_dir]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        print(f"STDERR: {result.stderr[:500]}", file=sys.stderr)
        print(f"STDOUT: {result.stdout[:500]}")
        sys.exit(result.returncode)

    print(result.stdout)
    try:
        manifest = json.loads(result.stdout)
        if manifest.get("error"):
            print(f"ERROR: {manifest['error']}", file=sys.stderr)
            sys.exit(1)
        print(f"OK: {manifest.get('char_count', 0)} chars extracted")
    except json.JSONDecodeError:
        print(result.stdout)

if __name__ == "__main__":
    main()
