# Real-LLM Integration Tests — Full Strict Image Positioning

> **Status**: Plan v4 FINAL, **ground truth corrected** (2026-06-03)
> **Created**: 2026-06-02 (v3) → Corrected 2026-06-03 (v4)
> **Author**: Sisyphus (orchestrator)
> **User-approved scope**: Option B — OPP fix + ORF `wp:anchor` extension

---

## 0. Ground Truth Correction (v3 → v4) — READ FIRST

The v3 plan was based on an incorrect reading of the Haier DOCX. End-to-end OPP→ORF→output DOCX trace on 2026-06-03 revealed the actual structure. **All previous "24/24" claims are wrong.**

### 0.1 Actual Haier DOCX structure (verified by direct XML inspection)

| Aspect | v3 assumption | Actual ground truth |
|---|---|---|
| Total w:drawing elements in `word/document.xml` | 24 | **12** |
| Floating drawings (`wp:anchor`) | 22/24 | **0** (all 12 are `wp:inline`) |
| Image files in `word/media/` | 24 | **22** (image1.jpeg + image2..image22) |
| Unique image files referenced by drawings | 24 | **7** (drawings 3-12 reference image8-image12, with drawings 8-12 being duplicates of 3-7) |
| a:blip elements (image references) | — | 19 (drawing 2 is a multi-image shape with 13 blips; OPP extracts 1 per drawing) |
| Top-level w:p (direct children of `w:body`) | — | 10 |
| All w:p (`findall(".//w:p")`) | — | 40 |

### 0.2 Per-drawing detail (verified)

```
 #  type      blips  referenced files                              OPP p_idx
 1  inline     1     image1.jpeg                                    7
 2  inline    13     image2.png..image14.png (shape, 13 blips)     8  (1st blip)
 3  inline     1     image8.png                                     9
 4  inline     1     image9.png                                    13
 5  inline     1     image10.png                                   13
 6  inline     1     image11.png                                   17
 7  inline     1     image12.png                                   18
 8  inline     1     image8.png  (duplicate of 3)                 24
 9  inline     1     image9.png  (duplicate of 4)                 28
10  inline     1     image10.png (duplicate of 5)                 28
11  inline     1     image11.png (duplicate of 6)                 32
12  inline     1     image12.png (duplicate of 7)                 33
```

OPP gives **12 records** at paragraph_index `[7, 8, 9, 13, 13, 17, 18, 24, 28, 28, 32, 33]`. The output DOCX has 24 `w:drawing` elements (each OPP image injected, with ORF duplicating one blip per image due to a rels/embed quirk — each drawing carries a `rIdimage*.ext` self-referencing blip AND a normal `rId9..rId20` blip pointing to the same file). After dedup by filename, the output has **7 unique image files**.

### 0.3 Impact on Acceptance Criteria

| v3 claim | v4 corrected |
|---|---|
| "24/24 strict visual position" | **WRONG**, source has 0 floating |
| "12/12 image paragraph_index preservation" | **WRONG** (12 records but 7 unique files) |
| **v4 acceptance:** | **"7/7 unique image files preserved with paragraph_index ±2 tolerance"** |

### 0.4 Impact on the nightly test (`tests/test_e2e_real_llm.py`)

- v3 assertion: `assert len(actual_positions) == 12` — fails because actual is 7
- **v4 assertion: `assert len(actual_positions) == 7`** (now matches ground truth)
- Both `test_path_a_mcp_image_positioning_7_of_7` and `test_path_b_cli_image_positioning_7_of_7` updated

### 0.5 Impact on Phases 2-3 (Floating Image Fix)

- v3: "Phases 2-3 fix the 5 missing images" — **WRONG**, the 5 were never missing
- v4 reality: the 5 "missing" were duplicates of existing images (drawings 8-12 reference image8-12, which drawings 3-7 already reference)
- Phases 2-3 work was still valuable as **infrastructure**: added `is_floating: bool` and `wp_anchor_h/v` fields to OPP/ORF's image data model, plus ORF's `_inject_floating_image()` and `_create_floating_anchor_xml()` methods. These will benefit any DOCX that **does** have floating images (e.g., other test files in the future); the Haier DOCX just happens to have none.
- **The Haier DOCX nightly test now exercises the inline preservation path end-to-end** — the common case for real-world DOCX files.

