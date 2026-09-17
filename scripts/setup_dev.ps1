<#
.SYNOPSIS
    Omni Suite — 原生 Windows 开发环境引导脚本。

.DESCRIPTION
    与 scripts/setup_dev.sh 等价，但面向**不使用 WSL** 的 Windows 开发者。
    背景：仓库根下的 .venv/ 与 .venv_ol/ 是 Linux 版 uv venv（pyvenv.cfg 指向
    /home/<user>/.local/share/uv/python/cpython-3.13-linux-*），Windows 无法
    创建或激活；CI 与 WSL 工作流依赖它们，因此本脚本**绝不触碰**这两个目录，
    而是在 .venv_win/ 建立独立的 Windows 原生 venv。

    步骤：
      1. 校验 Python >= 3.13
      2. 创建 / 复用 .venv_win/
      3. editable 安装三个子仓库（OPP / OL / ORF）
      4. 校验子仓库版本与 COMPATIBILITY.md 一致
      5. 复制 .env.example -> .env
      6. 校验 pandoc
      7. 运行 C-3 契约冒烟测试

.PARAMETER CheckOnly
    只做校验，不创建 venv、不安装依赖。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/setup_dev.ps1
    powershell -ExecutionPolicy Bypass -File scripts/setup_dev.ps1 -CheckOnly
#>
[CmdletBinding()]
param(
    [switch]$CheckOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Info { param([string]$Message) Write-Host "[INFO]  $Message" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Message) Write-Host "[OK]    $Message" -ForegroundColor Green }
function Write-Warn2 { param([string]$Message) Write-Host "[WARN]  $Message" -ForegroundColor Yellow }
function Write-Err  { param([string]$Message) Write-Host "[ERR]   $Message" -ForegroundColor Red }

# ─ 解析项目根目录 ────────────────────────────────────────────────────────────
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
# Windows 原生 venv（与 Linux 的 .venv / .venv_ol 分离，互不干扰）
$VenvDir  = Join-Path $ProjectRoot '.venv_win'
$VenvPy   = Join-Path $VenvDir 'Scripts\python.exe'
$SubRepos = @('Omni_Pre_Processor', 'Omni_Localizer', 'Omni_Re_Formatter')

Write-Info "项目根目录: $ProjectRoot"

# ─ 步骤 1 — 校验 Python >= 3.13 ─────────────────────────────────────────────
Write-Info "检查 Python 版本 …"
$PythonExe = $null
foreach ($candidate in @('python', 'py')) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) { $PythonExe = $cmd.Source; break }
}
if (-not $PythonExe) {
    Write-Err "未找到 Python。请安装 Python >= 3.13 并加入 PATH。"
    exit 1
}

$VersionRaw = & $PythonExe -c "import sys; print('%d.%d' % sys.version_info[:2])"
$Parts = $VersionRaw.Trim().Split('.')
if ([int]$Parts[0] -lt 3 -or ([int]$Parts[0] -eq 3 -and [int]$Parts[1] -lt 13)) {
    Write-Err "需要 Python >= 3.13，当前为 $VersionRaw"
    exit 1
}
Write-Ok "Python $VersionRaw 已就绪"

# ── 步骤 2 — 创建 / 复用 Windows venv ────────────────────────────────────────
if (-not $CheckOnly) {
    if (-not (Test-Path $VenvPy)) {
        Write-Info "创建 Windows 虚拟环境: $VenvDir …"
        & $PythonExe -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) { Write-Err "venv 创建失败"; exit 1 }
        Write-Ok "虚拟环境已创建"
    } else {
        Write-Info "虚拟环境已存在: $VenvDir"
    }
}

if (-not (Test-Path $VenvPy)) {
    if ($CheckOnly) {
        Write-Warn2 "未找到 $VenvPy（-CheckOnly 模式不创建）。"
        Write-Warn2 "去掉 -CheckOnly 重新运行即可完成安装。"
    } else {
        Write-Err "虚拟环境缺少 $VenvPy"
        exit 1
    }
}

