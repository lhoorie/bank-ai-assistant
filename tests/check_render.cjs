// Run with any existing Node runtime; no npm installation required.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const base = path.join(__dirname, '../app/static');
const context = vm.createContext({console, setTimeout, clearTimeout});
context.window = context;
for (const file of ['vendor/marked.js', 'vendor/katex.js', 'render.js']) {
  vm.runInContext(fs.readFileSync(path.join(base, file), 'utf8'), context, {filename:file});
}
const markdown = String.raw`## پاسخ آزمایشی

**مانده:** ۱۲٬۲۰۰٬۰۰۰ ریال

| مورد | مقدار |
|---|---|
| نسبت | ۱۲٫۲ |

- نتیجهٔ اول
- نتیجهٔ دوم

$$\frac{12{,}200{,}000}{1{,}000{,}000} = 12.2$$

فرمول درون متن: \(x_i + 2\) و $a_b$.

\[a \times b\]
`;
const html = context.marked.parse(markdown);
assert.match(html, /<h2>پاسخ آزمایشی<\/h2>/);
assert.match(html, /<strong>مانده:<\/strong>/);
assert.match(html, /<table>/);
assert.match(html, /<ul>/);
assert.equal((html.match(/data-math=/g) || []).length, 4);
assert.match(html, /data-math="\\frac/);
assert.match(html, /data-math="x_i \+ 2"/);
assert.match(html, /data-display="true"/);
const code = context.marked.parse('`$x$`\n\n```tex\n$$y$$\n```');
assert.doesNotMatch(code, /data-math=/);
assert.match(code, /<code>\$x\$<\/code>/);
const unsafe = context.marked.parse(String.raw`\(x < y & z\)`);
assert.match(unsafe, /x &lt; y &amp; z/);
const math = context.katex.renderToString(String.raw`\frac{12200000}{1000000}=12.2`, {trust:false});
assert.match(math, /katex-mathml/);
assert.match(math, /katex-html/);
const attack = context.katex.renderToString(String.raw`\href{javascript:alert(1)}{x}`, {trust:false,throwOnError:false});
assert.doesNotMatch(attack, /href="javascript:/);
console.log('Markdown tables/lists/bold, four math delimiters, TeX preservation, code exclusion and KaTeX trust checks passed.');