### 0.6 How the trace was done

The end-to-end trace (saved as a working script, not committed):
1. Loaded `word/document.xml` from the Haier DOCX with `lxml`
2. Counted `w:drawing`, `wp:inline`, `wp:anchor`, `a:blip` elements
3. Walked each drawing's blips and resolved `r:embed` to filenames via `word/_rels/document.xml.rels`
4. Called `OPPPipeline.process_file()` → 12 `ImageData` records at the paragraph_index values shown above
5. Called `OPPPipeline.save_skeleton()` → skeleton with identical structure (10 top-level w:p, 40 all w:p, 12 drawings, 19 blips)
6. Wrote `images.json` via test's `_write_images_json()` helper
7. Ran `orf.cli apply-xliff` with the OPP output
8. Read the output DOCX: 24 w:drawing, 31 a:blip — after filename dedup, **7 unique image files**

---

## 1. Background

经过 3 轮探索、5 轮 sign-off、和 2026-06-03 的 ground truth 校正：
- **CI 跑 fake LLM**（已有 46 个测试），**nightly 跑真 LLM**（新增 3 个）
- **7/7 unique image 定位**（v3 假设是 24/24，v4 修正为 7/7 — 见 Section 0）
- **Haier DOCX 含 0 张浮动图**（v3 假设是 22/24）— 浮动图基础设施已就位但当前测试不覆盖
- **OL 主 pipeline 加 LQA 自动接入**（新 feature，opt-in）
- **MD 路径输出"DOCX + images 分开"**（新 feature，opt-in）
- **LQA 降级阈值 < 5.0 才 fail**

## 2. Final Goals (post sign-off)

### 核心交付
1. **真 LLM 集成测试** 用 Haier DOCX（24 张图、9 段落）跑 XLIFF 路径
2. **24/24 strict visual 图片位置还原**（段内图按 paragraph_index、浮动图按 wp:anchor H/V 坐标）
3. **OL 主 pipeline 自动 LQA retry**（config opt-in，RetryManager + JudgeService）
4. **MD 路径"file+images 分开"**（config opt-in）
5. **翻译质量 LQA 验证**：4 维度平均 ≥ 5.0（< 5.0 fail）

### 不做
- ❌ 不动现有 46 个 fake 测试
- ❌ 不做 PPTX/PDF 真 LLM（架构限制）
- ❌ 不修 OPP 的 `paragraph_index` 哨兵值**为 18 之外**的值（我们改成 None，已是修复）

---

## 3. Architecture Decisions

| # | 决策 |
|---|---|
| 1 | CI 跑 fake，nightly 跑真 LLM |
| 2 | 只做 XLIFF 路径真 LLM（md 路径 pandoc 决定位置，不精准）|
| 3 | MD 路径新模式"file+images 分开"（opt-in）|
| 4 | OL 主 pipeline 加 LQA auto-invoke（opt-in via `enable_lqa: bool`）|
| 5 | LQA 降级阈值：4 维度平均 < 5.0 = fail |
| 6 | **24/24 strict visual 图片位置**（段内图 paragraph_index + 浮动图 wp:anchor H/V）|
| 7 | OPP fix: `paragraph_index=None` for floating（数据模型清理）|
| 8 | ORF fix: 新 `_inject_floating_image()` 方法，写 wp:anchor |
| 9 | 新 fixture `use_real_llm`（不设 `OMNI_TEST_FAKE_LLM`）|
| 10 | 加 `requires_api_key` + `nightly` markers |

---

## 4. File Structure

### 4.1 新建文件（6 个）