# ── 步骤 3 — editable 安装根工程 + 三个子仓库 ────────────────────────────────
if (-not $CheckOnly) {
    if (-not (Test-Path $VenvPy)) { exit 1 }
    Write-Info "安装根工程与子仓库（editable）…"
    & $VenvPy -m pip install --upgrade pip setuptools wheel -q
    $InstallArgs = @()
    # 根工程（omni_suite / omni_mcp / omni_metrics）必须一并安装：它的运行时依赖
    # （mcp / anyio，见 pyproject.toml 的 mcp extra 与 dependencies）不在三个子仓库的
    # 依赖里，而步骤 7 的 C-3 冒烟测试会在进程内 import opp.mcp.server → 缺 mcp 就红。
    # setup_dev.sh 走 `uv sync` 时会一并装上根 workspace，此处对齐同一语义。
    $InstallArgs += @('-e', $ProjectRoot)
    foreach ($repo in $SubRepos) { $InstallArgs += @('-e', (Join-Path $ProjectRoot $repo)) }
    & $VenvPy -m pip install @InstallArgs
    if ($LASTEXITCODE -ne 0) { Write-Err "editable 安装失败"; exit 1 }
    Write-Ok "OMNI-SUITE / OPP / OL / ORF 安装完成"
}

# ── 步骤 4 — 校验子仓库版本与 COMPATIBILITY.md 一致 ──────────────────────────
$CompatFile = Join-Path $ProjectRoot 'COMPATIBILITY.md'
$VersionFile = Join-Path $ProjectRoot 'VERSION'
if ((Test-Path $CompatFile) -and (Test-Path $VersionFile)) {
    # VERSION 前两行是注释；真实版本号取最后一行非注释内容
    $SuiteVersion = (Get-Content $VersionFile | Where-Object { $_ -notmatch '^\s*#' -and $_.Trim() } | Select-Object -Last 1).Trim()
    # 关键：COMPATIBILITY.md 中同一 Suite 版本可能出现多行（同一版本的不同补丁行），
    # 且历史版本行排在最前。必须取「与当前 VERSION 匹配的最后一行」——取第一行会
    # 命中历史版本，导致版本校验永远误报不一致（原 setup_dev.sh 的 head -1 即此缺陷）。
    $CompatLine = Select-String -Path $CompatFile -Pattern "^[|]\s*$([regex]::Escape($SuiteVersion))\s*[|]" | Select-Object -Last 1
    if ($CompatLine) {
        Write-Info "COMPATIBILITY.md 取用 Suite $SuiteVersion 行"
        $Cells = $CompatLine.Line.Split('|') | ForEach-Object { $_.Trim() }
        # 表格形如 | Suite | OL | OPP | ORF | ... ，去掉首尾空单元格
        $Expected = @{ OL = $Cells[2]; OPP = $Cells[3]; ORF = $Cells[4] }
        $Actual = @{}
        foreach ($kv in @(@('OL', 'Omni_Localizer'), @('OPP', 'Omni_Pre_Processor'), @('ORF', 'Omni_Re_Formatter'))) {
            $pyproj = Join-Path $ProjectRoot (Join-Path $kv[1] 'pyproject.toml')
            $m = Select-String -Path $pyproj -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
            $Actual[$kv[0]] = if ($m) { $m.Matches[0].Groups[1].Value } else { '?' }
        }
        $Mismatch = $false
        foreach ($key in @('OL', 'OPP', 'ORF')) {
            Write-Info ("  版本校验 {0}: COMPATIBILITY={1} 实际={2}" -f $key, $Expected[$key], $Actual[$key])
            if ($Expected[$key] -and $Expected[$key] -ne $Actual[$key]) { $Mismatch = $true }
        }
        if ($Mismatch) {
            Write-Warn2 "子仓库版本与 COMPATIBILITY.md 不一致（开发可接受，发布必须一致）。"
        } else {
            Write-Ok "子仓库版本与 COMPATIBILITY.md 一致"
        }
    }
}

# ── 步骤 5 — 复制 .env.example -> .env ──────────────────────────────────────
$EnvExample = Join-Path $ProjectRoot '.env.example'
$EnvTarget  = Join-Path $ProjectRoot '.env'
if (Test-Path $EnvExample) {
    if (-not (Test-Path $EnvTarget)) {
        Copy-Item $EnvExample $EnvTarget
        Write-Ok ".env 已从 .env.example 创建"
        Write-Warn2 "运行真实 LLM 测试前请在 .env 中填入 API Key。"
    } else {
        Write-Info ".env 已存在，跳过复制"
    }
} else {
    Write-Warn2 "未找到 $EnvExample — 跳过 .env 创建"
}

