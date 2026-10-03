// 대시보드(JS) 단위 테스트 — gov_dashboard.py 의 <script> 를 그대로 떼어 Node vm 에서 돌린다. 네트워크·브라우저 없음.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../src/gov_dashboard.py'), 'utf8');
const script = source.slice(source.lastIndexOf('<script>') + 8).split('</script>')[0].replace(/boot\(\);\s*$/, '');

// 발행 때 Python 이 채우는 판별 규칙의 축약본 (config/gov_sources.json 과 같은 모양)
const RULES = {
  fields: [{name:'AX·AI', keywords:['AI','인공지능','DX','디지털전환']}, {name:'장애인·고용', keywords:['장애인','일자리','고용']},
           {name:'원격훈련', keywords:['훈련','교육']}],
  roles: [{name:'공급기업', keywords:['공급기업 모집','공급기업 등록']}, {name:'운영기관', keywords:['운영기관 모집','위탁운영']},
          {name:'수요기업', keywords:['수요기업 모집','지원 대상 기업']}, {name:'참여기업', keywords:['참여기업 모집','참여기업']}],
  weights: {'교육':3, '훈련':3, '장애인':2, 'AI':1, 'DX':1, '고용':1, '일자리':1, '공급기업':3, '운영기관':3},
  min_score: 2, size_phrases: ['중소기업','소상공인','대기업 제외'],
  qualifications: [{name:'원격훈련기관 지정', phrases:['원격훈련기관']}, {name:'벤처기업', phrases:['벤처기업 확인']}],
  consortium_rules: [{status:'필수', keys:['컨소시엄필수','단독신청불가']}, {status:'불가', keys:['컨소시엄불가']}, {status:'가능', keys:['컨소시엄가능','단독또는컨소시엄']}],
  consortium_words: ['컨소시엄','공동수행'], institution_re: '(한국)?(장애인고용공단|산업인력공단)|고용노동부',
};

function run(expression, storage = '{}', {storageThrows = false, settings = 'null', showAll = true} = {}) {
  const nodes = new Map();
  const node = selector => {
    if(!nodes.has(selector)) nodes.set(selector, {
      value: selector === '#sort' ? 'end' : '', checked: false, hidden: false, innerHTML: '', textContent: '',
      classList: {toggle() {}, add() {}, remove() {}}, setAttribute() {}, focus() {}, scrollIntoView() {}, querySelector() { return null; },
    });
    return nodes.get(selector);
  };
  const context = vm.createContext({
    document: {querySelector: node, querySelectorAll: () => [], addEventListener() {}, getElementById: () => null},
    localStorage: {getItem: k => k === 'govdash.settings.v1' ? settings : storage,
                   setItem() { if(storageThrows) throw new Error('Storage unavailable'); }},
    setTimeout, clearTimeout, console,
  });
  const prelude = 'RULES = Object.assign({}, DEFAULT_RULES, ' + JSON.stringify(RULES) + '); INST_RE = null; showAll = ' + showAll + ';\n';
  return vm.runInContext(script + '\n' + prelude + expression, context);
}
const ITEMS = (extra = '') => "DATA.items=[" +
  "{k:'a',title:'2026년 중소기업 AI 교육 바우처 공급기업 모집',org:'중소벤처기업부',summary:'공급기업 등록 접수. 단독 또는 컨소시엄 신청 가능',end:'2099-12-31',seen:'2026-10-05'}," +
  "{k:'b',title:'[경남] 함양군 고용 장려금 참여기업 모집',org:'경상남도 · 기초자치단체',summary:'경남 소재 기업 대상',end:'2099-11-30',seen:'2026-09-28'}," +
  "{k:'c',title:'지난 교육 위탁운영기관 모집',org:'고용노동부',summary:'',end:'2000-01-01',seen:'2026-09-21'}," +
  "{k:'d',title:'2026년 상반기 시스템 점검 안내',org:'한국산업인력공단',summary:'',end:null,seen:'2026-09-28'}" + extra + "]; DATA.issue_key='2026-10-05'; annVer++;";

test('missing deadline asks the reader to verify the schedule', () => {
  assert.equal(run("dday(null).label"), '일정 확인');
  assert.equal(run("period({})"), '원문에서 확인');
});
test('future application opening is labelled as upcoming', () => {
  assert.equal(run("dday('2099-12-31', '2099-12-01').label"), '접수 예정');
});
test('saved expired notices remain in the interest view', () => {
  assert.equal(run("DATA.items=[{k:'saved',end:'2000-01-01',title:'공고'}]; mine.star.saved=true; quick='star'; visible().length"), 1);
});
test('malformed saved data does not break the list', () => {
  assert.equal(run("DATA.items=[{k:'a',end:'2099-12-31',title:'공고'}]; quick='star'; visible().length", '{"star":null,"memo":42,"roles":"x"}'), 0);
});
test('keyword abbreviations and role names can be searched directly', () => {
  assert.equal(run("DATA.items=[{k:'a',title:'제조 전환 지원',kw:['DX'],end:'2099-12-31'}]; $('#q').value='DX'; visible().length"), 1);
  assert.equal(run(ITEMS() + "$('#q').value='공급기업'; visible().map(i=>i.k).join()"), 'a');
});

