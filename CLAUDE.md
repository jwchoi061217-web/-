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

## 수집 범위·꼬리표·픽 (2026-10-02 개편 — 요구사항 정의서 2026-09-28 1단계 반영)

**원칙: 수집은 넓게, 좁히기는 보여 줄 때만.** 설정은 전부 `config/gov_sources.json`, 고치면 다음 수집부터
(지금 올라간 공고에 바로 적용하려면 `python -m src.retag`).

- `fields` 8개(원격훈련·평생교육·학술·연구·교육콘텐츠 제작·산업안전보건교육·이러닝·AX·AI·장애인·고용) + `keywords.include`
  가중치(3/2/1)의 **합집합이 수집 범위**다. 하나라도 걸리면 아카이브에 넣는다. `min_score` 로 수집을 거르지 않는다.
  - `keywords.exclude` 는 지원사업이 아닌 글(결과 발표·채용·인사·행정예고·점검 안내)만. 제목·분야에만 적용.
  - 관련도(`relevance`, 0~100) = 걸린 가중치 합 × 10. fields 에만 있는 키워드는 가중치 2(`FIELD_KEYWORD_WEIGHT`).
    `min_score`(2 → 관련도 20)는 **모아보기 기본 화면이 숨기는 기준**일 뿐이고, 숨긴 건수를 보여 주며 한 번에 편다.
  - 역할 태그는 가점·감점이 아니다(FR-KEY-03).
- `roles` 7개(공급기업·수행기관·운영기관·훈련·교육기관·참여기관·수요기업·참여기업)는 판별 구절 목록이다. 공고 하나에
  여러 개 붙고, 아무것도 안 걸리면 빈 목록(화면은 '역할 미확인'). 한글 구절은 띄어쓰기 무시 부분 일치, 영문은 단어 경계.
- `picks.*` 는 **카톡 '이번주 픽'과 주차 페이지(신규)에만** 적용: `min_score`, `exclude`(조선·태양광·수출 같은 주제별 제외),
  `region.allow/drop_county/keep_min_score`, `min_days_left`. 모아보기 아카이브에는 영향이 없다 — 마케팅팀(픽은 짧게)과
  경영기획팀(아카이브는 놓치지 않게)의 요구를 이렇게 나눠 담았다. 옛 최상위 `region`/`min_days_left` 도 picks 로 읽힌다.
- 꼬리표(`src/gov_tags.py`): `fields` `roles` `relevance` `region` `consortium{status,text}` `size_req` `quals` `region_text`
  `region_pref`. **아카이브를 쓸 때마다 전부 다시 매긴다**(`write_archive`) — 설정을 바꾸면 지난 공고에도 반영된다.
  추출하지 못하면 비워 둔다(화면은 '미확인 — 원문 확인'). 추정값을 만들지 않는다.
- 같은 공고가 두 출처에서 오면 1건으로 합치고 `sources[]` 에 둘 다 남긴다(`merge_duplicates`, 공고명·마감 기준).
- `data.json`(진행 중)은 **아카이브에서 매번 다시 뽑는다**(`write_store`). 둘이 어긋나면 아카이브가 맞다.
- 기관명(org)과 본문 속 기관명(`_INSTITUTION_RE`)은 키워드·분야 매칭에서 뺀다 — '장애인고용공단'의 '고용' 때문에 다 걸리는 걸 막는다.
- 걸러낸 건수·출처별 성공/실패는 `collect_gov.collect.last_stats`(`per_source`, `dropped_by_pick` …)와 stderr 로그에 남는다.

### 출처 22곳 (키 불필요 20 + 키 필요 2)

| 모듈 | 출처 |
|---|---|
| `collect_gov.py` | 기업마당(공개 목록 대체 수집) · K-Startup(키) · 고용노동부 RSS · 장애인고용공단 · 한국산업인력공단 · 안전보건공단 |
| `gov_src_g2b.py` | **나라장터**(키) — 용역·물품·공사 `*PPSSrch` 검색어별 조회 + 면허제한·참가가능지역 공고별 조회(`lookup_max`). 키 없이 받는 길은 없음(차세대 나라장터는 SSO 세션 필요, RSS 없음). 참고: `collect_gov.fetch_g2b` 는 옛 용역 전용 경로, 계약 테스트용 |
| `gov_src_ministry.py` | 과기정통부 · 중기부(RSS+HTML) · 교육부 · **e나라도움→보조금통합포털 bojo.go.kr API** · 산업통상부(**motir.go.kr**) · 문체부(RSS+HTML) · 행안부(RSS+HTML) · 복지부(RSS만 — robots) |
| `gov_src_ict.py` | NIPA 사업공고+입찰(AI·클라우드 바우처 공고가 여기 올라옴) · NIA · 수출바우처(**robots Crawl-delay 60초**) · 혁신바우처 |
| `gov_src_agency.py` | 중진공(사이트 JSON API) · 고용24(HRD-Net 통합, GET 쿼리로 열림) · IRIS(접수중 R&D, 접수기간 구조화) |

