#!/usr/bin/env python3
"""Comprehensive DOCX quality verification."""
from zipfile import ZipFile, BadZipFile
import re
import hashlib
from collections import Counter
import sys

SRC = "/tmp/e2e-level2/爱上海尔_第二章_全球创牌.docx"
TGT = "/tmp/e2e-level2/output/xliff/爱上海尔_第二章_全球创牌_EN.docx"

# ========== 1. LOAD BOTH DOCX ==========
try:
    src_zip = ZipFile(SRC, 'r')
    src_names = src_zip.namelist()
    print(f"[SRC] Loaded: {SRC} ({len(src_names)} entries)")
except BadZipFile as e:
    print(f"[SRC] ERROR: {e}")
    sys.exit(1)

try:
    tgt_zip = ZipFile(TGT, 'r')
    tgt_names = tgt_zip.namelist()
    print(f"[TGT] Loaded: {TGT} ({len(tgt_names)} entries)")
except BadZipFile as e:
    print(f"[TGT] ERROR: {e}")
    sys.exit(1)

# ========== 2. IMAGE VERIFICATION ==========
print("\n" + "=" * 70)
print("1. IMAGE VERIFICATION")
print("=" * 70)

src_imgs = sorted([n for n in src_names if n.startswith('word/media/')])
tgt_imgs = sorted([n for n in tgt_names if n.startswith('word/media/')])

print(f"\nSource images: {len(src_imgs)}")
print(f"Target images: {len(tgt_imgs)}")

src_img_set = set(src_imgs)
tgt_img_set = set(tgt_imgs)

common = src_img_set & tgt_img_set
missing_from_tgt = src_img_set - tgt_img_set
extra_in_tgt = tgt_img_set - src_img_set

print(f"\nCommon images (same name): {len(common)}")
print(f"Missing from target: {len(missing_from_tgt)}")
print(f"Extra in target: {len(extra_in_tgt)}")

# Check file hashes for common images
hash_mismatches = []
for img in sorted(common):
    src_data = src_zip.read(img)
    tgt_data = tgt_zip.read(img)
    src_hash = hashlib.md5(src_data).hexdigest()[:12]
    tgt_hash = hashlib.md5(tgt_data).hexdigest()[:12]
    if src_hash != tgt_hash:
        hash_mismatches.append((img, src_hash, tgt_hash))

if hash_mismatches:
    print(f"\n⚠ Hash mismatches ({len(hash_mismatches)}):")
    for name, sh, th in hash_mismatches:
        s = src_zip.getinfo(name).file_size
        t = tgt_zip.getinfo(name).file_size
        print(f"  {name}: src={sh}({s}B) tgt={th}({t}B)")
else:
    print(f"\n✅ All {len(common)} common images have identical content (MD5 match)")

if missing_from_tgt:
    print("\n⚠ Missing from target:")
    for img in sorted(missing_from_tgt):
        print(f"  - {img} ({src_zip.getinfo(img).file_size} bytes in source)")

# Count by extension
src_ext = Counter(n.split('.')[-1] for n in src_imgs)
tgt_ext = Counter(n.split('.')[-1] for n in tgt_imgs)
print(f"\nSource image types: {dict(src_ext)}")
print(f"Target image types: {dict(tgt_ext)}")

# ========== 3. IMAGE POSITION ==========
print("\n" + "=" * 70)
print("2. IMAGE POSITION (drawing elements in document.xml)")
print("=" * 70)

src_doc = src_zip.read('word/document.xml').decode('utf-8')
tgt_doc = tgt_zip.read('word/document.xml').decode('utf-8')

def extract_image_refs(doc_xml):
    """Extract image references from document.xml in order of appearance."""
    blips = re.findall(r'<a:blip[^>]*r:embed="([^"]+)"[^>]*/>', doc_xml)
    return blips

def get_rels(zip_file):
    """Get relationships mapping rId to target path."""
    try:
        rels_xml = zip_file.read('word/_rels/document.xml.rels').decode('utf-8')
    except KeyError:
        return {}
    rels = re.findall(
        r'<Relationship[^>]*Id="([^"]+)"[^>]*Target="([^"]+)"[^>]*/>',
        rels_xml
    )
    result = {}
    for rid, target in rels:
        if 'media/' in target.lower():
            result[rid] = target
    return result

