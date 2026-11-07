# audio2pez dependency installer (per-package, bypasses pip resolver hang).
#
# Why: "pip install -r requirements.txt" stalls for 10-20 minutes in this
# environment (no output, nothing installed). Single-package installs with
# --no-deps finish in seconds, so we install packages one by one in order.
#
# Usage:  install_deps.cmd          (preferred, bypasses execution policy)
#         powershell -ExecutionPolicy Bypass -File install_deps.ps1
#
# ASCII-only on purpose: this file is read by PowerShell 5.1, which decodes
# BOM-less files as ANSI and would corrupt any non-ASCII path.

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $here '.venv\Scripts\python.exe'
$index = 'https://pypi.tuna.tsinghua.edu.cn/simple'

if (-not (Test-Path $py)) { throw "venv interpreter not found: $py" }

$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'

# Order matters: leaf deps first. numba/llvmlite/numpy are pinned to a
# mutually compatible range (latest numba does not support latest numpy).
$pkgs = @(
    'typing_extensions',
    'lazy_loader',
    'decorator',
    'joblib',
    'platformdirs',
    'packaging',
    'threadpoolctl',
    'msgpack',
    'certifi',
    'charset_normalizer',
    'idna',
    'urllib3',
    'requests',
    'pooch',
    'audioread',
    'soxr',
    'pycparser',
    'cffi',
    'soundfile',
    'llvmlite>=0.43,<0.45',
    'numpy>=1.26,<2.3',
    'numba>=0.60,<0.62',
    'scipy>=1.11,<1.16',
    'scikit-learn>=1.3,<1.7',
    'Pillow>=9.0',
    'librosa>=0.10,<1.0'
)

foreach ($p in $pkgs) {
    Write-Host "--> $p" -NoNewline
    $sw = [Diagnostics.Stopwatch]::StartNew()
    & $py -m pip install --no-deps --only-binary=:all: --index-url $index --timeout 30 --retries 2 $p 2>&1 |
        Where-Object { $_ -match 'Successfully|ERROR|No matching' } | ForEach-Object { "  $_" }
    Write-Host ("    ({0:N0}s)" -f $sw.Elapsed.TotalSeconds)
}

Write-Host ''
Write-Host '=== import self-check ==='
& $py -c "import librosa, numpy, PIL, soundfile, numba; print('librosa', librosa.__version__); print('numpy', numpy.__version__); print('Pillow', PIL.__version__); print('soundfile', soundfile.__version__); print('numba', numba.__version__)"
