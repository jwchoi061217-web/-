# BNI 맥스 출석 체크인 — 설정 절차

한 번만 하면 되는 작업입니다. 순서대로 따라 하면 30분 안에 끝납니다.
전체 구조와 설계 근거는 [DESIGN.md](DESIGN.md) 참고.

```
NFC/QR → GitHub Pages 체크인 페이지 (docs/bni/checkin/)
       → Google Apps Script 웹앱 (검증 + 노션 토큰 보관)
       → 노션: BNI 맥스 출석 페이지의 3개 DB
```

## 0. 노션 데이터베이스 (이미 생성됨)

노션 워크스페이스의 **`BNI 맥스 출석`** 페이지 아래에 3개 DB가 준비되어 있습니다.

| DB | 용도 | 데이터베이스 ID |
|---|---|---|
| `BNI MAX` | 멤버 명부 (이름·파워팀·업종·상태) | `3be7bf36a26f808694bfee3f6080fc9e` |
| `출석기록` | 출석 원장 — 웹앱이 자동 기록 | `a87d91ad4e5b405fabec36483fc1fdd5` |
| `기기등록` | 폰(기기 토큰) ↔ 멤버 연결 | `60b3c33708454de4b16aed060617c628` |

**멤버 명단을 채워주세요**: `BNI MAX` DB에 멤버를 한 명씩 추가하고
`상태 = 활동` 으로 설정합니다. **`상태`가 `활동`인 행만 체크인 명단에 나옵니다.**
`파워팀` 을 채우면 이름 선택 화면이 파워팀별로 묶여 보입니다.

## 1. 노션 통합(Integration) 만들기

1. https://www.notion.so/my-integrations → **새 통합(New integration)**
2. 이름: `BNI 출석 체크인`, 워크스페이스 선택, 기능은 **콘텐츠 읽기·삽입·업데이트** 3개
3. 생성 후 **시크릿 토큰**(`ntn_...` 또는 `secret_...`)을 복사해 둡니다
4. 노션에서 **`BNI 맥스 출석` 페이지** 열기 → 우상단 `⋯` → **연결(Connections)** →
   방금 만든 통합 추가. **이 페이지 하나만 연결하면 아래 3개 DB 접근이 전부 상속됩니다.**

## 2. Apps Script 웹앱 배포

1. https://script.google.com → **새 프로젝트** (이름: `BNI 출석`)
2. 기본 `Code.gs` 내용을 지우고 이 폴더의 [`apps_script/Code.gs`](apps_script/Code.gs) 전체를 붙여넣기
3. 좌측 톱니(프로젝트 설정) → **"appsscript.json" 매니페스트 파일 표시** 체크 →
   편집기에서 `appsscript.json` 을 [`apps_script/appsscript.json`](apps_script/appsscript.json) 내용으로 교체
4. 프로젝트 설정 맨 아래 **스크립트 속성** 4개 추가:

   | 속성 | 값 |
   |---|---|
   | `NOTION_TOKEN` | 1단계에서 복사한 토큰 |
   | `DB_ROSTER_ID` | `3be7bf36a26f808694bfee3f6080fc9e` |
   | `DB_CHECKIN_ID` | `a87d91ad4e5b405fabec36483fc1fdd5` |
   | `DB_DEVICE_ID` | `60b3c33708454de4b16aed060617c628` |

5. **배포 → 새 배포 → 웹 앱**
   - 실행 계정: **나**
   - 액세스 권한: **모든 사용자**
   - 배포 후 권한 승인(내 계정 → 고급 → 이동)
6. 배포된 **웹 앱 URL**(`https://script.google.com/macros/s/…/exec`)을 복사

**동작 확인** (브라우저나 터미널):

```
curl -L "<웹앱URL>?action=ping"      → {"ok":true,"now":"..."}
curl -L "<웹앱URL>?action=members"   → {"ok":true,"members":[...]}   (활동 멤버 목록)
```

## 3. 체크인 페이지에 웹앱 URL 연결

`config/bni.json` 의 `gas_url` 에 웹앱 URL을 넣고 페이지를 다시 생성해 커밋합니다:

```bash
python -m src.bni_checkin
git add config/bni.json docs/bni/
git commit -m "bni: GAS 웹앱 URL 연결"
git push
```

