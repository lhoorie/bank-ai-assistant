'use strict';
const form = document.querySelector('#ask-form');
const input = document.querySelector('#question');
const messages = document.querySelector('#messages');
const send = document.querySelector('#send');
const clear = document.querySelector('#clear');
const status = document.querySelector('#status');
let busy = false;

function addMessage(kind, text) {
  document.querySelector('#welcome')?.remove();
  const item = document.createElement('article');
  item.className = `message ${kind}`;
  const label = document.createElement('div');
  label.className = 'message-label';
  label.textContent = kind === 'user' ? 'شما' : 'دستیار آدان';
  const content = document.createElement('div');
  content.className = 'content';
  content.textContent = text;
  item.append(label, content);
  messages.append(item);
  // Keep history in memory only, bounded to 20 exchanges.
  while (messages.children.length > 40) messages.firstElementChild.remove();
  item.scrollIntoView({block: 'end'});
  return item;
}
function addDetails(item, title, value) {
  if (!value?.length) return;
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = title;
  const pre = document.createElement('pre');
  pre.textContent = JSON.stringify(value, null, 2);
  details.append(summary, pre);
  item.append(details);
}
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (busy || !question) return;
  busy = true;
  send.disabled = true;
  clear.disabled = true;
  input.readOnly = true;
  status.textContent = 'در حال بررسی؛ دریافت پاسخ ممکن است کمی طول بکشد…';
  addMessage('user', question);
  input.value = '';
  const pending = addMessage('pending', 'در حال دریافت اطلاعات و آماده‌سازی پاسخ…');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 300000);
  try {
    const response = await fetch('/ask', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question}),
      signal: controller.signal
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(typeof data.error === 'string' ? data.error : `درخواست ناموفق بود (HTTP ${response.status}).`);
    }
    if (typeof data.answer !== 'string') throw new Error('پاسخ دریافتی معتبر نیست.');
    pending.className = 'message assistant';
    renderAnswer(pending.querySelector('.content'), data.answer);
    const timingTitle = data.timings ? `زمان مراحل · کل پاسخ ${(data.timings.total_ms / 1000).toFixed(1)} ثانیه` : 'زمان مراحل';
    addDetails(pending, timingTitle, data.timings?.events);
    addDetails(pending, 'مسیر تصمیم‌گیری روتر', data.router_trace);
    addDetails(pending, 'ابزارها، منابع و جزئیات اجرا', data.trace);
    if (data.request_id) {
      const id = document.createElement('div');
      id.className = 'request-id';
      id.textContent = `شناسه درخواست: ${data.request_id}`;
      pending.append(id);
    }
  } catch (error) {
    pending.className = 'message error';
    pending.querySelector('.content').textContent = error.name === 'AbortError'
      ? 'زمان انتظار تمام شد. ممکن است پردازش سمت سرور هنوز ادامه داشته باشد؛ کمی بعد دوباره امتحان کنید.'
      : (error instanceof TypeError ? 'ارتباط با سرور برقرار نشد. اتصال را بررسی کنید.' : error.message);
    input.value = question;
  } finally {
    clearTimeout(timer);
    busy = false;
    send.disabled = false;
    clear.disabled = false;
    input.readOnly = false;
    status.textContent = 'هر سؤال مستقل است؛ نام مشتری و موضوع را کامل بنویسید.';
    input.focus();
  }
});
input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});
document.querySelectorAll('[data-question]').forEach(button => {
  button.addEventListener('click', () => {
    input.value = button.dataset.question;
    input.focus();
  });
});
clear.addEventListener('click', () => {
  if (busy) return;
  messages.replaceChildren();
  input.value = '';
  input.focus();
  status.textContent = 'نمایش گفتگو پاک شد. سؤال تازه‌ای بنویسید.';
});
