'use strict';
(() => {
  const escape = text => text.replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  // Tokenize math before Markdown consumes backslashes or underscores.
  const mathExtension = (name, level, pattern, display) => ({
    name, level,
    start(src) { return src.search(display ? /\$\$|\\\[/ : /\$|\\\(/); },
    tokenizer(src) {
      const match = pattern.exec(src);
      if (match) return {type:name, raw:match[0], math:match[1] ?? match[2]};
    },
    renderer(token) {
      return `<span class="math-source" data-display="${display}" data-math="${escape(token.math)}"></span>` + (display ? '\n' : '');
    }
  });
  if (window.marked) marked.use({extensions:[
    mathExtension('displayMath','block', /^(?:\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\])(?:\n|$)/, true),
    mathExtension('inlineDisplayMath','inline', /^(?:\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\])/, true),
    mathExtension('inlineMath','inline', /^(?:\\\(([^\n]+?)\\\)|\$(?!\$)([^\n$]+?)\$(?!\$))/, false)
  ]});
  window.renderAnswer = (element, answer) => {
    if (!window.marked || !window.DOMPurify || !window.katex) {
      element.textContent = answer;
      return;
    }
    try {
      const html = marked.parse(answer, {gfm:true, breaks:true, async:false});
      element.innerHTML = DOMPurify.sanitize(html, {
        ALLOWED_TAGS:['p','br','strong','em','del','blockquote','h1','h2','h3','h4','h5','h6','ul','ol','li','table','thead','tbody','tr','th','td','pre','code','a','hr','span'],
        ALLOWED_ATTR:['href','title','class','start','align','data-display','data-math'],
        ALLOW_DATA_ATTR:false
      });
      element.classList.add('rendered');
      element.querySelectorAll('a').forEach(link => {
        const href = link.getAttribute('href') || '';
        if (!/^(https?:\/\/|mailto:|#)/i.test(href)) link.removeAttribute('href');
        link.rel = 'noopener noreferrer';
        link.target = '_blank';
      });
      element.querySelectorAll('.math-source[data-math]').forEach(node => {
        const source = node.getAttribute('data-math');
        try {
          katex.render(source, node, {
            displayMode:node.getAttribute('data-display') === 'true',
            throwOnError:false, trust:false, strict:'ignore', maxExpand:100, maxSize:20
          });
        } catch (_) { node.textContent = source; }
        node.removeAttribute('data-math');
      });
      element.querySelectorAll('table').forEach(table => {
        const wrap = document.createElement('div');
        wrap.className = 'table-scroll';
        table.replaceWith(wrap);
        wrap.append(table);
      });
    } catch (_) {
      element.classList.remove('rendered');
      element.textContent = answer;
    }
  };
})();