function savedNotices(count) {
  return `DATA.items = Array.from({length:${count}}, (_,i) => ({k:'item'+i,title:'Item '+i,end:'2099-12-31'}));
    DATA.items.forEach(it => mine.star[it.k] = true);
    quick = 'star'; calMonth = new Date(); page = 2; render(true);`;
}
test('removing a saved notice preserves the current results page', () => {
  const result = JSON.parse(run(savedNotices(45) + `
    toggleStar(cid('item25'));
    JSON.stringify({page, count:visible().length, pageInfo:$('#pageInfo').textContent});`));
  assert.deepEqual(result, {page:2, count:44, pageInfo:'2 / 3 페이지 · 44건'});
});
test('removing the only saved notice on the last page returns to the remaining page', () => {
  const result = JSON.parse(run(savedNotices(21) + `
    toggleStar(cid('item20'));
    JSON.stringify({page, count:visible().length, paginationHidden:$('#pagination').hidden, nextDisabled:$('#nextPage').disabled});`));
  assert.deepEqual(result, {page:1, count:20, paginationHidden:true, nextDisabled:true});
});
test('storage failures return false without claiming a successful save', () => {
  assert.equal(run('save()', '{}', {storageThrows:true}), false);
});
test('region comes from the title tag, then the organisation, else nationwide', () => {
  assert.equal(run("regionsOf({title:'[경남] 함양군 지원사업', org:'경상남도 · 기초자치단체'}).join()"), '경남');
  assert.equal(run("regionsOf({title:'2026년 지원사업', org:'경상북도 · 경상북도경제진흥원'}).join()"), '경북');
  assert.equal(run("regionsOf({title:'x', region:'전남·광주'}).join()"), '전남,광주');   // 수집기가 적어 둔 값이 우선
  assert.equal(run("regionsOf({title:'2026년 지원사업', org:'산업통상부 · 삼성서울병원'}).join()"), '전국');
});
test('closed notices leave the open view and appear in the closed view', () => {
  assert.equal(run(ITEMS() + "quick='open'; visible().map(i=>i.k).join()"), 'a,b,d');
  assert.equal(run(ITEMS() + "quick='closed'; visible().map(i=>i.k).join()"), 'c');
});
test('a region filter narrows the list', () => {
  assert.equal(run(ITEMS() + "rgFilter.add('경남'); visible().map(i=>i.k).join()"), 'b');
});

