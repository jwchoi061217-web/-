# 매주 정부지원사업 공고를 수집해 docs/ (대시보드 + 아카이브)를 갱신한다.
# Windows 작업 스케줄러가 호출한다 (월 08:00 + 로그온 catch-up).
#
# 같은 주에 두 번 돌지 않는다 — 로그온할 때마다 다시 수집하면 '이번주 신규'가
# 매번 바뀌고 같은 서버를 불필요하게 두드리게 된다. 강제로 다시 돌리려면 -Force.
param([switch]$Force)
$ErrorActionPreference = 'Continue'

$here = $PSScriptRoot
$root = Split-Path -Parent $here
$log = Join-Path $here 'collect.log'
$stateFile = Join-Path $here 'collect_state.json'

function Write-Log([string]$msg) {
    Add-Content -Path $log -Encoding utf8 -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
}

# 이번 주 월요일 날짜 = 주차 식별자
$today = (Get-Date).Date
$offset = (([int]$today.DayOfWeek) + 6) % 7
$week = $today.AddDays(-$offset).ToString('yyyy-MM-dd')

if (-not $Force -and (Test-Path $stateFile)) {
    try {
        $state = Get-Content $stateFile -Raw -Encoding utf8 | ConvertFrom-Json
        if ($state.week -eq $week) { exit 0 }
    } catch {}
}

$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $py) {
    Write-Log '[실패] 파이썬을 찾을 수 없습니다'
    exit 9
}

Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
Write-Log "수집 시작 (주차 $week)"

# 파이썬의 진행 로그는 stderr 로 나온다. cmd 를 거쳐 파일로 바로 붙인다
# (PS 5.1 에서 2>&1 을 쓰면 줄마다 오류 레코드로 감싸져 로그가 지저분해진다).
cmd /c "`"$py`" -m src.main >> `"$log`" 2>&1"
$code = $LASTEXITCODE

if ($code -eq 0) {
    @{ week = $week; ran_at = (Get-Date -Format 's') } | ConvertTo-Json |
        Out-File -FilePath $stateFile -Encoding utf8
    Write-Log '수집 완료'
} else {
    Write-Log "[실패] 종료 코드 $code - 다음 로그온 때 다시 시도합니다"
}
exit $code
