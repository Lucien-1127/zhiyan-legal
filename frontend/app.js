/* ══════════════════════════════════════════════════
   智研 AI 法律研究助手
   前端邏輯 — 聊天 UI 互動
   ══════════════════════════════════════════════════ */

// ─── 狀態 ──────────────────────────────────────────
const state = {
  status: 'checking',
  messages: [],
  sending: false,
};

// ─── DOM 參考 ──────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const chatArea = $('#chatArea');
const messages = $('#messages');
const welcome = $('#welcome');
const input = $('#messageInput');
const sendBtn = $('#sendBtn');
const statusText = $('#statusText');
const loadingOverlay = $('#loadingOverlay');

// ─── 初始化 ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  checkStatus();
  setupMobileMenu();
  setupAutoSend();
});

// ─── 系統狀態 ──────────────────────────────────────
async function checkStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    state.status = 'connected';
    statusText.textContent = '已連線';
  } catch (e) {
    state.status = 'error';
    statusText.textContent = '連線失敗';
    document.querySelector('.status-dot').style.background = '#ef4444';
  }
}

// ─── 發送訊息 ──────────────────────────────────────
async function sendMessage() {
  const text = input.value.trim();
  if (!text || state.sending) return;

  // 清除歡迎畫面
  welcome.style.display = 'none';

  // 顯示使用者訊息
  addMessage(text, 'user');

  // 清空輸入
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;

  // 顯示載入
  state.sending = true;
  loadingOverlay.style.display = 'flex';

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        temperature: 0.3,
        max_tokens: 4096,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '伺服器錯誤');
    }

    const data = await res.json();
    addMessage(data.content, 'ai', data);
  } catch (e) {
    addMessage(`❌ 查詢失敗：${e.message}`, 'ai', null, true);
  } finally {
    state.sending = false;
    loadingOverlay.style.display = 'none';
  }
}

// ─── 新增訊息 ──────────────────────────────────────
function addMessage(text, role, meta = null, isError = false) {
  const div = document.createElement('div');
  div.className = `message ${role}`;

  // 大頭貼
  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = role === 'user' ? '👤' : '⚖️';

  // 氣泡
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';

  // 轉換換行為 <p> 段落
  const paragraphs = text.split('\n').filter(Boolean);
  bubble.innerHTML = paragraphs.map(p => `<p>${escapeHtml(p)}</p>`).join('');

  if (isError) {
    bubble.style.borderColor = '#fca5a5';
    bubble.style.background = '#fef2f2';
  }

  appendCitations(bubble, meta?.citations || []);

  // 只顯示對使用者有意義的狀態，不顯示模型名或 token 數。
  if (meta && meta.mode) {
    const metaDiv = document.createElement('div');
    metaDiv.className = 'message-meta';
    metaDiv.innerHTML = `
      <span class="mode-tag">${escapeHtml(meta.mode_label || '法律研究')}</span>
      <span>${decisionLabel(meta.decision)}</span>
    `;
    bubble.appendChild(metaDiv);
  }

  div.appendChild(avatar);
  div.appendChild(bubble);
  messages.appendChild(div);

  // 滾到底
  scrollToBottom();
}

function appendCitations(bubble, citations) {
  if (!Array.isArray(citations) || citations.length === 0) return;

  const section = document.createElement('section');
  section.className = 'citation-list';

  const heading = document.createElement('h3');
  heading.textContent = '可核對的來源';
  section.appendChild(heading);

  citations.forEach((citation, index) => {
    const item = document.createElement('article');
    item.className = 'citation-item';

    const title = document.createElement('strong');
    title.textContent = `${index + 1}. ${citation.title || citation.locator || '來源'}`;
    item.appendChild(title);

    if (citation.exact_quote) {
      const quote = document.createElement('blockquote');
      quote.textContent = citation.exact_quote;
      item.appendChild(quote);
    }

    if (citation.locator) {
      const locator = document.createElement('div');
      locator.className = 'citation-locator';
      locator.textContent = citation.locator;
      item.appendChild(locator);
    }

    section.appendChild(item);
  });

  bubble.appendChild(section);
}

function decisionLabel(decision) {
  const labels = {
    DELIVER: '已完成來源與風險檢查',
    ASK: '需要補充資料',
    HUMAN_REVIEW: '建議人工確認',
    SAFE: '已停止高風險回答',
    STOP: '資料不足，未繼續推測',
  };
  return labels[decision] || '請核對重要資訊';
}

// ─── 建議問題 ──────────────────────────────────────
function askSuggest(btn) {
  input.value = btn.textContent;
  autoResize(input);
  sendMessage();
}

// ─── 新對話 ────────────────────────────────────────
function newChat() {
  messages.innerHTML = '';
  welcome.style.display = 'flex';
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;
  scrollToBottom();
}

// ─── 快捷鍵 ────────────────────────────────────────
function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

// ─── 自動調整輸入框 ────────────────────────────────
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

// ─── 啟用/停用送出按鈕 ──────────────────────────────
function setupAutoSend() {
  input.addEventListener('input', () => {
    sendBtn.disabled = !input.value.trim() || state.sending;
  });
}

// ─── 行動版選單 ────────────────────────────────────
function setupMobileMenu() {
  const toggle = $('#menuToggle');
  const sidebar = $('#sidebar');

  if (toggle && sidebar) {
    toggle.addEventListener('click', () => {
      sidebar.classList.toggle('open');
    });

    // 點主內容關閉選單
    document.addEventListener('click', (e) => {
      if (window.innerWidth <= 768) {
        if (!sidebar.contains(e.target) && !toggle.contains(e.target)) {
          sidebar.classList.remove('open');
        }
      }
    });
  }
}

// ─── 滾動到底 ──────────────────────────────────────
function scrollToBottom() {
  requestAnimationFrame(() => {
    chatArea.scrollTop = chatArea.scrollHeight;
  });
}

// ─── HTML 跳脫 ─────────────────────────────────────
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
