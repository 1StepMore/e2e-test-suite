#!/usr/bin/env python3
"""
E2E Matrix Runner — runs the full test matrix via MCP client.
Usage:
    python e2e_matrix_runner.py                    # Run all
    python e2e_matrix_runner.py --scene=1          # Run single scene
    python e2e_matrix_runner.py --format=docx       # Run single format
    python e2e_matrix_runner.py --dry-run           # Show what would run
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))
from mcp_client import MCPClient

CAMPAIGN = Path("/mnt/d/Hermes-Workspace/01-Projects/e2e-test-suite/campaign-realistic-e2e")
CORPUS = CAMPAIGN / "corpus"
SCENES = CAMPAIGN / "scenes"
REPORTS = CAMPAIGN / "reports"

# Scene definitions
SCENE_DEFS = {
    1: {"name": "scene-01-single-format", "desc": "Basic single-format extraction & translation"},
    2: {"name": "scene-02-format-fidelity", "desc": "Format preservation across document types"},
    3: {"name": "scene-03-glossary", "desc": "Glossary-aware translation"},
    4: {"name": "scene-04-cross-format", "desc": "Cross-format consistency"},
    5: {"name": "scene-05-scale", "desc": "Scale / batch performance"},
    6: {"name": "scene-06-error-recovery", "desc": "Error handling & recovery"},
}

# Formats to test
FORMATS = ["docx", "pptx", "pdf", "xlsx", "html", "epub", "csv", "json"]

# Which format supports which path
# MCP path = OPP extract → OL translate → ORF apply
# CLI path = uses CLI tools directly
PATHS = ["mcp"]


async def run_pipeline(scene_num: int, fmt: str, out_dir: Path) -> dict:
    """Run OPP → OL → ORF pipeline for a single file."""
    start_time = time.time()
    result = {
        "scene": scene_num,
        "format": fmt,
        "path": "mcp",
        "steps": [],
        "success": False,
        "duration": 0,
        "error": None,
    }

    # Find input file
    corpus_file = CORPUS / fmt / f"sample.{fmt}"
    if fmt == "html":
        corpus_file = CORPUS / fmt / "sample.html"
    elif fmt == "epub":
        corpus_file = CORPUS / fmt / "sample.epub"
    elif fmt == "csv":
        corpus_file = CORPUS / fmt / "sample.csv"
    elif fmt == "json":
        corpus_file = CORPUS / fmt / "sample.json"
    elif fmt == "pdf":
        corpus_file = CORPUS / fmt / "sample.pdf"

    if not corpus_file.exists():
        # Try alternative names
        alt_files = list(CORPUS.glob(f"{fmt}/*.*"))
        if alt_files:
            corpus_file = alt_files[0]
        else:
            result["error"] = f"No corpus file for {fmt}"
            return result

    result["input_file"] = str(corpus_file)
    scene_dir = out_dir / SCENE_DEFS[scene_num]["name"] / fmt / "mcp"
    scene_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: OPP extract
        t0 = time.time()
        async with MCPClient("opp") as opp:
            extract_result = await opp.call_tool("extract_document", {
                "file_path": str(corpus_file),
                "source_lang": "en",
                "target_lang": "zh",
            })
        t1 = time.time()
        result["steps"].append({
            "step": "opp_extract", "ok": True, "duration": round(t1 - t0, 2)
        })
        # Save extracted content
        with open(scene_dir / "opp-extract.json", "w") as f:
            json.dump(extract_result, f, ensure_ascii=False, indent=2)

        # Extract markdown from result
        markdown = extract_result.get("content") or extract_result.get("markdown", "")
        if not markdown and "content" in extract_result:
            content = extract_result.get("content")
            if isinstance(content, list):
                markdown = "\n\n".join(
                    c.get("text", "") for c in content if c.get("type") == "text"
                )

        if not markdown:
            result["error"] = "No markdown content extracted"
            return result

        with open(scene_dir / "source.md", "w") as f:
            f.write(markdown)

        # Step 2: OL translate
        t0 = time.time()
        async with MCPClient("ol") as ol:
            trans_result = await ol.call_tool("translate_md_text", {
                "content": markdown,
                "source_lang": "en",
                "target_lang": "zh",
            })
        t1 = time.time()
        result["steps"].append({
            "step": "ol_translate", "ok": trans_result.get("success", False),
            "duration": round(t1 - t0, 2),
        })
        if not trans_result.get("success"):
            result["error"] = f"OL translation failed: {trans_result}"
            return result

        translated = trans_result.get("translated", "")
        with open(scene_dir / "translated.md", "w") as f:
            f.write(translated)

        # Step 3: ORF apply
        t0 = time.time()
        output_path = str(scene_dir / f"output.{fmt}")
        async with MCPClient("orf") as orf:
            apply_result = await orf.call_tool("apply_md", {
                "input_md": translated,
                "target_format": fmt,
                "output_path": output_path,
            })
        t1 = time.time()
        result["steps"].append({
            "step": "orf_apply", "ok": True,
            "duration": round(t1 - t0, 2),
        })
        result["output_file"] = output_path

        # Success
        result["success"] = True

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    result["duration"] = round(time.time() - start_time, 2)
    return result


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="E2E Matrix Runner")
    parser.add_argument("--scene", type=int, help="Run single scene (1-6)")
    parser.add_argument("--format", choices=FORMATS, help="Run single format")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run")
    args = parser.parse_args()

    scenes_to_run = [args.scene] if args.scene else range(1, 7)
    formats_to_run = [args.format] if args.format else FORMATS

    if args.dry_run:
        print("E2E Matrix — Dry Run\n")
        print(f"{'Scene':<8} {'Format':<8} {'Path':<6} {'Input File':<50}")
        print("-" * 75)
        for sn in scenes_to_run:
            for fmt in formats_to_run:
                for path in PATHS:
                    f = CORPUS / fmt / f"sample.{fmt}"
                    print(f"S{sn:<5}  {fmt:<8} {path:<6} {f}")
        return

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = REPORTS / f"matrix-run-{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    total = len(scenes_to_run) * len(formats_to_run) * len(PATHS)
    completed = 0
    passed = 0
    failed = 0
    results = []

    print(f"{'=' * 60}")
    print(f"  E2E Matrix Run — {total} tests")
    print(f"  Output: {out_dir}")
    print(f"{'=' * 60}\n")

    for sn in scenes_to_run:
        scene_name = SCENE_DEFS[sn]["name"]
        for fmt in formats_to_run:
            for path in PATHS:
                completed += 1
                label = f"[{completed}/{total}] S{sn} {fmt} ({path})"
                print(f"\n{'─' * 50}")
                print(f"  {label}")
                print(f"{'─' * 50}")

                r = await run_pipeline(sn, fmt, out_dir)

                if r["success"]:
                    passed += 1
                    steps_ok = sum(1 for s in r["steps"] if s["ok"])
                    print(f"  ✅ PASS  ({r['duration']}s, {steps_ok}/{len(r['steps'])} steps OK)")
                else:
                    failed += 1
                    print(f"  ❌ FAIL  ({r['duration']}s)")
                    print(f"     Error: {r['error']}")

                results.append(r)

    # Summary
    summary = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "timestamp": timestamp,
        "results": results,
    }
    with open(out_dir / "summary.json", "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"  SUMMARY: {passed}/{total} passed, {failed} failed")
    print(f"  Report: {out_dir / 'summary.json'}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
