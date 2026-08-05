# 모두의러닝 주간 소식 자동 공유

매주 월요일 아침, 정부지원사업 공고와 HRD·산업안전 뉴스를 수집해 GitHub Pages로 발행하고
그 링크를 카카오톡 단톡방에 공유하는 시스템. 사용자 설명은 `README.md` 참고.

- 저장소: `jwchoi061217-web/-` (Public, 이름이 문자 그대로 `-`)
- 사이트: https://jwchoi061217-web.github.io/-/
- 공개 대시보드: https://jwchoi061217-web.github.io/-/gov/ (주소 고정, 단톡방 공지용)

## 구조

```
발행  GitHub Actions (월 08:00 KST) → docs/ 커밋 → Pages
발송  이 PC 작업 스케줄러 (월 08:05 + 로그온 catch-up) → windows/kakao_send.py
```

발행과 발송을 나눈 이유: 월요일 아침에 PC가 켜져 있다는 보장이 없다.
페이지는 무조건 만들어지고 발송만 늦어진다.

| 파일 | 역할 |
|---|---|
| `src/categories.py` | 카테고리 레지스트리 — 문구·색·최소건수는 **전부 여기** |
| `src/collect.py` | 네이버 뉴스 수집 |
| `src/collect_gov.py` | 공고 4개 소스 수집·정규화·신규 판정·누적 저장소 |
| `src/main.py` | 오케스트레이터 |
| `src/message.py` | 방별 카톡 메시지 조립 |
| `src/theme.py` | **공통 디자인 시스템** — 주차 페이지와 대시보드가 함께 씀 |
| `src/publish.py` | 주차 페이지 HTML |
| `src/gov_dashboard.py` | 공고 모아보기 `/gov/` |
| `src/thumbnail.py` | 카톡 미리보기 썸네일 (1080×1080) |
| `windows/kakao_win.py` | 카카오톡 창 탐색·클립보드·키 입력 |
| `windows/kakao_send.py` | 발송기 (중복 방지, 실패 시 비0 종료) |
| `windows/dashboard/` | 로컬 관리 대시보드 (포트 8422) |

## 실행

```bash
python -m src.main --mock              # 키 없이 fixtures 로 전 구간
python -m src.main --only gov          # 공고만
python -m src.main --no-state          # '이미 보낸 공고' 기록 안 남김
python windows/kakao_send.py --local --dry-run   # 전송 없이 대상 확인
powershell -ExecutionPolicy Bypass -File windows\start_dashboard.ps1
```

## 반드시 알아야 할 함정 (전부 실물로 확인함)

1. **카톡 채팅창 클래스는 `EVA_Window_Dblclk`** (`#32770` 아님). 메인 창도 같은 클래스라
   **입력창 `RICHEDIT50W` 존재 여부로 채팅방을 구분**한다. 클래스명이 대문자라 대소문자를
   구분해 비교하면 못 찾는다.
2. **공고 링크 정규화에서 쿼리스트링을 떼면 안 된다.** 정부 포털은 공고 ID가
   `?pblancId=` `?pbancSn=` `?bidno=` 처럼 쿼리에 있다. 뉴스처럼 자르면 한 사이트의
   모든 공고가 같은 URL로 뭉개진다(22건→4건 버그).
3. **기업마당 상세 주소는 `/sii/siia/selectSIIA200Detail.do?pblancId=`.**
   예전 `/web/lay1/bbs/...` 형식은 현재 리다이렉트로만 살아 있어 기대면 안 된다.
4. **고용노동부 RSS는 `<pubDate>`가 아니라 Dublin Core `<dc:date>`** 를 쓴다.
5. **`.ps1` 은 UTF-8 BOM 필수.** BOM 없으면 PS5.1이 한글 주석으로 다음 줄을 삼킨다.
   `.bat` 은 반대로 **CP949 또는 순수 ASCII** — `chcp 65001` + 한글 조합은 창이 그냥 닫힌다.
6. 스케줄러 작업의 `-File` 인자는 경로를 따옴표로 감쌀 것(공백·역슬래시로 깨진 전례 있음).

## 디자인

**모두의교육그룹 BI** 적용. 출처는 브랜딩북 29p
(`C:\Users\user\Downloads\work\presentations\one-brand-bi`).

- 선라이트 옐로우 `#FDB515` · 그라운드 브라운 `#545046` · 인사이트 네이비 `#003362`
- Neutral `#F5F5F5 #EAE8E8 #C2C2C2 #7A7A7A #111111`
- 시그니처 장치: 라벨 아래 짧은 옐로우 룰(24px) — 브랜딩북이 전 페이지에서 쓰는 장치
- 로고 마크(2×2: 라운드 사각·ㄷ자·원·재생 삼각형)를 인라인 SVG와 PIL로 재현
- 마감 임박 색은 BI에 없어 그룹 패밀리인 모두세이프티 오렌지 `#FF5F1B`를 차용 (D-3 이하)

색·타입·네비·푸터는 **`src/theme.py` 한 곳**에서 바꾸면 전 페이지에 반영된다.

## 배포

이 PC에는 git 자격증명이 없다. **GitHub Desktop을 열고 `Push origin`** 을 누르는 방식.
(로그인은 이미 완료. `gh` CLI도 설치돼 있으나 미인증.)

## 남은 작업

- 저장소 Secrets 미등록: `NAVER_CLIENT_ID` `NAVER_CLIENT_SECRET` `BIZINFO_KEY` `DATA_GO_KR_KEY`
  → ⚠️ **네이버 키가 없으면 월요일 자동 실행이 통째로 실패한다** (`collect.py`가 환경변수를 필수로 읽음)
- `config/rooms.json` 에 실제 단톡방 미지정 (대시보드에서 창 목록으로 선택)
- 작업 스케줄러 `모두의뉴스_발송` 미등록
- 나라장터 `min_budget`(기본 5천만원)은 임시값 — 실 키로 첫 실행 후 건수 보고 조정
- 공고 API 응답 필드명은 별칭 목록(`_first`)으로 방어해 뒀지만 실 키로 받아본 뒤 정리 필요

## 주의

카카오는 단톡방에 메시지를 넣는 공식 API를 제공하지 않는다. `windows/kakao_send.py` 는
PC 카카오톡 창을 조작하는 비공식 방식이라 계정 이용제한 가능성이 있다(사용자 인지·동의함).
