# 주간 발행물을 PC 카카오톡 단톡방으로 발송한다.
# Windows 작업 스케줄러가 이 스크립트를 호출한다 (월 08:05 + 로그온 catch-up).
$ErrorActionPreference = 'Continue'

$here = $PSScriptRoot
$root = Split-Path -Parent $here
$log = Join-Path $here 'send.log'

# 파이썬 실행 파일 찾기
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $py) {
    Add-Content -Path $log -Encoding utf8 -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [실패] 파이썬을 찾을 수 없습니다"
    exit 9
}

Set-Location $root
& $py (Join-Path $here 'kakao_send.py')
$code = $LASTEXITCODE

if ($code -ne 0) {
    Add-Content -Path $log -Encoding utf8 -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 발송 스크립트 종료 코드 $code"
}
exit $code
