'use strict';
(() => {
  const select = document.querySelector('#source-select');
  const view = document.querySelector('#data-view');
  const status = document.querySelector('#explorer-status');
  const info = document.querySelector('#page-info');
  const previous = document.querySelector('#previous');
  const next = document.querySelector('#next');
  const vectors = document.querySelector('#vectors');
  const dbTab = document.querySelector('#db-tab');
  const chunksTab = document.querySelector('#chunks-tab');
  const refresh = document.querySelector('#refresh');
  let mode = 'database', offset = 0, total = 0, busy = false;
  const limit = 25;
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = String(text);
    if (className) node.className = className;
    return node;
  }
  async function get(path) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 60000);
    try {
      const response = await fetch(path, {signal:controller.signal});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'خواندن اطلاعات ناموفق بود.');
      return data;
    } finally { clearTimeout(timer); }
  }
  function setBusy(value) {
    busy = value;
    [select, vectors, dbTab, chunksTab, refresh].forEach(node => node.disabled = value);
    previous.disabled = value || offset === 0 || total === 0;
    next.disabled = value || offset + limit >= total;
  }
  function renderDatabase(data) {
    const wrap = element('div', undefined, 'table-scroll');
    const table = element('table');
    const head = element('thead');
    const header = element('tr');
    data.columns.forEach(column => header.append(element('th', column)));
    head.append(header);
    const body = element('tbody');
    data.rows.forEach(row => {
      const tr = element('tr');
      row.forEach(value => tr.append(element('td', value === null ? 'NULL' : value)));
      body.append(tr);
    });
    table.append(head, body);wrap.append(table);view.append(wrap);
  }
  function renderChunks(data) {
    data.rows.forEach(row => {
      const card = element('article', undefined, 'chunk-card');
      card.append(element('h3', `${row.source} · صفحه ${row.page} · شناسه ${row.id}`));
      card.append(element('p', row.text, 'chunk-text'));
      if (Array.isArray(row.vector)) {
        const details = element('details');
        details.append(element('summary', `بردار embedding · ${row.vector.length} بُعد`));
        details.append(element('pre', JSON.stringify(row.vector)));
        card.append(details);
      }
      view.append(card);
    });
  }
  async function loadRows() {
    setBusy(true);status.textContent = 'در حال خواندن اطلاعات…';view.replaceChildren();info.textContent = '';
    try {
      const source = select.value;
      if (!source) { total = 0; status.textContent = mode === 'collections' ? 'هنوز چانکی ثبت نشده است. ابتدا یک سؤال دربارهٔ اسناد بپرسید.' : 'جدولی پیدا نشد.'; return; }
      const params = new URLSearchParams({offset,limit});
      if (mode === 'collections') params.set('include_vectors', vectors.checked);
      const data = await get(`/inspect/${mode}/${encodeURIComponent(source)}?${params}`);
      total = data.total;
      if (mode === 'database') renderDatabase(data); else renderChunks(data);
      status.textContent = total ? '' : 'این بخش خالی است.';
      info.textContent = total ? `${offset + 1} تا ${offset + data.rows.length} از ${total}` : '۰ مورد';
    } catch (error) {
      total = 0;
      status.textContent = error.name === 'AbortError' ? 'زمان خواندن اطلاعات تمام شد؛ دوباره تلاش کنید.' : error.message;
    } finally {setBusy(false);}
  }
  async function loadSources() {
    setBusy(true);status.textContent = 'در حال دریافت فهرست…';view.replaceChildren();select.replaceChildren();info.textContent = '';total = 0;
    try {
      const data = await get(`/inspect/${mode}`);
      const sources = mode === 'database' ? data.tables : data.collections;
      sources.forEach(item => {
        const option = element('option', mode === 'database' ? `${item.name} (${item.count})` : item);
        option.value = mode === 'database' ? item.name : item;
        select.append(option);
      });
      await loadRows();
    } catch (error) {status.textContent = error.name === 'AbortError' ? 'زمان اتصال تمام شد.' : error.message;}
    finally {setBusy(false);}
  }
  async function switchMode(value) {
    if (busy) return;
    mode = value;offset = 0;
    dbTab.setAttribute('aria-pressed', String(mode === 'database'));
    chunksTab.setAttribute('aria-pressed', String(mode === 'collections'));
    document.querySelector('#source-label').textContent = mode === 'database' ? 'جدول' : 'Collection';
    document.querySelector('#vector-option').hidden = mode !== 'collections';
    await loadSources();
  }
  dbTab.addEventListener('click', () => switchMode('database'));
  chunksTab.addEventListener('click', () => switchMode('collections'));
  select.addEventListener('change', () => {offset = 0;loadRows();});
  vectors.addEventListener('change', () => loadRows());
  refresh.addEventListener('click', () => {offset = 0;loadSources();});
  previous.addEventListener('click', () => {if (!busy) {offset = Math.max(0, offset-limit);loadRows();}});
  next.addEventListener('click', () => {if (!busy) {offset += limit;loadRows();}});
  loadSources();
})();
