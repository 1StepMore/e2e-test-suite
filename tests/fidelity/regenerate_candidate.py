"""Regenerate the Alice ch1 candidate via real LLM (Zhipu, para-by-para).

Used by `make fidelity-nightly`. Requires ZHIPU_API_KEY in .env.
Output: test_artifacts/ol/alice_ch1_zhipu_real.md
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE = REPO_ROOT / "test_corpus" / "real" / "cc0_02_gutenberg_alice_ch1.txt"
OUTPUT = REPO_ROOT / "test_artifacts" / "ol" / "alice_ch1_zhipu_real.md"


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass

    if not os.environ.get("ZHIPU_API_KEY"):
        print("FAIL: ZHIPU_API_KEY not set in .env", file=sys.stderr)
        return 1

    zhipu_key = os.environ["ZHIPU_API_KEY"]
    if zhipu_key.startswith("sk-dummy") or zhipu_key.startswith("nvapi-dummy"):
        print(
            "SKIP: ZHIPU_API_KEY is a dummy placeholder (sk-dummy / nvapi-dummy). "
            "Real Zhipu regeneration requires a valid production key. "
            "fidelity-gate still validates the existing test artifact.",
            file=sys.stderr,
        )
        return 0

    sys.path.insert(0, str(REPO_ROOT / "Omni_Localizer" / "src"))
    from ol_mcp.tools import translate_md_text, TranslateInput

    if not SOURCE.exists():
        print(f"FAIL: source not found: {SOURCE}", file=sys.stderr)
        return 1

    raw = SOURCE.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    body = parts[2].strip() if len(parts) >= 3 and parts[0].strip() == "" else raw
    body = re.sub(r"^#+\s.*$", "", body, flags=re.MULTILINE)
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip() and p.strip() != "Down the Rabbit-Hole"]

    print(f"Translating {len(paragraphs)} paragraphs via Zhipu...")

    async def translate_all():
        results = []
        for i, p in enumerate(paragraphs):
            r = await translate_md_text(TranslateInput(
                content=p, source_lang="en", target_lang="zh", add_frontmatter=False,
            ))
            rd = json.loads(r) if isinstance(r, str) else r
            if rd.get("success"):
                results.append(rd.get("translated", p))
                if i % 5 == 0:
                    print(f"  [{i+1}/{len(paragraphs)}] done")
            else:
                err = rd.get("error", "?")
                if not isinstance(err, str):
                    err = json.dumps(err, ensure_ascii=False)
                print(f"  [{i+1}] failed: {err[:60]}", file=sys.stderr)
                results.append(p)
        return results

    translated = asyncio.run(translate_all())
    header = "# 爱丽丝梦游仙境 — 第一章\n\n## 兔子洞之旅\n\nDown the Rabbit-Hole\n\n"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(header + "\n\n".join(translated) + "\n", encoding="utf-8")
    chinese = sum(1 for c in OUTPUT.read_text() if "\u4e00" <= c <= "\u9fff")
    print(f"Wrote {OUTPUT} ({chinese} Chinese chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