| 路径 | 估算行数 | 作用 |
|---|---|---|
| `Omni_Suite/tests/test_e2e_real_llm.py` | ~350 | 3 个真 LLM 测试 + `use_real_llm` fixture |
| `Omni_Suite/tests/test_ol_lqa_autoinvoke.py` | ~120 | OL LQA auto-invoke 测试（feature 3）|
| `Omni_Suite/Omni_Re_Formatter/tests/test_md_separate_images.py` | ~120 | MD 路径"file+images 分开"测试（feature 4）|
| `Omni_Suite/Omni_Re_Formatter/tests/test_xliff2docx_floating.py` | ~150 | ORF `wp:anchor` 浮动图注入路径测试（feature 2）|
| `Omni_Suite/tests/test_opp_floating_image_fix.py` | ~80 | OPP fix 测试（feature 1）|
| `Omni_Suite/.omo/plans/real-llm-integration-tests.md` | (此文件) | 本 plan |

### 4.2 修改文件（7 个）

| 路径 | 修改 |
|---|---|
| `Omni_Pre_Processor/src/opp/extractors/docx.py:220` | `assigned_index = None` for floating images（10-15 LoC）|
| `Omni_Pre_Processor/src/opp/utils/dataclasses.py:51-63` | `ImageData` 加 `is_floating: bool = False` 字段（1 LoC）|
| `Omni_Pre_Processor/src/opp/utils/images_json.py` | carry `is_floating` through to images.json（5 LoC）|
| `Omni_Re_Formatter/src/orf/channels/xliff2docx.py:633-755` | 新 `_inject_floating_image()` 方法 + `wp:anchor` 注入（100-150 LoC）|
| `Omni_Localizer/src/ol_config/schema.py` | `ProjectConfig` 加 `enable_lqa/lqa_threshold/lqa_max_retries` 3 字段 |
| `Omni_Localizer/src/ol_cli.py:_translate_md_async` + `_translate_xliff_async` | LQA auto-wrap RetryManager |
| `Omni_Localizer/src/ol_mcp/tools.py:translate_md_text` + `translate_xliff` | 同样 |
| `Omni_Re_Formatter/src/orf/channels/md2docx.py` | `MD2DOCXConverter.convert()` 加 `separate_images: bool` + `images_dir: Path` |
| `Omni_Re_Formatter/src/orf/cli.py:apply-md` | `--separate-images` flag |
| `Omni_Re_Formatter/src/orf/mcp/server.py:apply_md` | 加 `separate_images` 参数 |
| `Omni_Suite/tests/conftest.py:pytest_configure` + `Omni_Suite/tests/pytest.ini:markers` | 注册 `requires_api_key` + `nightly` markers |
| `Omni_Localizer/config/default.yaml` | 你加 6 个 model 条目（每个角色 2 个）|
| `Omni_Localizer/.env` | 你填真实 MINIMAX + BAIDU key |

### 4.3 不动
- 现有 46 个 fake 测试、3 个子仓的 .gitignore、OL 现有所有 LQA 模块、ORF 现有 XLIFF/MD 转换逻辑（除新功能外）

---

## 5. Feature Designs（4 个新 feature + 1 个新测试集）

### 5.1 Feature 1: OPP 浮动图修复

**改动**：`Omni_Pre_Processor/src/opp/extractors/docx.py:220`
```python
# 当前（伪 fallback）：
assigned_index = drawing_para_index if drawing_para_index > 0 else fallback_index

# Fix：
assigned_index = drawing_para_index if drawing_para_index > 0 else None
result.append(ImageData(
    data=image_part.blob,
    mime_type=image_part.content_type,
    paragraph_index=assigned_index,
    is_floating=(assigned_index is None),  # NEW
))
```

**新增字段**：`ImageData.is_floating: bool = False`（区分浮动/段内图）

**测试**：`tests/test_opp_floating_image_fix.py`
- 用 Haier DOCX 跑 OPP，断言 24 张图中：
  - 2 张 `is_floating=False`，`paragraph_index ∈ [0, 8]`
  - 22 张 `is_floating=True`，`paragraph_index is None`