src_img_refs = extract_image_refs(src_doc)
tgt_img_refs = extract_image_refs(tgt_doc)

src_rels = get_rels(src_zip)
tgt_rels = get_rels(tgt_zip)

print(f"\nSource image relationships: {len(src_rels)}")
print(f"Target image relationships: {len(tgt_rels)}")

src_rid_to_img = {rid: target for rid, target in src_rels.items()}
tgt_rid_to_img = {rid: target for rid, target in tgt_rels.items()}

# Map rIds to filenames preserving document order
src_order = []
for rid in src_img_refs:
    src_order.append(src_rid_to_img.get(rid, f"UNKNOWN:{rid}"))

tgt_order = []
for rid in tgt_img_refs:
    tgt_order.append(tgt_rid_to_img.get(rid, f"UNKNOWN:{rid}"))

print(f"\nSource image order ({len(src_order)}):")
for i, img in enumerate(src_order):
    print(f"  [{i+1:2d}] {img}")

print(f"\nTarget image order ({len(tgt_order)}):")
for i, img in enumerate(tgt_order):
    print(f"  [{i+1:2d}] {img}")

# Compare order
if src_order == tgt_order:
    print(f"\n✅ Image order identical ({len(src_order)} images)")
else:
    print("\n⚠ Image order differences:")
    # Check if it's just the total count
    if len(src_order) != len(tgt_order):
        print(f"  Count: src={len(src_order)}, tgt={len(tgt_order)}")
    for i, (s, t) in enumerate(zip(src_order, tgt_order)):
        if s != t:
            print(f"  Position {i+1}: src={s} → tgt={t}")

# ========== 4. TRANSLATION QUALITY ==========
print("\n" + "=" * 70)
print("3. TRANSLATION QUALITY (visible text)")
print("=" * 70)

def analyze_text(doc_xml, label):
    texts = re.findall(r'<w:t[^>]*>([^<]*)</w:t>', doc_xml)

    zh_runs = [t for t in texts if re.search(r'[\u4e00-\u9fff]', t)]
    en_runs = [t for t in texts if re.search(r'[a-zA-Z]', t)]

    zh_chars = sum(len(re.findall(r'[\u4e00-\u9fff]', t)) for t in texts)
    en_chars = sum(len(re.findall(r'[a-zA-Z]', t)) for t in texts)

    paras = re.split(r'</w:p>', doc_xml)
    zh_paras = []
    for p in paras:
        p_texts = re.findall(r'<w:t[^>]*>([^<]*)</w:t>', p)
        combined = ''.join(p_texts).strip()
        if combined and re.search(r'[\u4e00-\u9fff]', combined):
            zh_paras.append(combined)

    # Source echo: paragraphs with both ZH and significant EN
    echo_paras = []
    for p in paras:
        p_texts = re.findall(r'<w:t[^>]*>([^<]*)</w:t>', p)
        combined = ''.join(p_texts).strip()
        if combined and re.search(r'[\u4e00-\u9fff]', combined) and re.search(r'[a-zA-Z]{3,}', combined):
            echo_paras.append(combined[:120])

    has_en_prefix = '[en]' in doc_xml or '&#91;en&#93;' in doc_xml

    print(f"\n--- {label} ---")
    print(f"  Total text runs: {len(texts)}")
    print(f"  ZH text runs: {len(zh_runs)}")
    print(f"  EN text runs: {len(en_runs)}")
    print(f"  ZH chars: {zh_chars}")
    print(f"  EN chars: {en_chars}")
    print(f"  Total paragraphs: {len(paras)}")
    print(f"  Paragraphs with ZH: {len(zh_paras)}")
    print(f"  Source echo paragraphs: {len(echo_paras)}")
    print(f"  [en] prefix: {'YES' if has_en_prefix else 'NO'}")

    if zh_paras:
        print("  ⚠ Chinese content samples:")
        for p in zh_paras[:15]:
            print(f"    >>> {p[:100]}")

    if echo_paras:
        print("  ⚠ Source echo samples:")
        for p in echo_paras[:5]:
            print(f"    >>> {p[:120]}")

    return zh_paras, echo_paras

