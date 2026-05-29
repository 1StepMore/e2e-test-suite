# E2E Test Suite

OPP + OL + ORF 全链路集成测试环境。

## 目录结构

```
e2e-test-suite/
├── src/
│   ├── Omni_Pre_Processor/   # OPP submodule (Git SHA: 3684e87)
│   ├── Omni_Localizer/       # OL submodule (Git SHA: 4685a47)
│   └── Omni_Re_Formatter/    # ORF submodule (Git SHA: c7d6853)
├── .venv312/                 # Python 3.12 虚拟环境
├── test-artifacts/           # 源文档 + 中间产物
├── test-output/              # 最终输出文档
└── reports/                  # 测试报告 + Bug 报告
```

## Python 环境

- 基础：`/usr/bin/python3.12`
- 依赖包：`.venv312/`（uv venv）
- 需安装 litellm：`uv pip install litellm --python .venv312/bin/python`

## Git Submodules

```
src/Omni_Pre_Processor   → 1StepMore/Omni_Pre_Processor (main)
src/Omni_Localizer      → 1StepMore/Omni_Localizer (main)
src/Omni_Re_Formatter   → 1StepMore/Omni_Re_Formatter (main)
```

每次测试前建议 `git submodule update --init` 确保 SHA 正确。

## 测试命令

```bash
# 0. 同步 submodules 到目标 SHA
git submodule update --init

# 1. OPP 提取文档
python src/Omni_Pre_Processor/cli.py extract /path/to/haier.docx -o test-output/opp_out/

# 2. OL 翻译 (CLI)
python src/Omni_Localizer/src/ol_cli.py translate-xliff test-output/opp_out/out.xliff \
  --config src/Omni_Localizer/config/book_localization.yaml \
  --output test-output/ol_out/translated.xliff

# 3. ORF 还原文档
python src/Omni_Re_Formatter/src/orf/cli.py apply-xliff \
  --input test-output/opp_out/out.docx \
  --xliff test-output/ol_out/translated.xliff \
  --output test-output/orf_out/final.docx

# 4. MCP 测试
# 启动 MCP 服务器后用 curl 测试 stdio 协议
```