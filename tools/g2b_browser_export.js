/*
 * 나라장터 입찰공고 목록 내보내기 (브라우저 콘솔용) — DATA_GO_KR_KEY 없이 나라장터를 가져오는 반자동 경로.
 *
 * 쓰는 법 (크롬, 5분)
 *   1. https://www.g2b.go.kr → 입찰 → 입찰공고 → 입찰공고목록 을 연다. 로그인은 필요 없다.
 *   2. F12 → Console 탭에 이 파일 내용을 전부 붙여 넣고 Enter.
 *   3. 화면의 [검색] 버튼을 한 번 누른다 (검색어는 비워 둬도 된다). 그 요청을 본떠서 설정의 검색어마다
 *      최근 1개월 목록을 차례로 조회하고, 끝나면 g2b_export.json 이 내려받기 폴더에 저장된다.
 *   4. 저장소에서  python -m src.g2b_web import %USERPROFILE%\Downloads\g2b_export.json --push
 *
 * 왜 이렇게 하나: 목록 XHR 은 그 브라우저 세션의 쿠키·메뉴 헤더가 있어야만 응답한다(없으면 403). 그래서 목록은 사람이 연
 * 브라우저가 뽑고, 공고별 상세(지역·업종·공동수급·접수기간)는 세션 없이도 열리므로 파이썬이 채운다.
 * 검색어는 config/gov_sources.json → sources.g2b.search_terms 와 같게 맞춰 둔다.
 */
(function () {
  const TERMS = ["교육", "훈련", "연수", "이러닝", "콘텐츠", "안전보건", "안전교육", "HRD", "장애인", "역량강화", "AI", "디지털"];
  const PER_TERM_MAX = 2000;          // 검색어 하나당 최대 건수(최근 1개월 '교육' 이 900건쯤 된다)
  const LIST_PATH = "/BidPbac/selectBidPbacScrollTypeList.do";

  if (window.__g2bExportHooked) { console.log("이미 준비돼 있습니다 — [검색] 버튼을 누르세요."); return; }
  window.__g2bExportHooked = true;

  const un = (s) => String(s == null ? "" : s)
    .replace(/&#40;/g, "(").replace(/&#41;/g, ")").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#39;/g, "'");

  function rowOf(x) {
    const d = un(x.pbancPstgDt);                       // '2026/10/02 20:24<br/>(2026/10/16 12:00)' = 게시(마감)
    const m = d.match(/^(.*?)<br\/?>\s*\((.*?)\)/) || [null, d, ""];
    return {
      no: x.bidPbancUntyNo, ord: x.bidPbancUntyOrd || "000", id: x.bidPbancUntyNoOrd,
      title: un(x.bidPbancNm), org: un(x.oderInstUntyGrpNm), dmst: un(x.dmstNm),
      post: m[1].trim(), close: (m[2] || "").trim(),
      kind: un(x.prcmBsneSeCdNm), kindCd: x.prcmBsneSeCd, stts: un(x.pbancSttsNm).replace(/<\/?br\/?>/g, " "),
      method: un(x.scsbdMthdNm), bgt: x.alotBgtAmt || 0, prsp: x.prspPrce || 0, link: x.linkInstPbancLnkUrl || "",
    };
  }

  async function runAll(url, headers, template) {
    const all = new Map(); const perTerm = {};
    for (const t of TERMS) {
      const body = JSON.parse(JSON.stringify(template));
      const q = body.dlBidPbancLstM;
      q.bidPbancNm = t; q.recordCountPerPage = String(PER_TERM_MAX); q.startIndex = 1; q.endIndex = PER_TERM_MAX;
      const r = await fetch(url, { method: "POST", headers, body: JSON.stringify(body), credentials: "include" });
      const j = await r.json();
      const rows = j.result || [];
      perTerm[t] = rows.length;
      for (const x of rows) {
        const row = rowOf(x);
        const key = row.id || (row.no + "-" + row.ord);
        if (!all.has(key)) { row.terms = [t]; all.set(key, row); } else { all.get(key).terms.push(t); }
      }
      console.log(`  ${t}: ${rows.length}건 (누적 ${all.size}건)`);
      await new Promise((res) => setTimeout(res, 400));
    }
    const today = new Date().toISOString().slice(0, 10).replace(/-/g, "/");
    // 마감 지난 공고와 취소공고는 뺀다 — 가져가 봐야 바로 '마감됨' 이다
    const rows = [...all.values()].filter((x) => (!x.close || x.close.slice(0, 10) >= today) && !/취소/.test(x.stts));
    const doc = { exported: new Date().toISOString(), terms: TERMS, perTerm, total: all.size, rows };
    const blob = new Blob([JSON.stringify(doc)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "g2b_export.json"; document.body.appendChild(a); a.click(); a.remove();
    console.log(`완료: 검색 ${all.size}건 중 진행 중 ${rows.length}건을 g2b_export.json 으로 저장했습니다.`);
    console.log("다음: python -m src.g2b_web import <내려받은 파일> --push");
  }

  // 사용자가 [검색] 을 누를 때 나가는 목록 요청을 본뜬다 — 세션 헤더를 그대로 쓰기 위해서다.
  const origOpen = XMLHttpRequest.prototype.open;
  const origSetHeader = XMLHttpRequest.prototype.setRequestHeader;
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url) { this.__g2bUrl = url; this.__g2bHeaders = {}; return origOpen.apply(this, arguments); };
  XMLHttpRequest.prototype.setRequestHeader = function (k, v) { if (this.__g2bHeaders) this.__g2bHeaders[k] = v; return origSetHeader.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function (body) {
    const xhr = this;
    if (xhr.__g2bUrl && xhr.__g2bUrl.indexOf(LIST_PATH) >= 0 && !window.__g2bExportStarted) {
      xhr.addEventListener("load", function () {
        if (window.__g2bExportStarted || xhr.status !== 200) return;
        window.__g2bExportStarted = true;
        let template; try { template = JSON.parse(body); } catch (e) { console.error("요청 본문을 읽지 못했습니다", e); return; }
        console.log("검색 요청을 확인했습니다. 검색어별로 조회합니다…");
        runAll(xhr.__g2bUrl, xhr.__g2bHeaders, template).catch((e) => console.error("실패:", e));
      });
    }
    return origSend.apply(this, arguments);
  };
  console.log("준비됐습니다. 화면의 [검색] 버튼을 한 번 누르세요.");
})();