print("### Body Text ###")
src_zh, src_echo = analyze_text(src_doc, "SOURCE (Chinese)")
tgt_zh, tgt_echo = analyze_text(tgt_doc, "TARGET (English)")

# ========== 5. HEADER/FOOTER/TEXTBOX ==========
print("\n" + "=" * 70)
print("4. HEADER / FOOTER / TEXTBOX / SHAPES")
print("=" * 70)

for doc_name, doc_zip in [("SOURCE", src_zip), ("TARGET", tgt_zip)]:
    print(f"\n--- {doc_name} ---")
    for n in sorted(doc_zip.namelist()):
        if any(x in n.lower() for x in ['header', 'footer', 'textbox', 'shape']):
            try:
                xml = doc_zip.read(n).decode('utf-8', errors='replace')
                texts = re.findall(r'>([^<]{2,})<', xml)
                clean_texts = [t.strip() for t in texts if t.strip() and not t.startswith('<?') and not t.startswith('</') and not t.startswith('<w:')]
                if clean_texts:
                    zh = len(re.findall(r'[\u4e00-\u9fff]', xml))
                    en = len(re.findall(r'[a-zA-Z]', xml))
                    print(f"  {n}: ZH={zh}, EN={en}, texts={[t[:60] for t in clean_texts[:5]]}")
            except Exception:
                pass

# ========== 6. FORMATTING ==========
print("\n" + "=" * 70)
print("5. FORMATTING PRESERVATION")
print("=" * 70)

src_bold = len(re.findall(r'<w:b\b', src_doc))
tgt_bold = len(re.findall(r'<w:b\b', tgt_doc))
print(f"Bold markers (w:b): src={src_bold}, tgt={tgt_bold}")

src_italic = len(re.findall(r'<w:i\b', src_doc))
tgt_italic = len(re.findall(r'<w:i\b', tgt_doc))
print(f"Italic markers (w:i): src={src_italic}, tgt={tgt_italic}")

src_links = len(re.findall(r'<w:hyperlink', src_doc))
tgt_links = len(re.findall(r'<w:hyperlink', tgt_doc))
print(f"Hyperlinks: src={src_links}, tgt={tgt_links}")

src_paras = src_doc.count('</w:p>')
tgt_paras = tgt_doc.count('</w:p>')
print(f"Paragraphs: src={src_paras}, tgt={tgt_paras}")

src_tables = src_doc.count('</w:tbl>')
tgt_tables = tgt_doc.count('</w:tbl>')
print(f"Tables: src={src_tables}, tgt={tgt_tables}")

# ========== 7. DETAILED IMAGE ANALYSIS ==========
print("\n" + "=" * 70)
print("6. IMAGE PARAGRAPH CONTEXT")
print("=" * 70)

def get_img_paragraphs(doc_xml, label):
    """Get paragraphs containing images with their text context."""
    paras = re.split(r'</w:p>', doc_xml)
    img_paras = []
    for i, p in enumerate(paras):
        # More reliable: check for blip
        has_blip = 'r:embed' in p and 'media/' in (p[p.find('r:embed'):p.find('r:embed')+80] if 'r:embed' in p else '')
        if not has_blip:
            # Check for drawing
            has_blip = '<w:drawing>' in p
        if has_blip or 'mc:AlternateContent' in p and 'r:embed' in p:
            texts = re.findall(r'<w:t[^>]*>([^<]*)</w:t>', p)
            text = ''.join(texts).strip()[:100]
            # Extract image name from this paragraph
            blip_match = re.search(r'r:embed="([^"]+)"', p)
            img_name = blip_match.group(1) if blip_match else "?"
            img_paras.append((i, img_name, text))
    return img_paras

# Use the rels to get real image names
src_img_paras = get_img_paragraphs(src_doc, "SRC")
tgt_img_paras = get_img_paragraphs(tgt_doc, "TGT")

print(f"\nSource image paragraphs: {len(src_img_paras)}")
print(f"Target image paragraphs: {len(tgt_img_paras)}")

if len(src_img_paras) == len(tgt_img_paras):
    print("✅ Image paragraph count matches")