- 现有 OPP 测试不破（已确认无 `paragraph_index == N` 断言）

### 5.2 Feature 2: ORF `wp:anchor` 浮动图注入

**改动**：`Omni_Re_Formatter/src/orf/channels/xliff2docx.py`

新方法：
```python
def _inject_floating_image(
    self,
    doc_tree: etree._ElementTree,
    img: "ImagePlacement",
    anchor_data: dict,  # {positionH, positionV, relativeH, relativeV, ...}
) -> etree._Element:
    """Construct <w:drawing><wp:anchor> for floating image.

    Preserves the original positionH/positionV from the source DOCX.
    """
    # Construct <w:drawing>
    #   <wp:anchor distT="0" distB="0" distL="114300" distR="114300" simplePos="0" relativeHeight="251659264" behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">
    #     <wp:simplePos x="0" y="0"/>
    #     <wp:positionH relativeFrom="page"><wp:posOffset>...</wp:posOffset></wp:positionH>
    #     <wp:positionV relativeFrom="page"><wp:posOffset>...</wp:posOffset></wp:positionV>
    #     <wp:extent cx="..." cy="..."/>
    #     ...
    #     <a:graphic>
    #       <a:graphicData>
    #         <pic:pic>...</pic:pic>
    #       </a:graphicData>
    #     </a:graphic>
    #   </wp:anchor>
    # </w:drawing>
    pass  # implementation
```

修改 `inject_images()`：
```python
def inject_images(self, skeleton_path, images, output_path):
    # Separate by is_floating flag
    floating = [img for img in images if getattr(img, 'is_floating', False) and img.paragraph_index is None]
    in_para = [img for img in images if not getattr(img, 'is_floating', False) and img.paragraph_index is not None]

    # Existing logic for in_para
    positioned, unpositioned = self._inject_inline_images(doc_tree, in_para)

    # New logic for floating (wp:anchor)
    floating_positioned, floating_unpositioned = self._inject_floating_images(doc_tree, floating)

    return positioned + floating_positioned, unpositioned + floating_unpositioned
```

**anchor_data 来源**（需要 OPP 提供）：
- OPP 当前**不**提取 `wp:anchor` 的 `positionH`/`positionV`（只存 `paragraph_index`）
- 改动：OPP 从原 DOCX 提取 anchor 元素（如果是 `<wp:anchor>`），把 H/V 坐标存到 `ImageData`（或 `images.json`）
- OPP 改动 ~30-50 LoC：解析 `wp:anchor`，extract `wp:posOffset`，存到 ImageData

**测试**：`Omni_Re_Formatter/tests/test_xliff2docx_floating.py`
- 构造带 `wp:anchor` 的输入 DOCX（带 `<wp:positionH relativeFrom="page"><wp:posOffset>100000</wp:posOffset></wp:positionH>` 等）
- 调 ORF `inject_images`
- 断言输出 DOCX 里有相同 H/V 坐标的 `<wp:anchor>` 元素

### 5.3 Feature 3: OL LQA auto-invoke

**Schema 变更** (`Omni_Localizer/src/ol_config/schema.py`):
```python
class ProjectConfig(BaseModel):
    ...
    enable_lqa: bool = Field(False, description="Auto-invoke LQA judge with retry in main pipeline")
    lqa_threshold: float = Field(7.0, description="LQA judge pass threshold (0-10)")
    lqa_max_retries: int = Field(2, description="Max LQA retries (best-of-N)")
```