# ─ 步骤 6 — 校验 pandoc ────────────────────────────────────────────────────
Write-Info "检查 pandoc …"
$PandocCmd = Get-Command pandoc -ErrorAction SilentlyContinue
if ($PandocCmd) {
    $PandocVer = (& pandoc --version | Select-Object -First 1)
    Write-Ok "pandoc: $PandocVer"
} else {
    Write-Warn2 "未检测到 pandoc —— ORF 生成 DOCX/ODT/EPUB/RTF/ICML 需要它。"
    Write-Warn2 "安装方式: https://pandoc.org/installing.html（或 uv/pip 安装 pypandoc-binary）"
}

# ── 步骤 7 — 运行 C-3 契约冒烟测试 ──────────────────────────────────────────
$SmokePath = Join-Path $ProjectRoot 'tests\test_pipeline_contract_smoke.py'

# 选择解释器前必须探测它是否真能 import pytest，而不是只看 .venv_win\Scripts\python.exe
# 是否存在。原因：该文件在依赖装完之前就已存在（-CheckOnly 模式，或上一次 pip install
# 中途被打断），此时 `-m pytest` 会以 "No module named pytest" 退出 —— 把「环境未装完」
# 误报成「C-3 契约被破坏」。与 tests/test_pipeline_contract_smoke.py 的
# `_is_provisioned()` 同一原则：半成品解释器不得用来判定契约。
# 有 .venv_win 就以它为准（-CheckOnly 的语义是校验「已装好」的环境，与
# setup_dev.sh 的 --check-only 一致）；未建 venv 时才沿用原有的系统 Python 回退。
function Test-PytestAvailable {
    param([string]$Interpreter)
    if (-not $Interpreter -or -not (Test-Path $Interpreter)) { return $false }
    try {
        & $Interpreter -c "import pytest" 2>&1 | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

$SmokeCandidates = if (Test-Path $VenvPy) { @($VenvPy) } else { @($PythonExe) }
$SmokePy = $null
foreach ($candidate in $SmokeCandidates) {
    if (Test-PytestAvailable -Interpreter $candidate) { $SmokePy = $candidate; break }
}

if (Test-Path $SmokePath) {
    if (-not $SmokePy) {
        if ($CheckOnly) {
            Write-Warn2 "$VenvPy 尚不可用（依赖未安装，-CheckOnly 模式不安装）—— 跳过 C-3 冒烟测试。"
            Write-Warn2 "去掉 -CheckOnly 重新运行即可完成安装并执行该门禁。"
        } else {
            Write-Err "安装完成后 .venv_win 仍无 pytest（OL 的核心依赖 pytest>=8.0.0）—— 冒烟门禁无法执行。"
            exit 1
        }
    } else {
        Write-Info "C-3 冒烟测试解释器: $SmokePy"
        Write-Info "运行 C-3 契约冒烟测试 …"
        $env:OMNI_TEST_FAKE_LLM   = '1'
        $env:OMNI_TEST_FAKE_PANDOC = '1'
        $env:TRANSFORMERS_OFFLINE = '1'
        $env:HF_HUB_OFFLINE       = '1'
        Push-Location $ProjectRoot
        try {
            & $SmokePy -m pytest $SmokePath -v --tb=short
            $SmokeRc = $LASTEXITCODE
        } finally {
            Pop-Location
        }
        if ($SmokeRc -eq 0) {
            Write-Ok "C-3 契约冒烟测试通过"
        } else {
            Write-Err "C-3 契约冒烟测试失败（exit code $SmokeRc）"
            exit $SmokeRc
        }
    }
} else {
    Write-Warn2 "未找到 $SmokePath — 跳过冒烟测试"
}

# ── 汇总 ────────────────────────────────────────────────────────────────────
Write-Host ''
Write-Host '==========================================================================='
Write-Info '安装完成。快速开始（Windows PowerShell）：'
Write-Host ''
Write-Host '  .\.venv_win\Scripts\Activate.ps1'
Write-Host '  opp --target-format=md document.docx            # 抽取'
Write-Host '  ol translate-md document.md -s en -t zh -o out\ # 翻译'
Write-Host '  orf apply-md out\document.md --target-format docx -o result.docx  # 回填'
Write-Host ''
Write-Info '运行测试（需要设置允许目录，否则 PathValidator 会拒绝临时目录）：'
Write-Host "  `$env:MCP_ALLOWED_DIRECTORIES=`"$env:TEMP;$ProjectRoot`""
Write-Host '  .\.venv_win\Scripts\python.exe -m pytest tests -q -m "not nightly"'
Write-Host '==========================================================================='
