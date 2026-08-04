# 모두의러닝 주간 발송 관리 대시보드를 띄운다.
# 바탕화면 바로가기에서 실행하는 것을 전제로 한다.
$ErrorActionPreference = 'Stop'

$here = $PSScriptRoot
$root = Split-Path -Parent $here

$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $py) { Write-Host '파이썬을 찾을 수 없습니다.' -ForegroundColor Red; Read-Host '엔터'; exit 1 }

# 이미 떠 있으면 브라우저만 연다
$busy = $null
try { $busy = Get-NetTCPConnection -LocalPort 8422 -State Listen -ErrorAction SilentlyContinue } catch {}
if ($busy) {
    Write-Host '대시보드가 이미 실행 중입니다 — 브라우저만 엽니다.' -ForegroundColor Yellow
    Start-Process 'http://127.0.0.1:8422'
    exit 0
}

Set-Location $root
& $py (Join-Path $here 'dashboard\server.py')