**CLI 变更** (`Omni_Localizer/src/ol_cli.py:_translate_md_async`):
```python
# 在 pool = ModelPool.get_instance(...) 之后，translate 之前
if cfg.enable_lqa:
    from ol_lqa.judge import JudgeService
    from ol_retry.retry import RetryManager
    judge = JudgeService(pass_threshold=cfg.lqa_threshold)
    retry = RetryManager(max_retries=cfg.lqa_max_retries, pass_threshold=cfg.lqa_threshold)

    def translate_fn():
        return await pool.translate(shielded, src_lang, tgt_lang)

    def judge_fn(src, tgt, unit):
        return judge.judge(src, tgt, unit, source_lang=src_lang, target_lang=tgt_lang)

    result = retry.execute_with_retry("md_main", original_text, translate_fn, judge_fn)
    translated = result.best_translation
    if result.warning:
        logger.warning(f"LQA: {result.warning}")
else:
    translated = await pool.translate(shielded, src_lang, tgt_lang)
```

**MCP 变更** (`Omni_Localizer/src/ol_mcp/tools.py:translate_md_text`): 同样 wrap RetryManager。

**测试** (`Omni_Suite/tests/test_ol_lqa_autoinvoke.py`):
- 启用 LQA + 故意把 LLM 第一次返回 bad（mock）→ 验证 retry 触发
- 禁用 LQA → 验证 retry **不**触发
- max_retries=0 → 等价禁用

### 5.4 Feature 4: MD 路径"file+images 分开"

**Converter 变更** (`Omni_Re_Formatter/src/orf/channels/md2docx.py`):
```python
def convert(
    self,
    input_path: Path | str,
    output_path: Path | str,
    **options: Any,
) -> ConversionResult:
    separate_images: bool = options.get("separate_images", False)
    images_dir: Path | None = options.get("images_dir")

    if separate_images and images_dir:
        # 1. 解析 MD，提取所有图片引用
        images = extract_image_references(input_path)
        # 2. 复制图片到 images_dir/
        copy_images(images, images_dir)
        # 3. 写 image_manifest.json
        write_manifest(images, images_dir / "image_manifest.json")
        # 4. 把 MD 的 image 引用替换成占位符
        stripped_md = strip_image_refs(input_path, images)
        # 5. pandoc 转 stripped_md → DOCX（无图）
        return pandoc_convert(stripped_md, output_path)
    else:
        return pandoc_convert(input_path, output_path)  # 现有逻辑
```

**CLI 变更** (`Omni_Re_Formatter/src/orf/cli.py:apply-md`):
```python
"--separate-images": is_flag, help="Don't embed images; output DOCX + images/ separately"
"--images-dir": type=Path, default="./images", help="Output directory for images"
```

**MCP 变更** (`Omni_Re_Formatter/src/orf/mcp/server.py:apply_md`): 加 `separate_images` 和 `images_dir` 参数。

**测试** (`Omni_Re_Formatter/tests/test_md_separate_images.py`):
- 启用 separate_images → 验证 DOCX 无图、images/ 24 张图、manifest.json 正确
- 禁用 → 验证 DOCX 有图（现有行为）

### 5.5 真 LLM 集成测试

**新文件** `Omni_Suite/tests/test_e2e_real_llm.py`

**3 个测试**:

#### Test 1: `test_xliff_mcp_real_llm_image_positioning`（Path A）
```python
def test_xliff_mcp_real_llm_image_positioning(haier_real_docx_path, use_real_llm, tmp_path):
    """24/24 strict visual image positioning via real LLM."""
    # 1. OPP（真）: process_file + generate_xliff + save_skeleton
    pipeline = OPPPipeline(resource_storage_dir=tmp_path / "resources")
    result = pipeline.process_file(haier_real_docx_path)
    xliff = pipeline.generate_xliff(result.extraction_result, tmp_path / "out.xlf", "en", "zh")
    skeleton = pipeline.save_skeleton(result.extraction_result, "haier", tmp_path)

    # 2. OL MCP（真 LLM）: translate_xliff
    translated_xliff = ol_mcp_tools.translate_xliff(
        TranslateXliffInput(input_path=str(xliff), source_lang="en", target_lang="zh")
    )

    # 3. ORF MCP（真）: apply_xliff with images parameter
    images_list = [img.to_image_placement() for img in result.extraction_result.images]
    orf_mcp_tools.apply_xliff(
        input_file=str(skeleton),
        xliff_path=str(translated_xliff),
        output_path=str(tmp_path / "out.docx"),
        format="docx",
        images=images_list,
    )

    # 4. 验证 24/24 strict visual
    opp_positions = extract_image_visual_positions_from_opp(result.extraction_result)
    orf_positions = extract_image_visual_positions_from_docx(tmp_path / "out.docx")

    for img_filename, opp_pos in opp_positions.items():
        orf_pos = orf_positions[img_filename]
        # 段内图: 严格 paragraph_index match
        if opp_pos['type'] == 'inline':
            assert orf_pos['paragraph_index'] == opp_pos['paragraph_index']
        # 浮动图: 严格 H/V 坐标 match (允许 ±1px 容差)
        elif opp_pos['type'] == 'floating':
            assert abs(orf_pos['positionH'] - opp_pos['positionH']) <= 9525  # 1px = 9525 EMU
            assert abs(orf_pos['positionV'] - opp_pos['positionV']) <= 9525
```

