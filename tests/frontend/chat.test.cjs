const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const script = readFileSync(path.join(__dirname, '../../frontend/app.js'), 'utf8');

// Only the DOM surface used by app.js is simulated; execute its real send and
// rendering functions, without replacing addMessage or appendCitations.
class Element {
  constructor(tagName = 'div') {
    this.tagName = tagName;
    this.children = [];
    this.style = {};
    this.value = '';
    this.className = '';
    this._html = '';
    this._text = '';
  }
  appendChild(child) { this.children.push(child); }
  set textContent(value) {
    this._text = String(value);
    this._html = this._text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  get textContent() { return this._text; }
  set innerHTML(value) { this._html = value; this.children = []; }
  get innerHTML() { return this._html; }
}

function loadApp(fetch) {
  const elements = Object.fromEntries(
    ['chatArea', 'messages', 'welcome', 'messageInput', 'sendBtn', 'statusText', 'loadingOverlay']
      .map(id => [id, new Element()]),
  );
  elements.messageInput.value = '法律問題';
  const context = vm.createContext({
    document: {
      querySelector: selector => elements[selector.slice(1)],
      createElement: tag => new Element(tag),
      addEventListener() {},
    },
    fetch,
    requestAnimationFrame: callback => callback(),
  });
  vm.runInContext(script, context);
  return { context, elements };
}

function reply(status, payload) {
  let reads = 0;
  return {
    status,
    ok: status >= 200 && status < 300,
    async json() {
      assert.equal(++reads, 1, 'response body must only be read once');
      return payload;
    },
  };
}

function aiBubble(elements) {
  assert.equal(elements.messages.children.length, 2);
  const message = elements.messages.children[1];
  assert.equal(message.className, 'message ai');
  return message.children[1];
}

const decisions = [
  ['DELIVER', 200, '已完成來源與風險檢查'],
  ['ASK', 400, '需要補充資料'],
  ['SAFE', 403, '已停止高風險回答'],
  ['HUMAN_REVIEW', 403, '建議人工確認'],
  ['STOP', 422, '資料不足，未繼續推測'],
];

for (const [decision, status, label] of decisions) {
  test(`${decision}/${status} renders guidance, decision and citations`, async () => {
    const citation = {
      citation_id: 'citation-1', claim_id: 'claim-1', source_id: 'source-1',
      locator: '測試來源第 1 段', exact_quote: '<img src=x onerror=alert(1)> & 原文',
      evidence_level: 'VERIFIED', verified_at: '2026-10-06T00:00:00Z',
    };
    const { context, elements } = loadApp(async (url, options) => {
      assert.equal(url, '/api/chat');
      assert.equal(options.method, 'POST');
      assert.equal(JSON.parse(options.body).message, '法律問題');
      return reply(status, {
        decision, content: '請補充或核對資料\n保留完整說明。',
        mode: 'legal', mode_label: '法律分析模式', citations: [citation],
      });
    });

    await context.sendMessage();

    const bubble = aiBubble(elements);
    assert.equal(bubble.innerHTML, '<p>請補充或核對資料</p><p>保留完整說明。</p>');
    assert.equal(bubble.style.background, undefined);
    const section = bubble.children.find(child => child.className === 'citation-list');
    assert.equal(section.children[0].textContent, '可核對的來源');
    const item = section.children[1];
    assert.equal(item.children[0].textContent, `1. ${citation.locator}`);
    assert.equal(item.children[1].textContent, citation.exact_quote);
    assert.match(item.children[1].innerHTML, /^&lt;img/);
    assert.equal(item.children[2].textContent, citation.locator);
    const meta = bubble.children.find(child => child.className === 'message-meta');
    assert.ok(meta.innerHTML.includes(label));
    assert.equal(elements.loadingOverlay.style.display, 'none');
    assert.equal(vm.runInContext('state.sending', context), false);
  });
}

test('a reply without citations does not create an empty source section', async () => {
  const { context, elements } = loadApp(async () => reply(200, {
    content: '一般回答', decision: 'DELIVER', mode: 'general', citations: [],
  }));
  await context.sendMessage();
  assert.equal(aiBubble(elements).children.some(child => child.className === 'citation-list'), false);
});

const failures = [
  ['ordinary 400', 400, { detail: '輸入格式錯誤' }, '輸入格式錯誤'],
  ['ordinary 403', 403, { detail: '未授權' }, '未授權'],
  ['validation 422', 422, { detail: [{ msg: 'Field required' }] }, '伺服器錯誤'],
  ['rate limit', 429, { error: 'Rate limit exceeded' }, '伺服器錯誤'],
  ['server failure', 500, { detail: '伺服器內部錯誤' }, '伺服器內部錯誤'],
  ['provider STOP', 502, { decision: 'STOP', content: '供應商中斷', mode: 'legal' }, '伺服器錯誤'],
  ['wrong decision/status pair', 403, { decision: 'ASK', content: '缺資料' }, '伺服器錯誤'],
  ['unknown decision', 400, { decision: 'UNKNOWN', content: '不明回應' }, '伺服器錯誤'],
  ['missing content', 400, { decision: 'ASK' }, '伺服器錯誤'],
  ['blank content', 400, { decision: 'ASK', content: '   ' }, '伺服器錯誤'],
  ['null payload', 400, null, '伺服器錯誤'],
  ['invalid success payload', 200, { content: null }, '回應格式錯誤'],
];

for (const [name, status, payload, error] of failures) {
  test(`${name} remains an error, not a controlled answer`, async () => {
    const { context, elements } = loadApp(async () => reply(status, payload));
    await context.sendMessage();
    const bubble = aiBubble(elements);
    assert.equal(bubble.innerHTML, `<p>❌ 查詢失敗：${error}</p>`);
    assert.equal(bubble.style.background, '#fef2f2');
    assert.equal(bubble.children.length, 0);
    assert.equal(elements.loadingOverlay.style.display, 'none');
    assert.equal(vm.runInContext('state.sending', context), false);
  });
}

test('non-JSON server errors are readable and allow the next request', async () => {
  let calls = 0;
  const { context, elements } = loadApp(async () => {
    if (++calls === 1) return { status: 502, ok: false, async json() { throw new SyntaxError('invalid JSON'); } };
    return reply(200, { content: '已恢復', decision: 'DELIVER' });
  });
  await context.sendMessage();
  assert.equal(aiBubble(elements).innerHTML, '<p>❌ 查詢失敗：伺服器錯誤</p>');
  elements.messageInput.value = '再試一次';
  await context.sendMessage();
  assert.equal(calls, 2);
  assert.equal(elements.messages.children[3].children[1].innerHTML, '<p>已恢復</p>');
});

test('network failure clears the loading state', async () => {
  const { context, elements } = loadApp(async () => { throw new Error('網路中斷'); });
  await context.sendMessage();
  assert.equal(aiBubble(elements).innerHTML, '<p>❌ 查詢失敗：網路中斷</p>');
  assert.equal(elements.loadingOverlay.style.display, 'none');
  assert.equal(vm.runInContext('state.sending', context), false);
});
