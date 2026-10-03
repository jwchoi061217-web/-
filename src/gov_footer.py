"""대시보드(/gov/) 전용 푸터 — 네이비 한 단.

주차 페이지의 4단 푸터(theme.footer)는 정보가 너무 많아 공고 목록 아래에는 어울리지 않는다.
여기서는 세 줄만 둔다.
  1) 로고 + 슬로건  |  교육 문의(옐로우 버튼) · 웹 · 대표번호 · 이메일
  2) 이용 안내 한 줄 (브라우저 저장 · 원문 확인 · 수집 출처)
  3) 법인 · 주소
연락처는 2026-09-28 사용자 결정대로 대표번호 + jwchoi1@modulearning.kr 만 쓴다(교육 상담 번호 제외).
"""

from .theme import LOGO_DARK


CSS = r"""
.gov-footer{
  margin-top:32px;padding:26px 28px 22px;border-radius:20px;
  background:linear-gradient(150deg,#001C3B 0%,#00234A 60%,#003362 100%);
  color:#D3DFED;font-size:13px;line-height:1.5;overflow-wrap:anywhere;
}
.gov-footer p{margin:0}
.gov-footer-top{display:flex;align-items:center;justify-content:space-between;gap:16px 32px;flex-wrap:wrap}
.gov-footer-brand{display:flex;align-items:center;gap:16px;min-width:0;flex-wrap:wrap}
.gov-footer-brand .logo{height:30px;width:auto;object-fit:contain}
.gov-footer-tagline{color:#FFF;font-size:14px;font-weight:700;letter-spacing:-.2px}
.gov-footer-links{display:flex;align-items:center;flex-wrap:wrap;gap:6px 18px}
.gov-footer a{display:inline-flex;align-items:center;min-height:36px;color:inherit;
  text-underline-offset:4px;white-space:nowrap}
.gov-footer a:hover{text-decoration:underline}
.gov-footer a:focus-visible{outline:3px solid #FDB515;outline-offset:4px;border-radius:6px}
.gov-footer .gov-footer-cta{
  min-height:40px;padding:0 18px;border-radius:8px;background:#FDB515;color:#00234A;
  font-size:14px;font-weight:800;text-decoration:none;
}
.gov-footer .gov-footer-cta:hover{background:#FFC94F;text-decoration:none}
.gov-footer .gov-footer-cta:focus-visible{outline-color:#FFF}
.gov-footer-links .web{color:#FFF;font-weight:700}
.gov-footer-note{margin-top:18px!important;padding-top:14px;border-top:1px solid rgba(255,255,255,.14);
  font-size:12px;line-height:1.7;color:#BDCCDD}
.gov-footer-note .sep{margin:0 8px;color:rgba(255,255,255,.3)}
.gov-footer-company{margin-top:4px!important;font-size:12px;color:#8FA3BA}
.gov-footer-sr-only{
  position:absolute;width:1px;height:1px;padding:0;margin:-1px;
  overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;
}
@media(max-width:767px){
  .gov-footer{padding:22px 18px 18px;border-radius:16px;margin-top:24px}
  .gov-footer-top{flex-direction:column;align-items:flex-start;gap:14px}
  .gov-footer-brand{gap:10px}
  .gov-footer-brand .logo{height:26px}
  .gov-footer-tagline{font-size:13px}
  .gov-footer-links{gap:4px 14px}
  .gov-footer-note .sep{display:block;height:0;margin:0;overflow:hidden}
}
"""


def footer() -> str:
    """대시보드 푸터. '수집 출처'(#footerSources)는 대시보드가 데이터에서 채운다."""
    return f"""<footer class="gov-footer" aria-label="모두의러닝 문의 및 이용 안내">
  <div class="gov-footer-top">
    <div class="gov-footer-brand">
      {LOGO_DARK}
      <p class="gov-footer-tagline">기업의 성장을 위한 가장 확실한 HRD 파트너</p>
    </div>
    <div class="gov-footer-links">
      <a class="gov-footer-cta" href="mailto:jwchoi1@modulearning.kr">교육 문의</a>
      <a class="web" href="https://modulearning.kr" target="_blank"
         rel="noopener noreferrer">modulearning.kr<span aria-hidden="true">&nbsp;↗</span><span class="gov-footer-sr-only"> (새 창)</span></a>
      <a href="tel:1544-9335">대표번호 1544-9335</a>
      <a href="mailto:jwchoi1@modulearning.kr">jwchoi1@modulearning.kr</a>
    </div>
  </div>
  <p class="gov-footer-note">관심 표시와 메모는 이 브라우저에만 저장됩니다<span class="sep">·</span>마감일과 자격 요건은 공고 원문이 기준입니다<span class="sep">·</span>수집 출처 <span id="footerSources"></span></p>
  <p class="gov-footer-company">주식회사 모두의교육그룹 · 서울 금천구 가산디지털1로 75-15 가산하우스디와이즈타워 6층 621~625호</p>
</footer>"""