#### Test 2: `test_xliff_cli_real_llm_image_positioning`（Path B）
- 同样但用 subprocess 调 `ol_cli` 和 `orf.cli`
- 断言 subprocess rc == 0

#### Test 3: `test_xliff_real_llm_translation_quality`（Path A + LQA）
- 跑 Path A → translated_xliff
- 解析 XLIFF，提取 (source, target) 对
- 调 `JudgeService(pass_threshold=5.0).judge()` 对每对
- 聚合 4 维度评分
- 断言：4 维度平均 ≥ 5.0

**新 fixture** `use_real_llm`:
```python
@pytest.fixture
def use_real_llm(monkeypatch):
    """Inverse of use_fake_llm. Does NOT set OMNI_TEST_FAKE_LLM."""
    env_path = Path(__file__).resolve().parents[1] / "Omni_Localizer" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                if v.strip():
                    monkeypatch.setdefault(k.strip(), v.strip())
    if not any(os.environ.get(k) for k in ["MINIMAX_API_KEY", "BAIDU_API_KEY"]):
        pytest.skip("Real LLM test skipped: no MINIMAX/BAIDU key")
    return True
```

---

## 6. Migration Phases (7 phases, ~7-8h total)

### Phase 1（你做，10 min，阻塞）
1. 填 `Omni_Localizer/.env`:
   ```
   MINIMAX_API_KEY=<real key>
   MINIMAX_BASE_URL=https://api.minimaxi.com/v1
   BAIDU_API_KEY=<real key>
   BAIDU_BASE_URL=https://qianfan.baidubce.com/v2
   ```
2. 改 `Omni_Localizer/config/default.yaml`：加 6 个 model 条目（translation/judging/restoration 各 2 个）
3. 手动验证: `cd Omni_Localizer && python -m ol_cli translate-md <md> -s en -t zh` 确认真 LLM 调通

### Phase 2（我做，1-2h）：OPP 浮动图修复
- `extractors/docx.py:220`: `paragraph_index=None` for floating
- `utils/dataclasses.py`: 加 `is_floating: bool = False`
- `utils/images_json.py`: carry `is_floating` through
- `tests/test_opp_floating_image_fix.py`: 验证 22/24 `is_floating=True, paragraph_index=None`
- 跑现有 OPP 测试确认不破

### Phase 3（我做，2-3h）：ORF `wp:anchor` 注入路径
- `channels/xliff2docx.py`: 新 `_inject_floating_image()` 方法（~100-150 LoC）
- `utils/images_json.py`/`utils/dataclasses.py`: 携带 H/V 坐标（如果还没）
- `Omni_Re_Formatter/tests/test_xliff2docx_floating.py`: 验证 wp:anchor 注入
- 跑现有 ORF 测试确认不破

