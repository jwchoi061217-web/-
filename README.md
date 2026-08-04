# 모두의러닝 주간 소식 자동 공유

매주 월요일 아침, **정부지원사업 공고**와 **HRD·산업안전 뉴스**를 자동 수집해
GitHub Pages에 주차별 페이지로 발행하고, 그 링크를 카카오톡 단톡방에 공유하는 시스템입니다.

링크가 **모두의러닝 브랜드 썸네일 카드**로 표시되어, 받는 사람이 열기 전에 브랜드를 먼저 봅니다.
여러 사람이 각자 편한 시간에 열어볼 수 있고, 마감이 임박한 공고가 맨 위에 옵니다.

## 동작 구조

```
① GitHub Actions — 매주 월 08:00 KST (PC가 꺼져 있어도 항상 실행)
     정부지원사업 공고 4개 소스 + 네이버 뉴스 수집
   → 마감 지난 공고 제외 · 중복 제거 · 이미 내보낸 공고 제외
   → 주차별 썸네일(1080×1080) 생성
   → GitHub Pages 발행:  docs/issues/<날짜>/   그 주에 새로 뜬 것 (카톡으로 보냄)
                         docs/gov/            진행 중인 공고 전부 (상시 주소)
                         docs/latest/payload.json

② 이 PC — 매주 월 08:05 (꺼져 있었으면 로그온 2분 뒤 따라잡기)
     작업 스케줄러 → windows/kakao_send.py
   → payload.json 을 읽어 설정된 단톡방 창에 링크 메시지 전송
```

발행(①)과 발송(②)을 나눈 이유: 월요일 아침에 PC가 켜져 있지 않을 수 있기 때문입니다.
페이지는 무조건 만들어지고, 발송만 PC 사정에 따라 조금 늦어집니다.

## 수집 소스

| 구분 | 소스 | 필터 | 필요한 키 |
|---|---|---|---|
| 공고 | 기업마당 지원사업 공고 | 없음 (전부) | `BIZINFO_KEY` |
| 공고 | 창업진흥원 K-Startup 사업공고 | 없음 (전부) | `DATA_GO_KR_KEY` |
| 공고 | 조달청 나라장터 **용역** 입찰공고 | **금액 하한선** (기본 5천만원) | `DATA_GO_KR_KEY` |
| 공고 | 고용노동부 알려드립니다 (RSS) | 없음 (전부) | 불필요 |
| 뉴스 | 네이버 뉴스 API (HRD / 산업안전) | 카테고리당 10건 | `NAVER_CLIENT_ID/SECRET` |

> **나라장터만 하한선을 두는 이유** — 전 부처·전 지자체 입찰이 모두 들어와 물량이 다른 소스와
> 비교가 안 될 만큼 큽니다. 하한선 없이는 페이지가 입찰공고로 뒤덮입니다.
> 첫 실행 후 실제 건수를 보고 `config/gov_sources.json` 의 `min_budget` 을 조정하세요.
> (관리 대시보드에서 바로 바꿀 수 있습니다.)

공고는 **한 번 내보낸 것을 다시 올리지 않습니다.** `docs/state/seen_gov.json` 에 내보낸 공고를
기록하고 Actions가 함께 커밋합니다. 그래서 매주 "이번 주에 새로 뜬 공고"만 쌓입니다.

4개 소스 중 하나가 죽어도 나머지로 발행하고, 실패한 소스는 페이지에 표시합니다.

## 최초 설정

### 1. API 키 발급

