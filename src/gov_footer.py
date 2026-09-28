"""Compact, dashboard-only contact and provenance footer."""

from .theme import LOGO_DARK


CSS = r"""
/* Dashboard footer: one quiet navy surface, with a single yellow action. */
.gov-footer{
  margin-top:32px;padding:24px 28px;border-radius:20px;
  background:#00234A;color:#D3DFED;font-size:13px;line-height:1.5;
  overflow-wrap:anywhere;
}
.gov-footer p{margin:0}
.gov-footer-primary{
  display:grid;grid-template-columns:minmax(0,1fr) auto;
  align-items:center;gap:20px 32px;
}
.gov-footer-brand{min-width:0}
.gov-footer-brand .logo{height:28px;width:auto;max-width:100%;object-fit:contain}
.gov-footer-tagline{margin-top:10px!important;color:#FFF;font-size:14px;font-weight:600}
.gov-footer-contact{min-width:0}
.gov-footer-actions,.gov-footer-details{
  display:flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:0 16px;
}
.gov-footer a{
  display:inline-flex;align-items:center;justify-content:center;min-height:44px;
  max-width:100%;color:inherit;text-underline-offset:4px;
}
.gov-footer a:hover{text-decoration:underline}
.gov-footer a:focus-visible{outline:3px solid #FDB515;outline-offset:4px;border-radius:6px}
.gov-footer .gov-footer-cta{
  padding:0 18px;border-radius:8px;background:#FDB515;color:#00234A;
  font-size:14px;font-weight:800;text-decoration:none;
}
.gov-footer .gov-footer-cta:hover{background:#FFC94F;text-decoration:none}
.gov-footer .gov-footer-cta:focus-visible{outline-color:#FFF}
.gov-footer-website{color:#FFF!important;text-decoration:underline}
.gov-footer-details{font-size:12px}
.gov-footer-notes{
  margin-top:14px;padding-top:14px;border-top:1px solid #365270;
  font-size:12px;line-height:1.6;
}
.gov-footer-notes p+p{margin-top:2px}
.gov-footer-sources{color:#D3DFED}
.gov-footer-sources-label{font-weight:700;color:#FFF;margin-right:6px}
.gov-footer-company{color:#BDCCDD}
.gov-footer-sr-only{
  position:absolute;width:1px;height:1px;padding:0;margin:-1px;
  overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;
}
@media(max-width:767px){
  .gov-footer{padding:24px 20px;border-radius:16px;margin-top:24px}
  .gov-footer-primary{grid-template-columns:minmax(0,1fr);gap:16px}
  .gov-footer-actions,.gov-footer-details{justify-content:flex-start}
  .gov-footer-actions{gap:4px 16px}
  .gov-footer-details{column-gap:14px}
  .gov-footer-notes{margin-top:12px;padding-top:16px;line-height:1.7}
  .gov-footer-notes p+p{margin-top:6px}
}
"""


def footer() -> str:
    """Return the footer; the dashboard fills ``footerSources`` from its data."""
    return f"""<footer class="gov-footer" aria-label="모두의러닝 문의 및 이용 안내">
  <div class="gov-footer-primary">
    <div class="gov-footer-brand">
      {LOGO_DARK}
      <p class="gov-footer-tagline">기업교육이 필요할 때, 모두의러닝</p>
    </div>
    <div class="gov-footer-contact">
      <div class="gov-footer-actions">
        <a class="gov-footer-cta" href="mailto:jwchoi1@modulearning.kr">교육 문의</a>
        <a class="gov-footer-website" href="https://modulearning.kr" target="_blank"
           rel="noopener noreferrer">modulearning.kr<span aria-hidden="true">&nbsp;↗</span><span class="gov-footer-sr-only"> (새 창)</span></a>
      </div>
      <div class="gov-footer-details">
        <a href="tel:1544-9335">대표번호 1544-9335</a>
        <a href="mailto:jwchoi1@modulearning.kr">jwchoi1@modulearning.kr</a>
      </div>
    </div>
  </div>
  <div class="gov-footer-notes">
    <p>관심 공고와 메모는 이 브라우저에만 저장되며, 브라우저 데이터를 삭제하면 사라집니다.</p>
    <p>신청 마감일과 자격 요건은 반드시 공식 공고 원문에서 다시 확인하세요.</p>
    <p class="gov-footer-sources"><span class="gov-footer-sources-label">수집 출처</span><span id="footerSources"></span></p>
    <p class="gov-footer-company">주식회사 모두의교육그룹 · 서울 금천구 가산디지털1로 75-15 가산하우스디와이즈타워 6층 621~625호</p>
  </div>
</footer>"""