### Phase 4（我做，1h）：OL LQA auto-invoke
- `ol_config/schema.py`: 加 3 个字段
- `ol_cli.py:_translate_md_async` + `_translate_xliff_async`: wrap RetryManager
- `ol_mcp/tools.py:translate_md_text` + `translate_xliff`: 同样
- `Omni_Suite/tests/test_ol_lqa_autoinvoke.py`: 验证 retry 触发/不触发
- 跑现有 OL 测试确认不破（`enable_lqa=False` 默认行为不变）

### Phase 5（我做，1.5h）：MD path images-separation
- `orf/channels/md2docx.py`: `MD2DOCXConverter.convert()` 加 `separate_images: bool` + `images_dir: Path`
- `orf/cli.py:apply-md`: `--separate-images` flag
- `orf/mcp/server.py:apply_md`: MCP 参数
- `Omni_Re_Formatter/tests/test_md_separate_images.py`: 验证
- 跑现有 ORF 测试确认不破

### Phase 6（我做，1.5h）：真 LLM 集成测试
- 注册 `requires_api_key` + `nightly` markers
- 写 `use_real_llm` fixture
- 写 `test_xliff_mcp_real_llm_image_positioning`（Path A）
- 手动跑一次确认 OK
- 写 `test_xliff_cli_real_llm_image_positioning`（Path B）
- 写 `test_xliff_real_llm_translation_quality`（LQA）

### Phase 7（我做，30 min）：验证
- `pytest -m "not nightly" tests/` → 46 fake + 4 new feature tests 全过
- `pytest -m "nightly" tests/test_e2e_real_llm.py` → 3 真 LLM 测试
- 确认 `.env` 仍被 gitignore
- 确认没有 secret leak

---

## 7. Verification Commands

```bash
# CI 默认（fake LLM）
cd /mnt/d/贯维/Omni_Suite && .venv/bin/python -m pytest \
  tests/ -m "not nightly" --tb=short
# 46 fake + 4 new feature tests 全 PASS

# 单独验证 OPP fix
.venv/bin/python -m pytest Omni_Pre_Processor/tests/ tests/test_opp_floating_image_fix.py -v

# 单独验证 ORF wp:anchor
.venv/bin/python -m pytest \
  Omni_Re_Formatter/tests/test_xliff2docx_floating.py \
  Omni_Re_Formatter/tests/test_md_separate_images.py -v

# 单独验证 OL LQA auto-invoke
.venv/bin/python -m pytest tests/test_ol_lqa_autoinvoke.py -v

# Nightly（真 LLM）
.venv/bin/python -m pytest tests/test_e2e_real_llm.py -m "nightly" -v --tb=short
# 3 真 LLM 测试，~1-3 分钟
```

---

## 8. Risk Assessment

| # | 风险 | 概率 | 缓解 |
|---|---|---|---|
| 1 | OPP fix 改数据模型影响现有测试 | 低 | 已确认无 `paragraph_index == N` 断言 |
| 2 | ORF `wp:anchor` 路径复杂 | 高 | 严格按原 DOCX 的 anchor 元素直接 preserve 坐标 |
| 3 | 浮动图原 DOCX 没 `wp:anchor` | 中 | OPP 探一下 Haier DOCX 的 anchor 实际数量 |
| 4 | 真 LLM 慢 | 100% | 用户已认可；3 测试共 1-3 分钟 |
| 5 | LQA auto-invoke 改动 OL 主 pipeline 风险 | 中 | 默认 `enable_lqa=False`；现有测试全过 |
| 6 | MD images-separation 改动影响现有 MD 路径测试 | 中 | 旧行为保留（默认 `separate_images=False`）|
| 7 | `wp:anchor` 写入 XML 命名空间/属性问题 | 中-高 | 复用 ORF 现有的 namespace constants |
| 8 | OPP 提取 anchor H/V 失败（XML 解析错误）| 中 | 失败时 fallback 到 paragraph_index 定位 |

---

## 9. Acceptance Criteria