| 키 | 발급처 |
|---|---|
| `BIZINFO_KEY` | https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi 하단 "API 사용 신청" → 이메일 수신 |
| `DATA_GO_KR_KEY` | data.go.kr 에서 [K-Startup 조회서비스](https://www.data.go.kr/data/15125364/openapi.do) 와 [나라장터 입찰공고정보서비스](https://www.data.go.kr/data/15129394/openapi.do) 각각 활용신청 (키는 하나를 공용) |
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | https://developers.naver.com/apps → 애플리케이션 등록 (검색 API, 무료) |

> data.go.kr 키는 **일반 인증키(Decoding)** 를 쓰세요. 인코딩된 키를 넣으면 이중 인코딩되어 실패합니다.

저장소 → Settings → Secrets and variables → Actions 에 위 4개를 등록합니다.

### 2. GitHub Pages

저장소 → Settings → Pages → Source: **Deploy from a branch**, Branch: 기본 브랜치의 **/docs**.

> Actions의 예약 실행(cron)은 **기본 브랜치**에서만 동작합니다.

### 3. 이 PC 설정

```powershell
git clone https://github.com/jwchoi061217-web/-.git C:\Users\user\modu-news
cd C:\Users\user\modu-news
pip install -r requirements.txt
```

푸시까지 하려면 GitHub 자격증명이 필요합니다: `winget install GitHub.cli` 후 `gh auth login`.

### 4. 단톡방 지정 — 관리 대시보드

```powershell
powershell -ExecutionPolicy Bypass -File windows\start_dashboard.ps1
```

http://127.0.0.1:8422 이 열립니다. [방 관리] 탭에서:

1. 카카오톡에서 **보낼 단톡방을 더블클릭해 별도 창으로 열어둡니다** (필수)
2. 대시보드 하단 드롭다운에 그 방이 나타나면 [＋ 방 추가]
3. 보낼 내용(HRD / 산업안전 / 정부지원사업)을 체크하고 [저장]
4. [현황] 탭에서 [👀 대상만 확인]으로 창을 제대로 찾는지 먼저 시험
5. 문제없으면 사용을 켜고 [🧪 테스트방에만]으로 실제 전송 확인

> 방 이름을 직접 타이핑하지 않고 **열려 있는 창 목록에서 고르게** 되어 있습니다.
> 이름이 한 글자만 달라도 발송이 조용히 실패하기 때문입니다.

### 5. 발송 스케줄 등록

대시보드 [소스·스케줄] 탭에서 요일·시각을 정하고 [작업 등록 / 변경] (관리자 승인 필요).
직접 실행하려면:

```powershell
powershell -ExecutionPolicy Bypass -File windows\register_task.ps1 -Weekday 1 -Hour 8 -Minute 5
```

## 두 가지 페이지 — 무엇을 어디에 쓰나

| | 주차 페이지 | 공고 모아보기 |
|---|---|---|
| 주소 | `/issues/<날짜>/gov.html` (매주 새 주소) | **`/gov/` (항상 같은 주소)** |
| 내용 | 그 주에 **새로 뜬** 공고만 | 마감 안 지난 공고 **전부** |
| 쓰임 | 매주 월요일 카톡으로 발송 | 단톡방 **공지에 고정**해두고 아무때나 |

`/gov/` 는 한 번 공지에 걸어두면 계속 최신 상태로 유지됩니다. 매주 주소가 바뀌지 않습니다.

**공고 모아보기에 있는 것**
- 요약 타일 — 진행 중 / 이번주 신규 / 7일 내 마감 / 내 관심
- 검색(공고명·기관·대상) + 필터(소스별, 7일·30일 내 마감, 이번주 신규, 관심만) + 정렬
- **마감 달력** — 날짜별 마감 건수를 달력에 표시, 날짜를 누르면 그날 마감 공고만
- **⭐관심 표시와 메모** — 공고마다 별표와 짧은 메모

> ⚠️ 관심 표시·메모는 **보는 사람 브라우저에만** 저장됩니다(localStorage). GitHub Pages는 정적
> 페이지라 서버에 저장할 곳이 없습니다. 그래서 다른 사람에게는 보이지 않고, 브라우저 데이터를
> 지우거나 다른 기기에서 열면 사라집니다. 페이지 하단에도 같은 안내가 있습니다.
> 여러 사람이 공유하는 메모가 필요해지면 별도 저장소(구글 시트 등)를 붙여야 합니다.
>
> 대시보드 썸네일에는 **건수·날짜를 넣지 않았습니다.** 주소가 고정이라 카카오가 미리보기를
> 캐시하는데, 숫자를 넣으면 몇 주 뒤 카드에 옛날 숫자가 남기 때문입니다.

## 관리 대시보드

`windows\start_dashboard.ps1` → http://127.0.0.1:8422 (로컬 전용, 외부에 열지 마세요)

- **현황** — 이번주 수집 건수, 소스별 내역, 방별 발송 상태, 다음 실행 예정, 즉시 발송 버튼
- **방 관리** — 방마다 받을 내용·형식·사용 여부. 방 이름은 열린 카톡 창에서 선택
- **미리보기** — 방마다 **실제로 나갈 메시지 원문**을 보내기 전에 확인
- **소스·스케줄** — 소스 on/off, 나라장터 금액 하한선, 발송/발행 시각
- **이력** — 주차별 수집 건수와 방별 발송 결과
- **로그** — `windows/send.log`

## 직접 실행

```bash
python -m src.main --mock          # API 키 없이 fixtures 로 전 구간 실행
python -m src.main                 # 실제 수집
python -m src.main --only gov      # 공고만
python -m src.main --no-state      # '이미 보낸 공고' 기록을 남기지 않음 (테스트용)

python windows/kakao_send.py --local --dry-run   # 전송 없이 대상 확인
python windows/kakao_send.py --local --test-only # test:true 방에만
python windows/kakao_send.py --local --force     # 이미 보낸 주차도 다시
```

GitHub에서는 Actions → weekly-publish → **Run workflow** (mock 체크 시 키 없이 테스트).

## 주의사항

- **카카오는 단톡방에 메시지를 넣는 공식 API를 제공하지 않습니다.** 이 시스템은 PC 카카오톡 창을
  사람이 하듯 조작합니다. 카카오 이용약관 위반 소지가 있어 **계정이 제재될 수 있습니다.**
  업무용 보조 계정 사용을 권하고, 발송 빈도(주 1회)와 방 수를 최소한으로 유지하세요.
- **발송하려면 해당 단톡방이 별도 창으로 열려 있어야 합니다.** 창을 닫으면 발송이 실패합니다
  (실패는 로그에 남고 종료 코드가 0이 아닙니다 — 조용히 넘어가지 않습니다).
- **발송 중 몇 초간 카카오톡 창이 앞으로 나옵니다.** 그동안 키보드·마우스를 건드리면 엉뚱한 곳에
  입력될 수 있습니다. 방해가 곤란하면 `--background` 옵션이 있지만 카카오톡 버전에 따라
  동작하지 않을 수 있습니다.
- **페이지는 인터넷에 공개됩니다** (카카오 미리보기 크롤러가 읽어야 썸네일 카드가 뜹니다).
  공고 정보만 올리고 사내 코멘트는 넣지 마세요.
- 썸네일이 안 보이면 [카카오 공유 디버거](https://developers.kakao.com/tool/debugger/sharing)에서
  해당 주차 URL의 캐시를 초기화하세요. 주차마다 URL이 달라 평상시에는 문제없습니다.
- 뉴스가 카테고리당 3건 미만이면 발행이 중단됩니다(연휴 등). 공고는 0건이어도 발행합니다.

## 파일 구조

```
config/rooms.json                 발송 대상 방 (대시보드에서 편집)
config/gov_sources.json           공고 소스 on/off · 나라장터 금액 하한선
src/categories.py                 카테고리 레지스트리 — 문구·색·최소건수는 전부 여기
src/collect.py                    네이버 뉴스 수집
src/collect_gov.py                정부지원사업 공고 4개 소스 수집·정규화·신규 판정
src/main.py                       파이프라인 오케스트레이터
src/message.py                    방별 카톡 메시지 조립
src/publish.py                    주차 페이지 HTML 생성 (og 태그 포함)
src/gov_dashboard.py              공고 모아보기 대시보드 (/gov/) 생성
src/thumbnail.py                  브랜드 썸네일 생성
windows/kakao_win.py              카카오톡 창 탐색·클립보드·키 입력
windows/kakao_send.py             발송기 (중복 방지 · 실패 시 비0 종료)
windows/dashboard/                관리 대시보드 (포트 8422)
windows/register_task.ps1         작업 스케줄러 등록 (관리자 권한)
windows/run_send.ps1              스케줄러가 호출하는 실행 스크립트
docs/                             GitHub Pages 산출물 (자동 생성)
docs/gov/data.json                진행 중인 공고 누적 저장소 (대시보드가 읽음)
docs/state/seen_gov.json          이미 내보낸 공고 기록 (주차 페이지 중복 방지용)
tests/fixtures/                   mock 실행용 샘플 데이터
.github/workflows/weekly-news.yml 매주 월 08:00 KST 발행
```

> `.ps1` 파일은 **UTF-8 BOM** 으로 저장해야 합니다. BOM이 없으면 PowerShell 5.1이 한글 주석을
> 깨뜨려 다음 줄 코드를 삼킵니다.
