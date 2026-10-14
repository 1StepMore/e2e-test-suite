#!/usr/bin/env python3
"""Diagnostic: Test why Units 2 and 7 get empty targets in OL batch translation."""
import asyncio, sys, os, json, tempfile
from pathlib import Path

E2E_ROOT = Path("/mnt/d/Hermes-Workspace/01-Projects/e2e-test-suite")
sys.path.insert(0, str(E2E_ROOT / "src" / "Omni_Localizer" / "src"))
os.chdir(E2E_ROOT)

UNITS = {
    "1": "\u300a\u7231\u4e0a\u6d77\u5c14\u300b<bx id=\"1\" type=\"bold\"/><ex id=\"1\"/>",
    "2": "\u5168\u7403\u521b\u724c<bx id=\"1\" type=\"bold\"/><ex id=\"1\"/><bx id=\"2\" type=\"bold\"/><ex id=\"2\"/><bx id=\"3\" type=\"bold\"/><ex id=\"3\"/><bx id=\"4\" type=\"bold\"/><ex id=\"4\"/>",
    "3": "\u521b\u51fa\u4e00\u4e2a\u5168\u7403\u5316\u4f01\u4e1a\u3001\u4e16\u754c\u7ea7\u54c1\u724c<bx id=\"1\" type=\"bold\"/><ex id=\"1\"/>",
    "4": "\u6539\u9769\u5f00\u653e\u4ee5\u6765\uff0c\u4e2d\u56fd\u4f01\u4e1a\u201c\u51fa\u6d77\u201d\u5df2\u8d70\u8fc7\u6570\u5341\u5e74\u5386\u7a0b\u3002",
    "5": "\u5386\u7ecf40\u5e74\u521b\u4e1a\u53d1\u5c55\uff0c\u6d77\u5c14\u6301\u7eed\u805a\u7126\u79d1\u6280\u81ea\u4e3b\u521b\u65b0\uff0c\u4ee5\u7528\u6237\u4e3a\u4e2d\u5fc3\uff0c\u575a\u5b9a\u4e0d\u79fb\u5730\u63a8\u8fdb\u5168\u7403\u521b\u724c\u6218\u7565\uff0c\u5f15\u9886\u5168\u7403\u5bb6\u7535\u884c\u4e1a\u7684\u98ce\u5411\u6807\uff0c\u521b\u51fa\u4e86\u4e00\u4e2a\u5168\u7403\u5316\u4f01\u4e1a\u3001\u4e16\u754c\u7ea7\u54c1\u724c\u3002",
    "6": "40\u5e74\u6765\uff0c\u6d77\u5c14\u7684\u5168\u7403\u54c1\u724c\u521b\u5efa\u5386\u7a0b\u4e3a\u4e2d\u56fd\u4f01\u4e1a\u51fa\u6d77\u63d0\u4f9b\u4e86\u6709\u76ca\u5019\u9274\u3002",
    "7": "  #46",
    "8": "\u201c\u6d77\u5c14\u51fa\u6d77\u90a3\u5e74\uff0c\u6211\u4eec\u505a\u597d\u4e86\u8270\u82e6\u5358\u7edd\u7684\u5fc3\u7406\u51c6\u5907\uff0c\u56e0\u4e3a\u8fd9\u6761\u8def\u6ce8\u5b9a\u8981\u54ac\u7259\u575a\u6301\u5f88\u4e45\u3002\u201d",
    "9": "\u6df1\u8015\u5168\u7403\u521b\u724c\u4e4b\u8def\uff0c\u6d77\u5c14\u5b9e\u73b0\u4e86\u5404\u4e2a\u533a\u57df\u7684\u5168\u7403\u5f15\u9886\uff0c\u6210\u4e3a\u5168\u7403\u5404\u5927\u4e3b\u6d41\u56fd\u5bb6\u3001\u4e3b\u6d41\u5e02\u573a\u7684\u4e3b\u6d41\u54c1\u724c\u3002",
}

EXPECTED_OK = {"1", "3"}
EXPECTED_EMPTY = {"2", "4", "5", "6", "7", "8", "9"}

async def test_unit(pool, uid, source):
    try:
        result = await pool.translate(source, "zh", "en", context=None)
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in result)
        return {"unit_id": uid, "result": result[:80], "full_result": result,
                "has_chinese": has_chinese, "success": bool(result and not has_chinese), "error": None}
    except Exception as e:
        return {"unit_id": uid, "result": "", "full_result": "", "has_chinese": False, "success": False, "error": str(e)[:100]}

async def test_all():
    from ol_pool.router import ModelPool
    config_path = str(E2E_ROOT / "src" / "Omni_Localizer" / "config" / "default.yaml")
    pool = ModelPool.get_instance(config_path)
    results = {}
    for uid in sorted(UNITS.keys()):
        print(f"Testing unit {uid}...", flush=True)
        r = await test_unit(pool, uid, UNITS[uid])
        results[uid] = r
        print(f"  Result: {repr(r['result'][:60])}")
        if r['error']:
            print(f"  ERROR: {r['error']}")
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"{'Unit':<6} {'Chars':<6} {'ExpectedOK':<12} {'GotOK':<12} {'Match'}")
    print("-"*60)
    for uid in sorted(UNITS.keys()):
        r = results[uid]
        chars = len(UNITS[uid])
        expected_ok = uid in EXPECTED_OK
        got_ok = r['success']
        match = "OK" if expected_ok == got_ok else "MISMATCH"
        print(f"  {uid:<6} {chars:<6} {str(expected_ok):<12} {str(got_ok):<12} {match}")
    
    out_path = Path(tempfile.gettempdir()) / "ol_unit_diag_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nResults: {out_path}")
    return results

if __name__ == "__main__":
    results = asyncio.run(test_all())
