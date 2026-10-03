# AGENTS.md — GPT(Codex 등) 작업 안내

이 저장소는 Claude 와 GPT 가 번갈아 작업한다. Claude 토큰이 떨어지면 GPT 가 이어받는다.
**프로젝트 설명·구조·함정은 전부 `CLAUDE.md` 에 있다 — 작업 전에 반드시 먼저 읽을 것.** 이 파일은 자주 맡기는 일의 순서만 적는다.

## 공통 규칙

- 답은 한국어로, 짧고 직설적으로.
- `docs/` 는 수집 결과물이다. 손으로 고치지 말고 명령으로 다시 만든다.
- `.cache/` 와 `--mock` 결과는 커밋하지 않는다. fixtures 를 실제 아카이브에 섞지 말 것.
- 코드를 고쳤으면 커밋 전에 테스트를 돌린다:
  `python -m unittest discover -s tests -p "test_*.py" && node --test tests/gov-dashboard.test.cjs`
- `src/gov_tags.py` 를 고치면 `src/gov_dashboard.py` 의 JS 규칙도 같이 고친다(같은 규칙).
- push 는 `main` 에 바로 한다. 사무실 PC 수집 스크립트와 겹치지 않게 push 전에 `git pull --rebase`.

## "나라장터 갱신해줘" (API 키가 없는 동안)

나라장터 목록은 사람이 연 브라우저 세션에서만 열린다. 상세는 세션 없이 열린다.

1. 크롬에서 https://www.g2b.go.kr → 입찰 → 입찰공고 → **입찰공고목록**을 연다(로그인 불필요, 공지 팝업은 닫는다).
2. F12 → Console 에 `tools/g2b_browser_export.js` 전체를 붙여 넣고 Enter → 화면의 **[검색]** 을 한 번 누른다.
   검색어 12개(교육·훈련·연수·이러닝·콘텐츠·안전보건·안전교육·HRD·장애인·역량강화·AI·디지털)를 1개월치 조회해
   `g2b_export.json` 이 내려받기 폴더에 저장된다.
3. 저장소에서:
   ```
   python -m src.g2b_web import %USERPROFILE%\Downloads\g2b_export.json --details .cache/g2b_details.json --push
   ```
   상세를 공고마다 받고(0.5초 간격, 500건이면 5~10분), 아카이브·대시보드를 다시 만들고 커밋·push 한다.
   `--details` 캐시 덕에 중간에 끊겨도 다시 돌리면 이어서 한다.
4. 결과 보고: 조회 건수 → 진행 중 → 반영 건수, 관련도 상위 공고 몇 건. 사이트 https://jwchoi061217-web.github.io/-/gov/

- 연계기관 공고(국방전자조달·한전·LH 등, 공고번호가 R 로 시작하지 않음)는 상세가 없어 목록 정보로만 들어간다.
- 검색어를 바꾸려면 `config/gov_sources.json` → `sources.g2b.search_terms` 와 스크립트의 `TERMS` 를 같이 바꾼다.
- 키(`DATA_GO_KR_KEY`)가 `.env` 에 들어오면 이 수동 절차는 필요 없다 — 월요일 자동 수집이 API 로 가져온다.

## 그 밖에 자주 맡기는 일

- 설정만 바꿨을 때 지난 공고에 바로 반영: `python -m src.retag` 후 docs/ 커밋·push
- 공고만 다시 수집해 미리보기: `python -m src.main --only gov --no-state --out C:\temp\preview`
- 키 확인: `python tools/check_keys.py`