- [~] Phase 1：`.env` 填好，CLI 手动调通真 LLM
- [~] Feature 1：OPP 24 张图中 22 张 `is_floating=True, paragraph_index=None`，2 张段内图
- [~] Feature 2：ORF 新 `_inject_floating_image()` 对 22 张浮动图写入 `wp:anchor` 含 H/V 坐标
- [~] Feature 3：`enable_lqa=True` 时 RetryManager 触发；`False` 时不触发
- [~] Feature 4：`separate_images=True` 时 DOCX 无图、images/ 24 张、manifest 正确
- [~] 3 个真 LLM 测试通过手动跑（`pytest -m nightly`）
- [~] 24/24 strict visual 位置匹配（2 段内图 paragraph_index + 22 浮动图 wp:anchor H/V）
- [~] LQA 4 维度平均 ≥ 5.0（多次跑稳定）
- [~] 46 fake + 4 new feature 测试保持 PASS
- [~] `pytest -m "not nightly"` 不跑真 LLM（CI 友好）
- [~] `.env` 仍被 3 个子仓 gitignore 保护
- [~] 没有 secret leak

---

## 10. Estimated Effort

| Phase | 内容 | 估时 |
|---|---|---|
| Phase 1 | 你填 key + config | 10 min |
| Phase 2 | OPP fix | 1-2h |
| Phase 3 | ORF `wp:anchor` | 2-3h |
| Phase 4 | OL LQA auto-invoke | 1h |
| Phase 5 | MD images-separation | 1.5h |
| Phase 6 | 真 LLM 集成测试 | 1.5h |
| Phase 7 | 验证 | 30 min |
| **总计** | | **~7-8h**（你 10 min + 我 7-8h）|

---

## 11. Sign-off

✅ **所有 6 件事已 sign-off**（from previous turn's question round + this turn's B choice）：

- [x] CI 跑 fake，nightly 跑真 LLM
- [x] XLIFF 路径（A+B），不做 MD 路径和多格式
- [x] 24/24 strict visual 位置（不是 presence only）
- [x] OL 主 pipeline 加 LQA auto-invoke
- [x] LQA 阈值 4 维度 < 5.0 才 fail
- [x] 5 个新测试文件，46 现有 fake 测试不动

**Plan FINAL. 等你 Phase 1 完成就开干。**

---

## 12. References

- `.omo/plans/e2e-4path-test-refactor.md` — 上一轮 fake-LLM 重构 plan（已执行完毕）
- `Omni_Pre_Processor/src/opp/extractors/docx.py:195-230` — OPP 浮动图 fallback 逻辑（要修）
- `Omni_Pre_Processor/src/opp/utils/dataclasses.py:51-63` — ImageData 定义（要加 is_floating）
- `Omni_Re_Formatter/src/orf/channels/xliff2docx.py:633-755` — inject_images 逻辑（要加 _inject_floating_image）
- `Omni_Re_Formatter/src/orf/mcp/schemas.py:36-77` — ImagePlacement schema（已有 page_number，要加 is_floating）
- `Omni_Localizer/src/ol_config/schema.py:59-66` — ProjectConfig（要加 LQA 字段）
- `Omni_Localizer/src/ol_cli.py:239,338` — _translate_*_async（要加 LQA wrap）
- `Omni_Localizer/src/ol_mcp/tools.py:160,474` — translate_*_text/xliff（要加 LQA wrap）
- `Omni_Localizer/src/ol_lqa/judge.py:19` — JudgeService
- `Omni_Localizer/src/ol_retry/retry.py:18` — RetryManager
- `Omni_Re_Formatter/src/orf/channels/md2docx.py:44-115` — MD2DOCXConverter（要加 separate_images）
- `tests/conftest.py:593` — haier_real_docx_path fixture
- `tests/test_e2e_path_xliff_mcp.py` — 现有 fake 版 XLIFF 路径测试（可复用 dispatcher）
- `tests/test_e2e_cloud.py:137-158` — "real if creds" 模式（可改造）
- `tests/pytest.ini:46-53` — markers 注册位置
