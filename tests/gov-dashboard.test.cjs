const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../src/gov_dashboard.py'), 'utf8');
const script = source.slice(source.lastIndexOf('<script>') + 8).split('</script>')[0].replace(/boot\(\);\s*$/, '');
function run(expression, storage = '{}', {storageThrows = false} = {}) {
  const nodes = new Map();
  const node = selector => {
    if(!nodes.has(selector)) nodes.set(selector, {
      value: selector === '#sort' ? 'end' : '',
      classList: {toggle() {}}, setAttribute() {}, focus() {}, scrollIntoView() {},
    });
    return nodes.get(selector);
  };
  const context = vm.createContext({
    document: {querySelector: node, querySelectorAll: () => [], addEventListener() {}},
    localStorage: {getItem: () => storage, setItem() { if(storageThrows) throw new Error('Storage unavailable'); }},
    setTimeout, clearTimeout, console,
  });
  return vm.runInContext(script + '\n' + expression, context);
}
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
  assert.equal(run("DATA.items=[{k:'a',end:'2099-12-31',title:'공고'}]; quick='star'; visible().length", '{"star":null,"memo":42}'), 0);
});
test('keyword abbreviations can be searched directly', () => {
  assert.equal(run("DATA.items=[{k:'a',title:'제조 전환 지원',kw:['DX'],end:'2099-12-31'}]; $('#q').value='DX'; visible().length"), 1);
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