- 각 모듈의 `SOURCES` 레지스트리를 `collect_gov.external_sources()` 가 모은다. 새 출처는 그 모듈에 `parse_*`/`fetch_*` 와
  `SOURCES` 항목을 넣고 config 에 id 를 적으면 끝. 상세 본문은 소스별 컨테이너를 먼저 잘라야 메뉴 텍스트가 개요로 안 들어간다.
- 구조화된 마감(`STRUCTURED_DEADLINE_SOURCES`: bizinfo·kstartup·g2b·gosims·iris)이 아니면 마감이 비었을 때 '상시'가 아니라
  **'마감 원문 확인'**. nipa 는 입찰공고가 본문 추출이라 넣지 않았다.
- 나라장터 어댑터는 참가가능지역을 조회한 공고에 `region`(표준 지역명)을 직접 적는다 — `collect()` 는 어댑터가 적은 region 을 덮어쓰지 않는다.
  `target` 은 정의서 5-1 순서(지역 → 업종 → 공동수급)로 "지역제한: 서울특별시 · 업종: 학원운영업 …" 한 줄. 모르는 것은 '원문 확인'.
- robots 가 막아 **넣지 않은 곳**: **S2B 학교장터**(s2b.kr·m.s2b.kr `Disallow: /`, API·RSS 없음 — 공급업체 계정의 관심공고 알림 메일이 유일한 경로) · 데이터바우처(kdata) · 국가평생교육진흥원(nile) · 한국연구재단(nrf, IRIS 가 덮음) · 콘진원(kocca) ·
  창업진흥원 게시판(kised, K-Startup API 가 덮음) · HRD4U. 해외 IP 차단·TLS 로 샌드박스에서 **확인 못 한 곳**: 소진공(semas) ·
  KERIS · 서울경제진흥원(sba) · AI바우처(aivoucher). 사무실 PC(한국 IP)에서 되면 추가.
- 수집 시간: 상세 읽기 `detail_max` 와 0.5초 간격 때문에 전체 10~20분. 수출바우처는 60초 간격이라 1~4분 더.
- kead·hrdkorea·kosha 의 함정(EUC-KR·자바 날짜·Vue API)은 아래 '함정' 절 참고. msit 은 셀 값이 인라인 JS 안에 있고,
  mcst 상세는 hwpx 뷰어라 개요가 '붙임 참고' 인 공고가 많다.

### 대시보드 (/gov/)

- 보기 탭(진행 중·마감 임박·이번 주 신규·관심·마감됨) → **역할 필터 줄**(OR, 건수, 기본 전체) → 도구줄 → 표.
  왼쪽: 분야(8) → 세부 키워드 → 참여 조건(소재지 참여 가능만 · 컨소시엄 필수 제외) → 지역 → 마감 달력 → 출처.
- 줄: 마감 · 공고명+역할 배지(색은 구분용) · 기관 · 지역+판정 아이콘 · 관련도 · 기간 · 원문↗. 펼치면 **지역 제한 판정 → 컨소시엄 →
  역할(수동 지정 가능) → 기업 규모 → 필수 자격 → 지원 규모 → 일정 → 신청·문의 → 원문** 순(정의서 5-1). 휴대폰은 전체 화면 시트.
- ⚙ 설정(브라우저 저장): 회사 프로필(소재지 복수·규모·보유 자격) · 관련도 기준 · 제외 키워드 · 분야/키워드 편집(기존 공고에 즉시 재적용).
  특정 회사 값을 기본으로 넣지 않는다 — 소재지를 넣기 전엔 '소재지 미설정'.
- **필터 상태는 전부 주소에 남는다**: `?v=soon&role=공급기업,운영기관&f=AX·AI&rg=서울&q=…&sort=rel&all=1&fit=1&nocons=1&day=…`.
  옛 `#soon` 해시도 연다. 카톡 링크에 쓴다.
- 판별 규칙은 `data.js` 의 `rules`(수집기가 config 에서 실음)를 쓰고, 없으면 HTML 에 박힌 기본 규칙(발행 시점 config). JS 와
  `gov_tags.py` 는 같은 규칙이다 — 한쪽을 고치면 다른 쪽도 고칠 것(테스트: `tests/gov-dashboard.test.cjs`, `tests/test_gov_tags.py`).
