'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const labels = {faithfulness:'وفاداری به شواهد',completeness:'کامل‌بودن',context_relevance:'ارتباط زمینه',answer_relevance:'ارتباط پاسخ',correctness:'صحت پاسخ'};
  const statuses = {pass:'قبول',partial:'ناقص',fail:'رد',api_error:'خطای برنامه',judge_error:'خطای داور'};
  const number = n => typeof n === 'number' && Number.isFinite(n) ? n.toLocaleString('fa-IR',{maximumFractionDigits:3}) : 'نامشخص';
  const percent = n => typeof n === 'number' ? number(n*100)+'٪' : 'نامشخص';
  let report = null, requestId = 0;
  function node(tag, text, cls) { const n=document.createElement(tag); if(text!==undefined)n.textContent=String(text); if(cls)n.className=cls; return n; }
  async function get(url) {
    const response=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(30000)});
    if(!response.ok)throw new Error('دریافت گزارش ناموفق بود.');
    return response.json();
  }
  function raw(title, value) { const d=node('details');d.append(node('summary',title),node('pre',JSON.stringify(value,null,2)));return d; }
  function card(title,value,detail) { const c=node('div',undefined,'eval-card');c.append(node('span',title),node('strong',value),node('small',detail));return c; }
  function render() {
    const s=report.summary || {}, counts=s.counts || {};
    $('report-meta').textContent=`مدل داور: ${report.judge_model || 'نامشخص'} · تاریخ: ${report.created_at ? new Date(report.created_at).toLocaleString('fa-IR') : 'نامشخص'}`;
    $('summary-cards').replaceChildren(
      card('کل سناریوها',number(s.total),'داوری‌شده: '+number(s.judged)),
      card('قبول',number(counts.pass),'ناقص: '+number(counts.partial)+' · رد: '+number(counts.fail)),
      card('خطاها',number((counts.api_error||0)+(counts.judge_error||0)),'برنامه: '+number(counts.api_error)+' · داور: '+number(counts.judge_error)),
      card('نرخ قبولی کل',percent(s.pass_rate_all),'از موارد داوری‌شده: '+percent(s.pass_rate_judged)),
      card('میانگین زمان پاسخ',number(s.mean_api_seconds)+' ثانیه','صدک ۹۵: '+number(s.p95_api_seconds)+' ثانیه'));
    $('metric-cards').replaceChildren();
    for(const [key,label] of Object.entries(labels)) {
      const m=s.metrics?.[key] || {}, c=card(label,number(m.mean),'سنجیده‌شده: '+number(m.scored)+' · بدون امتیاز: '+number(m.unscored));
      if(typeof m.mean==='number'){const p=node('progress');p.max=1;p.value=m.mean;p.setAttribute('aria-label',label);c.append(p);}
      $('metric-cards').append(c);
    }
    renderCases();
  }
  function renderCases() {
    if(!report)return;
    const query=$('search').value.trim().toLocaleLowerCase(), filter=$('filter').value;
    const rows=(report.results||[]).filter(r=>(filter==='all'||r.status===filter)&&(`${r.id} ${r.question}`).toLocaleLowerCase().includes(query));
    $('result-count').textContent=`نمایش ${number(rows.length)} از ${number((report.results||[]).length)} سناریو`;
    $('results').replaceChildren();
    for(const r of rows) {
      const d=node('details',undefined,'eval-case'), title=node('summary',r.question || r.id);
      title.append(node('span',statuses[r.status]||r.status,'eval-badge '+r.status));d.append(title);
      d.append(node('p',`${r.id} · زمان پاسخ: ${number(r.elapsed_seconds)} ثانیه`));
      d.append(node('h3','جواب مرجع'),node('p',r.reference_answer || r.expected || 'ثبت نشده','reference'));
      if(r.reference_answer)d.append(raw('انتظار و رفتار موردنیاز',r.expected));
      d.append(node('h3','پاسخ واقعی'),node('p',r.actual?.answer || r.error || 'پاسخی ثبت نشده'));
      const table=node('table'), head=node('tr');['معیار','امتیاز از ۱','احتمالات سطوح داوری'].forEach(t=>head.append(node('th',t)));table.append(head);
      for(const [key,label] of Object.entries(labels)) {
        const m=r.judgment?.metrics?.[key], tr=node('tr');
        tr.append(node('td',label),node('td',number(m?.score)),node('td',m ? Object.entries(m.probabilities||{}).map(([k,v])=>`${k}: ${percent(v)}`).join(' · ') : 'ثبت نشده'));table.append(tr);
      }
      const wrap=node('div',undefined,'table-scroll');wrap.append(table);d.append(wrap);
      d.append(raw('جزئیات داوری، مدل و مصرف',r.judgment || {}),raw('شواهد و مسیر ابزارها',r.actual?.trace || []),raw('زمان‌بندی مراحل',r.actual?.timings || {}),raw('دادهٔ کامل سناریو',r));
      $('results').append(d);
    }
  }
  async function loadSelected() {
    const id=++requestId;report=null;$('download').disabled=true;
    ['results','metric-cards','summary-cards','report-meta','result-count'].forEach(k=>$(k).replaceChildren());
    if(!$('report').value)return;
    $('eval-status').textContent='در حال دریافت جزئیات…';
    try { const value=await get('/api/evaluations/'+encodeURIComponent($('report').value));if(id!==requestId)return;report=value;render();$('download').disabled=false;$('eval-status').textContent='گزارش بارگذاری شد.'; }
    catch(e){if(id===requestId)$('eval-status').textContent=e.message;}
  }
  async function refresh() {
    $('refresh').disabled=true;
    try { const data=await get('/api/evaluations'),previous=$('report').value;$('report').replaceChildren();
      for(const r of data.reports)$('report').append(node('option',r.name));
      if(data.reports.some(r=>r.name===previous))$('report').value=previous;
      await loadSelected();if(!data.reports.length)$('eval-status').textContent='هنوز گزارشی وجود ندارد. ابتدا پایپ‌لاین ارزیابی را اجرا کنید.';
    } catch(e){$('eval-status').textContent=e.message;}finally{$('refresh').disabled=false;}
  }
  $('report').addEventListener('change',loadSelected);$('refresh').addEventListener('click',refresh);
  $('filter').addEventListener('change',renderCases);$('search').addEventListener('input',renderCases);
  $('download').addEventListener('click',()=>{if(!report)return;const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'})),a=node('a');a.href=url;a.download=$('report').value;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  refresh();
})();
