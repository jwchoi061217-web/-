# 모두의러닝 주간 HRD·산업안전 뉴스 카카오톡 자동 공유

매주 월요일 아침 8시(KST), HRD 뉴스와 산업안전 뉴스를 자동 수집하여 카카오톡 단톡방에 공유하는 시스템입니다.
메시지 첫 줄의 링크가 **모두의러닝 홍보 썸네일 카드**로 표시되어, 받는 사람이 열기 전에 브랜드를 먼저 보게 됩니다.

## 동작 구조

```
GitHub Actions (매주 월 08:00 KST)
  1. 네이버 뉴스 API로 HRD / 산업안전 뉴스 수집 (최근 7일, 중복 제거, 카테고리당 10건)
  2. 모두의러닝 홍보 썸네일(1080×1080) 자동 생성
  3. config/rooms.json 기반으로 방별 메시지 조립
  4. GitHub Pages(docs/)에 발행: 주차별 페이지(og:image 썸네일) + payload.json
안드로이드 폰 (메신저봇R)
  5. payload.json을 30분마다 확인 → 설정된 방에 자동 전송 (중복 발송 방지)
```

### 뉴스 웹페이지 (기사 클릭 → 요약 → 원문)

카톡 메시지의 링크를 열면 모바일 웹페이지가 나옵니다:

- **리스트 페이지**: 전체 / HRD / 산업안전 탭. 방 카테고리에 맞는 페이지로 링크됩니다 (HRD 전용 방 → HRD 리스트).
- **디테일 페이지**: 기사 제목을 누르면 언론사·날짜·**뉴스 요약**이 보이고, [원문 기사 보기] 버튼으로 이동. 하단에 모두의러닝 홍보 배너.

### 메시지 스타일 (방마다 선택, `style` 필드)

- **compact (기본)**: 링크(썸네일 카드) + 카테고리별 TOP3 미리보기 + "링크를 눌러 전체 보기" — 메시지 1건, 깔끔함
- **full**: 카테고리당 10건 제목+링크 전체 나열 — HRD만/안전만 방은 1건, 혼합 방은 2건 연속

## 최초 설정 (1회)

### 1. 네이버 API 키 발급
1. https://developers.naver.com/apps → 애플리케이션 등록 (검색 API 선택, 무료)
2. GitHub 저장소 → Settings → Secrets and variables → Actions에 등록:
   - `NAVER_CLIENT_ID`
   - `NAVER_CLIENT_SECRET`

### 2. GitHub Pages 활성화
저장소 → Settings → Pages → Source: **Deploy from a branch**, Branch: 기본 브랜치의 **/docs** 폴더 선택.

> ⚠️ GitHub Actions의 예약 실행(cron)은 **기본 브랜치**에서만 동작합니다.

### 3. 단톡방 설정
`config/rooms.json`을 수정합니다. `name`은 **카카오톡 방 이름과 한 글자도 다르지 않게** 입력하세요.

```json
{ "rooms": [
    { "name": "우리 회사 교육방", "categories": ["hrd"],           "enabled": true },
    { "name": "안전관리자 모임",   "categories": ["safety"],        "enabled": true },
    { "name": "통합 소식방",       "categories": ["hrd", "safety"], "enabled": true },
    { "name": "전문 나열 원하는 방", "categories": ["hrd"], "style": "full", "enabled": true }
] }
```

`style`을 생략하면 compact(링크 중심)입니다.

### 4. 메신저봇R 설치 (안드로이드 폰)
1. 메신저봇R 앱 설치 후 **알림 접근 권한** 허용, **배터리 최적화 제외** 설정
2. 새 봇 생성 → `android/modu_news_bot.js` 내용 붙여넣기 → 컴파일 & 활성화
3. 폰은 상시 전원 연결 + 카카오톡 알림이 꺼져 있으면 안 됩니다

> ⚠️ **세션 제약**: 봇 앱을 (재)시작한 후, 각 방에서 **알림을 1회 이상 받아야** 그 방으로 전송할 수 있습니다.
> 봇이 30분마다 재시도하므로 방에 새 메시지가 올라오면 자동으로 발송됩니다.
> 아무 방에서나 `!뉴스` 를 입력하면 즉시 확인·발송합니다.

## 테스트

```bash
pip install -r requirements.txt
python -m src.main --mock          # API 키 없이 tests/fixtures 데이터로 전체 실행
python -m src.main                 # 실제 수집 (NAVER_CLIENT_ID/SECRET 환경변수 필요)
```

GitHub에서는 Actions → weekly-news → **Run workflow** (mock 체크 시 키 없이 테스트)로 수동 실행할 수 있습니다.

썸네일 미리보기 캐시 문제로 카드가 안 보이면 [카카오 공유 디버거](https://developers.kakao.com/tool/debugger/sharing)에서 해당 주차 URL의 캐시를 초기화하세요. (주차마다 고유 URL을 쓰므로 평상시에는 문제없습니다.)

## 주의사항 (중요)

- **비공식 자동화 위험**: 메신저봇R은 카카오 공식 기능이 아니며, 운영 정책에 따라 **계정이 제재될 수 있습니다**. 업무용 보조 계정 사용을 권장하며, 발송 빈도(주 1회)와 방 수를 최소한으로 유지하세요. 카카오는 단톡방 봇 API를 공식 제공하지 않습니다.
- **방 이름 불일치 시 조용히 미발송**됩니다. 메신저봇R 로그에서 "세션 없음" / "전송 실패" 메시지를 확인하세요.
- **이미지 직접 전송 불가**: 메신저봇R은 텍스트만 보낼 수 있어, 썸네일은 링크 미리보기 카드 방식으로 노출됩니다.
- 뉴스가 카테고리당 3건 미만인 주(연휴 등)에는 발행이 중단되고 Actions가 실패 처리됩니다(이메일 알림).
- 네이버 API 무료 쿼터는 일 25,000회로, 주 10회 호출 수준이라 여유가 큽니다. 키는 절대 코드에 넣지 말고 Secrets로만 관리하세요.

## 파일 구조

```
config/rooms.json                 # 단톡방 설정 (이 파일만 수정하면 됨)
src/                              # 수집·메시지·썸네일·발행 파이프라인
android/modu_news_bot.js          # 메신저봇R 스크립트
docs/                             # GitHub Pages 산출물 (자동 생성)
tests/fixtures/                   # 테스트용 뉴스 데이터
.github/workflows/weekly-news.yml # 매주 월 08:00 KST 자동 실행
```