- 엑셀(CSV) 내려받기는 현재 필터 결과를 BOM 붙은 CSV 로(FR-OPS-07).
- 아직 **안 된 것**(정의서 2~4단계): 첨부 공고문(HWP/PDF) 텍스트 추출, 팀 공유 저장·진행 상태·담당자·이메일 알림(정적 사이트라
  외부 저장소 필요), 등록·풀 모집 탭·연간 캘린더·서류 체크리스트, 월·수·금 수집 주기(PC 스케줄러 변경이면 됨).
- 카톡 기본 스타일은 `picks`("이번주 픽 5건", `src/message.py`). 첫 줄은 반드시 주차 페이지 링크. 픽은 점수 → 마감 임박 → 최근 게시 순.
- `docs/gov/archive.json` 은 **지우지 않는 누적본**, `docs/gov/archive/<날짜>.json` 은 주차 스냅샷, `data.json` 은 진행 중만.
  대시보드는 `data.js`(archive 와 같은 내용)를 `<script>` 로 읽는다 — `fetch()` 는 file:// 에서 막힌다.
- `--mock` 은 임시 폴더에 쓴다. 실제 아카이브에 fixtures 를 섞지 말 것.

| 파일 | 역할 |
|---|---|
| `src/categories.py` | 카테고리 레지스트리 — 문구·색·최소건수는 **전부 여기** |
| `src/collect.py` | 네이버 뉴스 수집 |
| `src/collect_gov.py` | 공고 수집 파이프라인(7개 소스 내장)·정규화·키워드 점수·픽 좁히기·아카이브/저장소 |
| `src/gov_src_ministry.py` `gov_src_ict.py` `gov_src_agency.py` | 추가 출처 15곳 어댑터 (`SOURCES` 레지스트리) |
| `src/gov_tags.py` | 꼬리표 — 분야·역할·관련도·컨소시엄·규모·자격·지역 근거 |
| `src/retag.py` | 수집 없이 아카이브 꼬리표만 다시 매기고 대시보드 재생성 |
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
python -m src.main --only gov --no-state --out C:\temp\preview   # docs/ 안 건드리고 미리보기
python -m unittest discover -s tests -p "test_*.py" && node --test tests/gov-dashboard.test.cjs
python -m src.retag                    # config 의 분야·역할·키워드를 지금 아카이브에 다시 적용 + 대시보드 재생성
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
`run_collect.ps1` 은 2026-10-02 부터 **수집 전에 `git pull --rebase --autostash`** 를 하고, push 전에도 rebase 한다.
그래도 PC 의 작업 사본에 충돌이 남으면 `collect.log` 에 경고가 남으니, 코드를 다른 환경에서 크게 고쳐 올렸으면
PC 의 `C:\Users\user\modu-news` 에서 한 번 `git pull` 해 두는 게 안전하다.
`gh` CLI 는 미인증. 주간 수집 스크립트가 docs/ 를 자동으로 올린다 — 실패하면 `windows/collect.log` 에 경고가 남는다.

## 남은 작업

- API 키 미등록(`.env`): `DATA_GO_KR_KEY`(K-Startup·나라장터) `BIZINFO_KEY` `NAVER_CLIENT_ID/SECRET`.
  없어도 돌아가지만 K-Startup·나라장터 공고와 뉴스는 빠진다. 넣은 뒤 `python tools/check_keys.py`.
- `config/rooms.json` 에 실제 단톡방 미지정 (대시보드에서 창 목록으로 선택)
- 작업 스케줄러 `모두의뉴스_발송` 미등록
- `C:\Users\user\카카오톡단톡방관리` 는 이 저장소의 8월 5일자 복제본. 이쪽(modu-news)이 본체다.
- 나라장터 `min_budget`(기본 5천만원)은 임시값 — 실 키로 첫 실행 후 건수 보고 조정
- 공고 API 응답 필드명은 별칭 목록(`_first`)으로 방어해 뒀지만 실 키로 받아본 뒤 정리 필요
- 요구사항 정의서 2~4단계(위 '대시보드' 절의 '안 된 것'). 팀 공유 저장은 구글 시트/서버리스 중 택일이 먼저.
- 샌드박스에서 못 연 출처(소진공·KERIS·서울경제진흥원·AI바우처)를 사무실 PC 에서 확인해 추가
- 수집 범위가 넓어져 첫 PC 실행 때 상세 읽기가 오래 걸릴 수 있다(10~20분). `collect.log` 의 출처별 건수를 보고 `detail_max` 조정

## 주의

카카오는 단톡방에 메시지를 넣는 공식 API를 제공하지 않는다. `windows/kakao_send.py` 는
PC 카카오톡 창을 조작하는 비공식 방식이라 계정 이용제한 가능성이 있다(사용자 인지·동의함).
