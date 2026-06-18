"""D1 reference set builder (Phase D1, 20 docs).

Generates 20 synthetic source documents across 9 categories and
language pairs. Translates each with the reference LLM (currently
deepseek-v4-flash, held out from the active translation pool).

Run: python -m eval.reference.build
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

REFERENCE_DIR = Path(__file__).parent

CATEGORIES = [
    ("legal_zh_en", "zh", "en", "docx", 3),
    ("legal_en_zh", "en", "zh", "docx", 2),
    ("product_catalog_zh", "zh", "en", "md", 3),
    ("literature_en", "en", "zh", "docx", 2),
    ("technical_doc_en", "en", "zh", "md", 2),
    ("email_mixed", "mixed", "en", "eml", 2),
    ("notebook_en", "en", "zh", "ipynb", 2),
    ("csv_zh", "zh", "en", "csv", 2),
    ("xml_en", "en", "zh", "xml", 2),
]


@dataclass
class DocSpec:
    doc_id: str
    category: str
    source_lang: str
    target_lang: str
    fmt: str
    source_text: str


SYNTHETIC_SOURCES = {
    "legal_zh_en": [
        "本协议自双方签署之日起生效，有效期为三年。",
        "甲方有权在合同期限内对乙方的履约情况进行监督检查。",
        "任何因本协议引起的争议应通过友好协商解决。",
    ],
    "legal_en_zh": [
        "This Agreement shall be governed by the laws of the State of California.",
        "The parties agree to submit any disputes to binding arbitration.",
    ],
    "product_catalog_zh": [
        "智能冰箱：容量500升，能效等级一级，支持手机远程控制。",
        "变频空调：制冷量3500瓦，制热量4200瓦，静音设计。",
        "滚筒洗衣机：洗涤容量10公斤，烘干容量7公斤，14种洗涤程序。",
    ],
    "literature_en": [
        "It was the best of times, it was the worst of times.",
        "All happy families are alike; each unhappy family is unhappy in its own way.",
    ],
    "technical_doc_en": [
        "The API endpoint accepts JSON payloads and returns results in under 100ms.",
        "Configure the load balancer to distribute traffic across three availability zones.",
    ],
    "email_mixed": [
        "Subject: Meeting Tomorrow\nHi team, let's meet at 3pm to discuss the Q4 roadmap.",
        "Subject: Project Update\nThe deployment is on track for Friday. Please review the PR.",
    ],
    "notebook_en": [
        "# Data Analysis\nimport pandas as pd\ndf = pd.read_csv('data.csv')\nprint(df.describe())",
        "# Model Training\nfrom sklearn.ensemble import RandomForestClassifier\nmodel = RandomForestClassifier()",
    ],
    "csv_zh": [
        "产品,价格,库存\n冰箱,5999,150\n洗衣机,3999,200\n空调,2999,300",
        "日期,销售额,订单数\n2024-01,100000,500\n2024-02,120000,600",
    ],
    "xml_en": [
        "<config><database host='localhost' port='5432'/><cache ttl='3600'/></config>",
        "<workflow id='wf-001'><step name='extract'/><step name='transform'/></workflow>",
    ],
}


def generate_sources() -> list[DocSpec]:
    """Generate all 20 source docs."""
    docs = []
    for category, src_lang, tgt_lang, fmt, count in CATEGORIES:
        sources = SYNTHETIC_SOURCES.get(category, [])
        for i, text in enumerate(sources[:count]):
            doc_id = f"{category}_{i+1:02d}"
            docs.append(DocSpec(
                doc_id=doc_id,
                category=category,
                source_lang=src_lang,
                target_lang=tgt_lang,
                fmt=fmt,
                source_text=text,
            ))
    return docs


def save_sources(docs: list[DocSpec]) -> None:
    """Save source docs to disk."""
    for doc in docs:
        cat_dir = REFERENCE_DIR / doc.category
        cat_dir.mkdir(parents=True, exist_ok=True)
        ext = {"docx": "txt", "md": "md", "eml": "eml",
               "ipynb": "py", "csv": "csv", "xml": "xml"}.get(doc.fmt, "txt")
        source_path = cat_dir / f"{doc.doc_id}_source.{ext}"
        source_path.write_text(doc.source_text, encoding="utf-8")
        meta_path = cat_dir / f"{doc.doc_id}_meta.json"
        meta_path.write_text(json.dumps({
            "doc_id": doc.doc_id,
            "source_lang": doc.source_lang,
            "target_lang": doc.target_lang,
            "fmt": doc.fmt,
        }, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(docs)} source docs to {REFERENCE_DIR}")


def main():
    docs = generate_sources()
    print(f"Generated {len(docs)} synthetic source docs")
    print(f"By category: {dict((c, sum(1 for d in docs if d.category == c)) for c, *_ in CATEGORIES)}")
    save_sources(docs)
    print("\nNext step: run translate_with_reference_llm.py to generate references")


if __name__ == "__main__":
    main()
