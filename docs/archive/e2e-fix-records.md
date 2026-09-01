> **Status: ARCHIVED (2026-08-23). Reason: one-off E2E bug-fix records moved out of `README.md`. Superseded by: `CHANGELOG.md` + git history.**

# E2E Fix Records (E2E-03 / E2E-06 / E2E-07)

Historical record of three E2E bug fixes. Previously inline in `README.md`;
moved here during the doc-foundation gap-closure (2026-08-23) because one-off
bug evidence does not belong in the human front door. See `CHANGELOG.md` and
git history for the authoritative record.

## E2E-03 修复记录

**文件**：`Omni_Re_Formatter/src/orf/mcp/server.py:189`

**问题**：`images=None` 时访问未初始化变量 `temp_created`，导致 `NameError`

**修复**：在 `if images:` 之前添加 `temp_created = False`

**验证**：
```bash
PYTHONPATH="Omni_Re_Formatter/src" .venv312/bin/python -c "
from orf.mcp.server import _run_cli_command
# 模拟 images=None 调用
result = _run_cli_command(['apply-xliff', '/nonexistent.docx', '--xliff', '/nonexistent.xliff', '--output', '/tmp/out.docx', '--format', 'docx'])
print('OK — no NameError' if 'NameError' not in str(result) else 'FAIL')
"
```

## E2E-06: MD Path 段落膨胀修复

**问题**：OL `TokenPositionTracker.rebuild()` 在 `paragraph_close` 时只输出 `\n`（单换行），导致段落间空行丢失。随后 `ensure_md_block_separation()` 过度补偿——在每个行内折行处注入 `<!-- p -->`，使段落数从 12,273 膨胀至 16,860（+37%）。

**改动清单**：

| 组件 | 文件 | 改动 |
|------|------|------|
| OL | `token_stream.py` | `paragraph_close` 改为输出 `\n\n`（双换行），恢复段落间空行 |
| Suite | `test_e2e_real_llm.py` | `ensure_md_block_separation()` 正则从 `(?<=\S)\n(?=\S)` 收紧为 `\n\n(?=\S)`，仅在空行边界注入 `<!-- p -->` |

**验证**：
```bash
pytest tests/test_e2e_real_llm.py -v -k test_md_channel
```

## E2E-07: 边界条件测试修复

**问题**：OPP/ORF/images 模块的 9 个边缘测试因环境差异（python-pptx 版本、缺少 CLI 工具、格式变更）而失败。

**改动清单**：

| 组件 | 文件 | 改动 |
|------|------|------|
| OPP | `test_e2e_opp_all_formats.py` | `_create_minimal_epub()` 添加 `OEBPS/` mkdir；PPTX `slide_layouts[6]` → `[0]`（3处）；IPYNB 添加 `@pytest.mark.xfail` |
| ORF | `test_e2e_orf_all_formats.py` | ICML 断言改为检查 `ParagraphStyleRange`；MD2PPTX 添加 `shutil.which()` 跳过守卫 |
| ORF | `options.py` | PDF 默认引擎从 `pdflatex` 改为 `weasyprint` |
| Images | `test_e2e_images.py` | PPTX `slide_layouts[6]` → `[0]` |
| Suite | `e2e_runner.py` + `test_e2e_real_llm.py` | 新增 `--glossary` 参数传递支持 |

**验证**：
```bash
pytest tests/test_e2e_opp_all_formats.py -v -k "pptx or ipynb"
pytest tests/test_e2e_orf_all_formats.py -v -k "icml or md2pptx or md2pdf"
pytest tests/test_e2e_images.py -v -k "pptx"
```
