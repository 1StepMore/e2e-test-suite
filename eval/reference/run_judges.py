"""D6 multi-judge runner (Phase D6, step 2).

Runs 3 different LLM judges on each doc in the reference set.
Each judge scores 1-5 on adequacy, fluency, terminology, format.
Stores results as JSON for calibration.

Judge models: glm-4-flash (Zhipu), agnes-2.0-flash (Agnes),
              kimi-k2.6 (Moonshot) — all different from the
              reference LLM (deepseek-v4-flash).

Run: python -m eval.reference.run_judges
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

REFERENCE_DIR = Path(__file__).parent

JUDGE_MODELS = ["glm-4-flash", "agnes-2.0-flash", "kimi-k2.6"]

JUDGE_PROMPT = """Score this translation on 4 dimensions (1-5 each).
Output ONLY 4 numbers separated by commas in this exact order:
adequacy,fluency,terminology,format

Source ({src_lang}): {source}
Translation ({tgt_lang}): {translation}

Scores (a,f,t,fmt):"""


def load_reference_set() -> list[dict]:
    """Load all source + reference doc pairs."""
    docs = []
    for meta_path in sorted(REFERENCE_DIR.rglob("*_meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        cat_dir = meta_path.parent
        ext = {"docx": "txt", "md": "md", "eml": "eml",
               "ipynb": "py", "csv": "csv", "xml": "xml"}.get(meta["fmt"], "txt")
        source_path = cat_dir / f"{meta['doc_id']}_source.{ext}"
        ref_path = cat_dir / f"{meta['doc_id']}_reference.{ext}"
        if source_path.exists() and ref_path.exists():
            meta["source_text"] = source_path.read_text(encoding="utf-8")
            meta["reference_text"] = ref_path.read_text(encoding="utf-8")
            docs.append(meta)
    return docs


def parse_scores(raw: str) -> dict[str, int]:
    """Parse '4,5,3,4' into {adequacy: 4, fluency: 5, ...}."""
    numbers = re.findall(r"\d+", raw)
    if len(numbers) < 4:
        return {"adequacy": 0, "fluency": 0, "terminology": 0, "format": 0}
    scores = [max(1, min(5, int(n))) for n in numbers[:4]]
    return {
        "adequacy": scores[0],
        "fluency": scores[1],
        "terminology": scores[2],
        "format": scores[3],
    }


async def judge_doc(pool, doc: dict, model: str) -> dict[str, int]:
    """Run a single judge on a single doc."""
    prompt = JUDGE_PROMPT.format(
        src_lang=doc["source_lang"],
        tgt_lang=doc["target_lang"],
        source=doc["source_text"][:500],
        translation=doc["reference_text"][:500],
    )
    try:
        response = await pool.translate(
            text=prompt,
            source_lang="en",
            target_lang="en",
            temperature=0.0,
        )
        return parse_scores(response)
    except Exception as e:
        print(f"    [WARN] {model} failed on {doc['doc_id']}: {e}")
        return {"adequacy": 0, "fluency": 0, "terminology": 0, "format": 0}


async def run_all_judges(docs: list[dict]) -> list[dict]:
    """Run all 3 judges on all docs. Returns list of per-doc judge results."""
    from ol_pool.router import ModelPool

    config_path = os.environ.get(
        "OL_CONFIG_PATH",
        str(REFERENCE_DIR.parent.parent / "Omni_Localizer" / "config" / "local.yaml"),
    )
    pool = ModelPool.get_instance(config_path=config_path)

    results = []
    for doc in docs:
        print(f"  Judging {doc['doc_id']}...")
        doc_result = {"doc_id": doc["doc_id"], "judges": {}}
        for model in JUDGE_MODELS:
            scores = await judge_doc(pool, doc, model)
            doc_result["judges"][model] = scores
        results.append(doc_result)
    return results


def main():
    docs = load_reference_set()
    print(f"Found {len(docs)} docs in reference set")
    print(f"Judge models: {JUDGE_MODELS}")
    print()

    results = asyncio.run(run_all_judges(docs))

    output_path = REFERENCE_DIR / "judge_results.json"
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved {len(results)} judge results to {output_path}")


if __name__ == "__main__":
    main()
