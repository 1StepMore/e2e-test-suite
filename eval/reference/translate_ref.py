"""D1 reference LLM translator (Phase D1, step 2).

Translates each source doc with the reference LLM (deepseek-v4-flash,
the highest-priority model in the pool). Stores translations as
{doc_id}_reference.{ext}.

Per the plan: "Reference LLM must be held out from the active
translation pool" — this is documented but not enforced here
(deferred to D1 hardening pass).

Run: python -m eval.reference.translate_ref
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

REFERENCE_DIR = Path(__file__).parent

REFERENCE_MODEL = "deepseek-v4-flash"


def load_sources() -> list[dict]:
    """Load all source docs with their metadata."""
    docs = []
    for meta_path in REFERENCE_DIR.rglob("*_meta.json"):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        cat_dir = meta_path.parent
        ext = {"docx": "txt", "md": "md", "eml": "eml",
               "ipynb": "py", "csv": "csv", "xml": "xml"}.get(meta["fmt"], "txt")
        source_path = cat_dir / f"{meta['doc_id']}_source.{ext}"
        if source_path.exists():
            meta["source_text"] = source_path.read_text(encoding="utf-8")
            meta["source_path"] = source_path
            meta["ref_ext"] = ext
            docs.append(meta)
    return sorted(docs, key=lambda d: d["doc_id"])


async def translate_all(docs: list[dict]) -> int:
    """Translate all docs with the reference LLM."""
    from ol_pool.router import ModelPool

    config_path = os.environ.get(
        "OL_CONFIG_PATH",
        str(REFERENCE_DIR.parent.parent / "Omni_Localizer" / "config" / "local.yaml"),
    )
    pool = ModelPool.get_instance(config_path=config_path)
    success = 0
    for doc in docs:
        ref_path = doc["source_path"].parent / f"{doc['doc_id']}_reference.{doc['ref_ext']}"
        if ref_path.exists():
            print(f"  [skip] {doc['doc_id']} (reference already exists)")
            success += 1
            continue
        try:
            translation = await pool.translate(
                text=doc["source_text"],
                source_lang=doc["source_lang"],
                target_lang=doc["target_lang"],
            )
            ref_path.write_text(translation, encoding="utf-8")
            print(f"  [ok]   {doc['doc_id']} -> {ref_path.name}")
            success += 1
        except Exception as e:
            print(f"  [FAIL] {doc['doc_id']}: {e}")
    return success


def main():
    docs = load_sources()
    print(f"Found {len(docs)} source docs to translate")
    print(f"Reference model: {REFERENCE_MODEL}")
    print()

    n = asyncio.run(translate_all(docs))
    print(f"\nDone: {n}/{len(docs)} translated successfully")
    if n < len(docs):
        sys.exit(1)


if __name__ == "__main__":
    main()
