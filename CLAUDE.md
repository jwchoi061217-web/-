# 모두의러닝 주간 소식 자동 공유

매주 월요일 아침, 정부지원사업 공고와 HRD·산업안전 뉴스를 수집해 GitHub Pages로 발행하고
그 링크를 카카오톡 단톡방에 공유하는 시스템. 사용자 설명은 `README.md` 참고.

- 저장소: `jwchoi061217-web/-` (Public, 이름이 문자 그대로 `-`)
- 사이트: https://jwchoi061217-web.github.io/-/
- 공개 대시보드: https://jwchoi061217-web.github.io/-/gov/ (주소 고정, 단톡방 공지용)

## 구조

```
수집  이 PC 작업 스케줄러 '모두의뉴스_수집' (월 08:00 + 로그온 catch-up)
      → windows/run_collect.ps1 → python -m src.main → docs/ 갱신
공개  수집 직후 run_collect.ps1 이 docs/ 를 커밋·push → Pages (자동)
발송  이 PC 작업 스케줄러 (월 08:05 + 로그온 catch-up) → windows/kakao_send.py  ※ 미등록
```

2026-09-28 에 수집 주체를 GitHub Actions → 이 PC 로 옮겼다. Secrets 가 하나도 없어
Actions 가 8주 연속 실패했기 때문이다. workflow 의 schedule 은 주석 처리돼 있고
수동 실행(workflow_dispatch)만 남아 있다. **PC 와 Actions 를 동시에 켜지 말 것** —
둘 다 docs/ 를 고쳐 push 가 충돌한다.

PC 가 월요일에 꺼져 있었으면 다음 로그온 때 따라잡는다. 같은 주에는 한 번만 수집한다
(`windows/collect_state.json`). 로그는 `windows/collect.log`.

## 키워드와 아카이브

- 키워드는 `config/gov_sources.json` 의 `keywords.include / exclude`. 고치면 다음 수집부터 반영.
  영문 키워드(AI·DX)는 단어 경계로, 한글은 부분 일치로 본다. 기관명은 매칭에서 뺐다.
- `docs/gov/archive.json` 은 **지우지 않는 누적본**(마감 공고 포함),
  `docs/gov/archive/<날짜>.json` 은 주차 스냅샷. `data.json` 은 진행 중만.
- 대시보드는 `data.js`(archive 와 같은 내용)를 `<script>` 로 읽는다 —
  `fetch()` 는 file:// 에서 막혀 로컬에서 열면 목록이 비기 때문.
- `--mock` 은 임시 폴더에 쓴다. 실제 아카이브에 fixtures 를 섞지 말 것.
- 기업마당은 `BIZINFO_KEY` 가 없으면 공개 목록 페이지에서 수집한다(robots.txt 허용 경로, 0.5초 간격).
  K-Startup 목록 페이지는 robots.txt 가 막고 있어 API 키 없이는 수집하지 않는다.

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

2026-09-28 부터 `modu-bi` 스킬(html-kit) 기준을 따른다.

- 선라이트 옐로우 `#FDB515` · 인사이트 네이비 `#003362` · 딥네이비 `#00234A` · 그라운드 브라운 `#545046`
- 다크 네이비 그라데이션 히어로 + 옐로우 ▶ 키커, Pretendard, 카드 radius 20px
- 공식 로고는 `assets/brand/*.png` 를 base64 임베드 (밝은 배경 light / 네이비 dark)
- 옐로우는 글자색으로 쓰지 않는다. 옐로우 배경 위 글자는 딥네이비
- 마감 임박 색은 BI에 없어 그룹 패밀리인 모두세이프티 오렌지 `#FF5F1B`를 차용 (D-3 이하)
- 카톡 썸네일(`src/thumbnail.py`)은 아직 예전 흰 바탕 디자인이다

색·타입·네비·푸터는 **`src/theme.py` 한 곳**에서 바꾸면 전 페이지에 반영된다.

## 배포

명령줄 `git push` 가 된다(Git Credential Manager 에 로그인 정보가 있음, 2026-09-28 확인).
`gh` CLI 는 미인증. 주간 수집 스크립트가 docs/ 를 자동으로 올린다 — 실패하면 `windows/collect.log` 에 경고가 남는다.

## 남은 작업

- API 키 미등록(`.env`): `DATA_GO_KR_KEY`(K-Startup·나라장터) `BIZINFO_KEY` `NAVER_CLIENT_ID/SECRET`.
  없어도 돌아가지만 K-Startup·나라장터 공고와 뉴스는 빠진다. 넣은 뒤 `python tools/check_keys.py`.
- `config/rooms.json` 에 실제 단톡방 미지정 (대시보드에서 창 목록으로 선택)
- 작업 스케줄러 `모두의뉴스_발송` 미등록
- `C:\Users\user\카카오톡단톡방관리` 는 이 저장소의 8월 5일자 복제본. 이쪽(modu-news)이 본체다.
- 나라장터 `min_budget`(기본 5천만원)은 임시값 — 실 키로 첫 실행 후 건수 보고 조정
- 공고 API 응답 필드명은 별칭 목록(`_first`)으로 방어해 뒀지만 실 키로 받아본 뒤 정리 필요

## 주의

카카오는 단톡방에 메시지를 넣는 공식 API를 제공하지 않는다. `windows/kakao_send.py` 는
PC 카카오톡 창을 조작하는 비공식 방식이라 계정 이용제한 가능성이 있다(사용자 인지·동의함).