> URL만 알려주시면 이 단계는 Claude가 대신 처리할 수 있습니다.

게시 주소: `https://jwchoi061217-web.github.io/-/bni/checkin/`

**엔드투엔드 테스트**: 폰에서
`https://jwchoi061217-web.github.io/-/bni/checkin/?tag=TEST&ctr=1` 접속 →
이름 선택 → 체크인 완료 화면 → 노션 `출석기록`에 `방법=테스트` 행이 생겼는지 확인.
(TEST 태그는 모임일·시간 검증을 건너뜁니다. 테스트 행은 노션에서 지우면 됩니다.)

## 4. NFC 태그 쓰기 · QR 인쇄

**준비물**: NTAG213 이상 태그 (금속 위에 붙일 거면 **on-metal 태그**),
폰에 **NFC Tools** 앱 (iOS/Android 무료).

태그 A (입구) 기준 — NFC Tools 에서:

1. **쓰기 → 레코드 추가 → URL**:
   `https://jwchoi061217-web.github.io/-/bni/checkin/?tag=A&ctr=000000`
2. **⚠️ 카운터 미러 설정** — NFC Tools 의 *기타 → 카운터 설정(UID/Counter mirror)* 에서
   **카운터 활성화 + URL 미러**를 켜고, 미러 위치를 URL 끝의 `000000` 자리에 맞춥니다.
   태그가 탭될 때마다 이 6자리가 실제 탭 횟수(16진수)로 자동 교체됩니다 —
   서버가 이 값의 증가를 검증해 **한 번 쓰인 링크의 재사용을 차단**합니다.
3. 쓰기 후 태그를 **잠금(읽기 전용)** 처리 — 덮어쓰기 방지. 잠금은 되돌릴 수 없으니
   먼저 폰으로 태그를 탭해 체크인 페이지가 열리는지 확인한 뒤에 잠급니다.
4. 태그 B (데스크)는 `?tag=B&ctr=000000` 으로 동일하게.

**QR 예비 카드**: `?tag=QR1`, `?tag=QR2` URL로 QR 생성·인쇄 (ctr 없음).
QR은 카운터 검증이 없으므로 예비 수단입니다 — 평상시엔 NFC를 주 수단으로.

**설치**: 태그와 QR을 **나란히** 배치하고 안내 문구는 한 줄:
**"폰 뒷면을 여기에 대세요 · 안 되면 QR"**

## 5. 운영

- **모임 설정 변경** (요일·시간창·휴회일·태그 추가): `apps_script/Code.gs` 상단 `CONFIG`
  수정 → Apps Script 편집기에 반영 → **배포 → 배포 관리 → 새 버전**.
  `config/bni.json` 의 표시용 값도 같이 맞춥니다.
- **서기 보정**: 노션 `출석기록`에서 직접. 결석(A)·의료(M)·대참(S)은 행을 추가하거나
  코드를 바꾸면 됩니다. 폰을 안 가져온 멤버는 `방법=수동` 으로 행 추가.
- **폰 교체한 멤버**: 새 폰에서 태그를 탭하면 이름 선택이 다시 뜹니다(자동 처리).
  `기기등록`의 옛 행은 그대로 둬도 무해하며, 정리하고 싶으면 삭제.
- **개인정보**: `BNI 맥스 출석` 페이지 공유는 회장·부회장·서기로 제한하세요.

## 문제 해결

| 증상 | 원인/조치 |
|---|---|
| 체크인 페이지에 "서버 주소가 설정되지 않았습니다" | `config/bni.json` 의 `gas_url` 미기입 → 3단계 |
| `?action=ping` 이 HTML 로그인 페이지를 반환 | 웹앱 배포의 액세스 권한이 "모든 사용자"가 아님 → 재배포 |
| `?action=members` 가 `Script Property 누락` | 스크립트 속성 4개 확인 → 2-4단계 |
| `?action=members` 가 Notion API 404 | 통합이 `BNI 맥스 출석` 페이지에 연결 안 됨 → 1-4단계 |
| 명단이 비어 있음 | `BNI MAX` 멤버들의 `상태` 가 `활동` 인지 확인 |
| 태그를 탭해도 "이미 사용된 링크" | 카운터 미러 설정이 안 된 태그 → 4-2단계 다시 |