else:
    print(f"⚠ Count differs: src={len(src_img_paras)}, tgt={len(tgt_img_paras)}")

# Show first/last image paragraphs
print("\nFirst 5 image paragraphs (target):")
for i, (pidx, rid, txt) in enumerate(tgt_img_paras[:5]):
    img_name = tgt_rid_to_img.get(rid, rid)
    print(f"  Para {pidx}: [{img_name}] \"{txt}\"")

print("\nLast 5 image paragraphs (target):")
for i, (pidx, rid, txt) in enumerate(tgt_img_paras[-5:]):
    img_name = tgt_rid_to_img.get(rid, rid)
    print(f"  Para {pidx}: [{img_name}] \"{txt}\"")

# ========== 8. SUMMARY ==========
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

checks = []

# Image count
if len(src_imgs) == len(tgt_imgs):
    checks.append(("Image count", f"✓ {len(tgt_imgs)}/{len(src_imgs)}", True))
else:
    checks.append(("Image count", f"⚠ {len(tgt_imgs)} vs src {len(src_imgs)}", False))

# Image content
all_match = len(hash_mismatches) == 0 and len(missing_from_tgt) == 0 and len(extra_in_tgt) == 0
if all_match:
    checks.append(("Image content", f"✓ All {len(common)} identical (MD5)", True))
else:
    issues = []
    if hash_mismatches: issues.append(f"{len(hash_mismatches)} hash mismatch")
    if missing_from_tgt: issues.append(f"{len(missing_from_tgt)} missing")
    if extra_in_tgt: issues.append(f"{len(extra_in_tgt)} extra")
    checks.append(("Image content", f"⚠ {', '.join(issues)}", False))

# Image order
if len(src_order) == len(tgt_order) and src_order == tgt_order:
    checks.append(("Image order", f"✓ {len(src_order)} images in same order", True))
elif len(src_order) == len(tgt_order):
    checks.append(("Image order", f"⚠ {len(src_order)} images, order differs", False))
else:
    checks.append(("Image order", f"⚠ src={len(src_order)}, tgt={len(tgt_order)}", False))

# ZH in target visible text
if len(tgt_zh) == 0:
    checks.append(("ZH residual (text)", "✓ 0 Chinese paragraphs", True))
else:
    checks.append(("ZH residual (text)", f"⚠ {len(tgt_zh)} paragraphs", False))

# Source echo
if len(tgt_echo) == 0:
    checks.append(("Source echo", "✓ None", True))
else:
    checks.append(("Source echo", f"⚠ {len(tgt_echo)} paragraphs", False))

# [en] prefix
has_en = '[en]' in tgt_doc or '&#91;en&#93;' in tgt_doc
checks.append(("[en] prefix", f"{'✓ None' if not has_en else '⚠ Found'}", not has_en))

# Bold count
bold_ok = abs(src_bold - tgt_bold) / max(src_bold, 1) * 100 < 20
checks.append(("Bold", f"src={src_bold}, tgt={tgt_bold}", bold_ok))

# Table count
checks.append(("Tables", f"src={src_tables}, tgt={tgt_tables}", src_tables == tgt_tables))

# Paragraph count
para_ok = abs(src_paras - tgt_paras) / max(src_paras, 1) * 100 < 5
checks.append(("Paragraphs", f"src={src_paras}, tgt={tgt_paras}", para_ok))

# Image paragraph count match
ip_ok = len(src_img_paras) == len(tgt_img_paras)
checks.append(("Img paragraphs", f"src={len(src_img_paras)}, tgt={len(tgt_img_paras)}", ip_ok))

print(f"\n{'Check':<30} {'Result':<45} {'Status':<8}")
print("-" * 85)
passed = 0
total = 0
all_pass = True
for name, result, ok in checks:
    total += 1
    if ok:
        passed += 1
    else:
        all_pass = False
    print(f"{name:<30} {result:<45} {'✅' if ok else '❌'}")
print("-" * 85)
print(f"\nPassed: {passed}/{total} ({passed/total*100:.0f}%)")
if all_pass:
    print("🎉 ALL CHECKS PASSED")
else:
    print(f"⚠ {total - passed} check(s) failed")

src_zip.close()
tgt_zip.close()