// ── 2026-10-02 개편: 역할 태그 · 분야 · 관련도 · 판정 · URL · 설정 ──
test('roles are tagged from the configured phrases, several per notice, none → 역할 미확인', () => {
  assert.equal(run(ITEMS() + "annotate(DATA.items[0])._roles.join()"), '공급기업');
  assert.equal(run(ITEMS() + "annotate(DATA.items[1])._roles.join()"), '참여기업');
  assert.equal(run(ITEMS() + "annotate(DATA.items[2])._roles.join()"), '운영기관');
  assert.equal(run(ITEMS() + "annotate(DATA.items[3])._roles.length"), 0);
  assert.equal(run("annotate({k:'x',title:'운영기관 모집 및 공급기업 등록 안내',end:'2099-12-31'})._roles.join()"), '공급기업,운영기관');
});
test('role filter is OR across roles and counts the untagged bucket', () => {
  assert.equal(run(ITEMS() + "roleFilter.add('공급기업'); roleFilter.add('참여기업'); visible().map(i=>i.k).join()"), 'a,b');
  assert.equal(run(ITEMS() + "roleFilter.add('역할 미확인'); visible().map(i=>i.k).join()"), 'd');
});
test('manual role override wins over auto tagging and can be reset', () => {
  assert.equal(run(ITEMS() + "mine.roles[DATA.items[3].k]=['수요기업']; annVer++; annotate(DATA.items[3])._roles.join() + '|' + annotate(DATA.items[3])._manual"), '수요기업|true');
  assert.equal(run(ITEMS() + "render(); toggleRole(cid('d'),'수요기업'); annotate(DATA.items[3])._roles.join()"), '수요기업');
  assert.equal(run(ITEMS() + "render(); toggleRole(cid('d'),'수요기업'); resetRole(cid('d')); annotate(DATA.items[3])._roles.length"), 0);
});
test('fields come from the rules and a browser-side field edit re-tags existing notices', () => {
  assert.equal(run(ITEMS() + "annotate(DATA.items[0])._fields.join()"), 'AX·AI,원격훈련');
  assert.equal(run(ITEMS() + "SET.fields=[{name:'바우처',keywords:['바우처']}]; annVer++; annotate(DATA.items[0])._fields.join()"), '바우처');
  assert.deepEqual(JSON.parse(run("JSON.stringify(textToFields('원격훈련 | 훈련, 교육\\n\\n평생교육|평생학습'))")),
    [{name:'원격훈련', keywords:['훈련','교육']}, {name:'평생교육', keywords:['평생학습']}]);
});
test('low relevance is hidden by default but counted, and 모두 보기 reveals it', () => {
  // b: '고용' 한 단어(가중치 1 → 관련도 10) · d: 점검 안내(관련도 0) — 둘 다 기준(20) 미만. 역할 태그는 가점이 아니다(FR-KEY-03)
  assert.equal(run(ITEMS() + "quick='open'; visible().map(i=>i.k).join()", '{}', {showAll:false}), 'a');
  assert.equal(run(ITEMS() + "quick='open'; render(); $('#lowNote').innerHTML.includes('2건')", '{}', {showAll:false}), true);
  assert.equal(run(ITEMS() + "SET.relevance_min=0; quick='open'; visible().length", '{}', {showAll:false}), 3);
  assert.equal(run(ITEMS() + "SET.exclude=['함양군']; quick='open'; visible().map(i=>i.k).join()", '{}', {showAll:false}), 'a');
});
test('region verdict needs the company location and respects 전국·비수도권', () => {
  assert.equal(run(ITEMS() + "annotate(DATA.items[1])._judge.s"), 'unset');
  assert.equal(run(ITEMS() + "SET.company.regions=['서울']; annVer++; annotate(DATA.items[1])._judge.s"), 'no');
  assert.equal(run(ITEMS() + "SET.company.regions=['경남','서울']; annVer++; annotate(DATA.items[1])._judge.s"), 'ok');
  assert.equal(run(ITEMS() + "annotate(DATA.items[0])._judge.label"), '참여 가능');
  assert.equal(run("SET.company.regions=['서울']; annotate({k:'x',title:'지역 혁신 지원',summary:'비수도권 소재 기업만 신청 가능',end:'2099-12-31'})._judge.s"), 'no');
  assert.equal(run("SET.company.regions=['서울']; annotate({k:'y',title:'[부산] 지원사업',summary:'부산 지역 기업 가점',end:'2099-12-31'})._judge.s"), 'pref');
  assert.equal(run(ITEMS() + "SET.company.regions=['서울']; annVer++; fitOnly=true; quick='open'; visible().map(i=>i.k).join()"), 'a,d');
});
test('consortium, company size and qualification are read from the text, never guessed', () => {
  assert.equal(run(ITEMS() + "annotate(DATA.items[0])._cons.status"), '가능');
  assert.equal(run("annotate({k:'x',title:'공동 사업',summary:'단독 신청 불가, 컨소시엄 필수',end:'2099-12-31'})._cons.status"), '필수');
  assert.equal(run("annotate({k:'x',title:'공고',summary:'내용 없음',end:'2099-12-31'})._cons.status"), '미기재');
  assert.equal(run(ITEMS() + "annotate(DATA.items[0])._size"), '중소기업');
  assert.equal(run("SET.company.size='대기업'; judgeSize('중소기업').label"), '미충족');
  assert.equal(run("SET.company.size='소기업'; judgeSize('중소기업').label"), '충족');
  assert.equal(run("annotate({k:'x',title:'훈련 공고',summary:'원격훈련기관으로 지정된 기관만',end:'2099-12-31'})._quals.join()"), '원격훈련기관 지정');
  assert.equal(run(ITEMS() + "noCons=true; quick='open'; visible().length"), 3);
});
test('filter state round-trips through the URL query (FR-TAG-11)', () => {
  const q = run(ITEMS() + "quick='soon'; roleFilter.add('공급기업'); themeFilter.add('AX·AI'); rgFilter.add('경남'); $('#q').value='AI 교육'; showAll=true; fitOnly=true; selDay='2099-12-31'; stateToQuery()");
  assert.equal(q, '?v=soon&role=%EA%B3%B5%EA%B8%89%EA%B8%B0%EC%97%85&f=AX%C2%B7AI&rg=%EA%B2%BD%EB%82%A8&q=AI%20%EA%B5%90%EC%9C%A1&day=2099-12-31&all=1&fit=1');
  const back = JSON.parse(run("queryToState('" + q + "', ''); JSON.stringify({quick, role:[...roleFilter], f:[...themeFilter], rg:[...rgFilter], q:$('#q').value, showAll, fitOnly, selDay})"));
  assert.deepEqual(back, {quick:'soon', role:['공급기업'], f:['AX·AI'], rg:['경남'], q:'AI 교육', showAll:true, fitOnly:true, selDay:'2099-12-31'});
  assert.equal(run("queryToState('', '#closed'); quick"), 'closed');   // 옛 해시 링크도 연다
  assert.equal(run("queryToState('?v=bogus', ''); quick"), 'open');
});
test('csv export carries verdicts and escapes quotes', () => {
  const csv = run(ITEMS() + "csvRows(DATA.items.slice(0,1))");
  const lines = csv.split('\r\n');
  assert.equal(lines[0].split(',')[5], '"지역 판정"');
  assert.ok(lines[1].includes('"공급기업"') && lines[1].includes('"참여 가능"') && lines[1].includes('"가능"'));
  assert.ok(run("csvRows([{k:'q',title:'따옴표 \"테스트\"',end:'2099-12-31'}])").includes('"따옴표 ""테스트"""'));
});
