# 카카오톡 발송 작업을 Windows 작업 스케줄러에 등록한다.
# 관리자 권한이 필요하다 (대시보드가 UAC 승격으로 호출한다).
#
#   powershell -ExecutionPolicy Bypass -File register_task.ps1 -Weekday 1 -Hour 8 -Minute 5
#
# 트리거 2개
#   1) 매주 지정 요일·시각
#   2) 로그온 2분 뒤 — 정시에 PC가 꺼져 있었으면 따라잡아 발송
#      (이미 보낸 주차·방은 sent_state.json 을 보고 건너뛰므로 중복 발송되지 않는다)
param(
    [int]$Weekday = 1,   # 1=월 … 7=일
    [int]$Hour = 8,
    [int]$Minute = 5
)
$ErrorActionPreference = 'Stop'

$taskName = '모두의뉴스_발송'
$days = @('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
$day = $days[$Weekday - 1]
$at = Get-Date -Hour $Hour -Minute $Minute -Second 0

$ps1 = Join-Path $PSScriptRoot 'run_send.ps1'
if (-not (Test-Path $ps1)) { throw "run_send.ps1 을 찾을 수 없습니다: $ps1" }

# 인자에 공백·역슬래시가 섞여도 깨지지 않도록 경로를 따옴표로 감싼다.
# (같은 실수로 다른 프로젝트에서 스케줄 작업이 매번 실패한 적이 있다)
$argument = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}"' -f $ps1

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argument
$weekly = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $day -At $at
$logon = New-ScheduledTaskTrigger -AtLogOn
$logon.Delay = 'PT2M'

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName $taskName -Action $action `
    -Trigger @($weekly, $logon) -Settings $settings -RunLevel Limited -Force | Out-Null

Write-Output "등록 완료: '$taskName' — 매주 $day $($at.ToString('HH:mm')) + 로그온 2분 후"
Write-Output "실행 파일: $ps1"

# 등록 직후 인자가 제대로 들어갔는지 확인해서 출력한다.
$check = (Get-ScheduledTask -TaskName $taskName).Actions[0]
Write-Output "확인 - Execute: $($check.Execute)"
Write-Output "확인 - Arguments: $($check.Arguments)"
