"""Generate a selectable Persian PDF with shaped text and embedded fonts."""
from pathlib import Path

PAGES = [
('افتتاح حساب و احراز هویت', [
'این سند فقط برای آزمون دستیار بانکی تهیه شده است. تمام قوانین، مبالغ و زمان‌ها ساختگی هستند و مقررات هیچ بانک واقعی محسوب نمی‌شوند. این راهنما مخصوص حساب آموزشی «سپهر آزمایشی» است و شرایط آن را نباید به سایر حساب‌ها تعمیم داد.',
'برای افتتاح حساب سپهر آزمایشی، ارائه مدرک شناسایی معتبر، شماره موبایل تأییدشده و نشانی محل سکونت لازم است. شماره موبایل باید متعلق به متقاضی باشد. حداقل سن افتتاح مستقل این حساب ۱۸ سال است؛ افراد زیر این سن در این طرح پذیرفته نمی‌شوند.',
'حداقل موجودی افتتاح حساب سپهر آزمایشی ۲٬۰۰۰٬۰۰۰ ریال است. این مبلغ کارمزد نیست و به موجودی حساب افزوده می‌شود. این شرط فقط به حساب سپهر آزمایشی مربوط است؛ درباره حداقل موجودی سایر حساب‌ها این سند حکمی ندارد.',
'اگر مدارک کامل باشد، بررسی درخواست حداکثر ۲ روز کاری طول می‌کشد. درخواست ناقص تا زمان تکمیل مدارک بررسی نمی‌شود. اگر ظرف ۱۰ روز تقویمی مدارک تکمیل نشود، درخواست بسته می‌شود و متقاضی باید درخواست تازه‌ای ثبت کند.',
'تغییر شماره موبایل نیازمند احراز هویت دوباره است. کارکنان پشتیبانی نباید رمز ورود، رمز کارت یا رمز یک‌بارمصرف را از مشتری بخواهند. اطلاعات این سند شامل هیچ مشتری یا شماره حساب واقعی نیست.'
]),
('انتقال وجه و سقف تراکنش', [
'قوانین این صفحه فقط برای انتقال‌های آموزشی حساب سپهر آزمایشی است. همه مبالغ به ریال بیان شده‌اند. برای تبدیل ریال به تومان باید مبلغ ریالی بر ۱۰ تقسیم شود.',
'سقف هر انتقال داخلی ۵۰٬۰۰۰٬۰۰۰ ریال و سقف مجموع انتقال داخلی در هر روز تقویمی ۱۵۰٬۰۰۰٬۰۰۰ ریال است. سقف روزانه در ساعت صفر به وقت تهران بازنشانی می‌شود. انتقال ناموفق از سقف روزانه کم نمی‌کند.',
'کارمزد هر انتقال داخلی موفق ۵٬۰۰۰ ریال است و جدا از مبلغ انتقال از موجودی قابل برداشت کسر می‌شود. انتقال داخلی بین دو حساب متعلق به همان مشتری در این طرح بدون کارمزد است. برای انتقال ناموفق کارمزدی دریافت نمی‌شود.',
'سقف هر انتقال بین‌بانکی آزمایشی ۱۰۰٬۰۰۰٬۰۰۰ ریال است. درخواست ثبت‌شده پیش از ساعت ۱۳ روز کاری، همان روز پردازش می‌شود. درخواست ساعت ۱۳ یا بعد از آن و درخواست روز تعطیل، روز کاری بعد پردازش می‌شود. این زمان‌بندی فقط شبیه‌سازی است.',
'درخواست انتقال زمان‌بندی‌شده تا پیش از شروع پردازش قابل لغو است. پس از شروع پردازش، لغو در این طرح امکان ندارد. اگر موجودی برای مبلغ انتقال و کارمزد کافی نباشد، تراکنش رد می‌شود. چت‌بات فقط می‌تواند این قواعد را توضیح دهد و انتقال واقعی انجام نمی‌دهد.'
]),
('کارت مفقودی و صدور جایگزین', [
'این صفحه قواعد کارت آموزشی سپهر آزمایشی را بیان می‌کند. کارت و فرآیندهای توصیف‌شده واقعی نیستند. چت‌بات مجاز به ادعای مسدودکردن کارت یا ثبت عملیات واقعی نیست.',
'در صورت گم‌شدن کارت، مشتری باید از مسیر بخش کارت در برنامه نمایشی یا شعبه آموزشی درخواست مسدودی ثبت کند. برای ثبت درخواست، احراز هویت لازم است. ارسال رمز کارت، رمز یک‌بارمصرف یا تصویر کامل کارت در گفتگو ممنوع است.',
'پس از تأیید درخواست مسدودی، کارت آموزشی بلافاصله غیرفعال می‌شود. کارت مسدودشده به علت مفقودی دوباره فعال نمی‌شود، حتی اگر بعداً پیدا شود. برای ادامه استفاده باید کارت جایگزین درخواست شود.',
'صدور کارت جایگزین حداکثر ۳ روز کاری و هزینه آن ۱۲۰٬۰۰۰ ریال است. تحویل حضوری رایگان است. در صورت انتخاب ارسال، هزینه ثابت ارسال ۸۰٬۰۰۰ ریال جداگانه دریافت می‌شود. بنابراین صدور همراه ارسال مجموعاً ۲۰۰٬۰۰۰ ریال هزینه دارد.',
'برای درخواست جایگزین، مدرک شناسایی و نشانی تأییدشده لازم است. شماره پیگیری آموزشی پس از ثبت درخواست صادر می‌شود. اگر بیش از ۳ روز کاری از تأیید درخواست گذشته باشد، مشتری می‌تواند با همان شماره پیگیری وضعیت را بررسی کند.'
]),
('صورت‌حساب، اعتراض و پرسش‌های خارج از سند', [
'صورت‌حساب حساب سپهر آزمایشی برای ۱۸ ماه گذشته در دسترس است. این بازه مخصوص این محصول آموزشی است. دریافت نسخه الکترونیکی رایگان و هزینه هر درخواست نسخه کاغذی ۳۰٬۰۰۰ ریال است، مستقل از تعداد صفحات همان درخواست.',
'صورت‌حساب شامل تاریخ، مبلغ، نوع و وضعیت تراکنش است. در محاسبه مخارج و درآمد قطعی، فقط تراکنش تکمیل‌شده لحاظ می‌شود؛ تراکنش در انتظار یا ناموفق نباید به عنوان هزینه قطعی شمرده شود.',
'مهلت ثبت اعتراض به تراکنش ۷ روز تقویمی از تاریخ تراکنش است. مشتری باید شناسه تراکنش، تاریخ و شرح مشکل را اعلام کند. ارائه رمز یا رمز یک‌بارمصرف برای اعتراض لازم نیست. رسیدگی اولیه حداکثر ۴ روز کاری پس از دریافت اطلاعات کامل انجام می‌شود.',
'نمونه محاسباتی ساختگی: اگر مخارج تکمیل‌شده شهریور ۸٬۰۰۰٬۰۰۰ ریال و مهر ۱۰٬۰۰۰٬۰۰۰ ریال باشد، افزایش برابر ۲٬۰۰۰٬۰۰۰ ریال و درصد رشد برابر ۲۵ درصد است. این اعداد صرفاً مثال آموزشی هستند و از دیتابیس مشتریان استخراج نشده‌اند.',
'این سند درباره نرخ سود سپرده، نرخ سود وام، جریمه دیرکرد یا قوانین ارزی اطلاعاتی ندارد. در پاسخ به پرسش درباره این موضوعات باید نبود اطلاعات کافی اعلام شود. این سند برای محاسبه مانده حساب شخص خاص نیز داده تراکنش ارائه نمی‌کند.'
])]



def canonical_font_maps(document):
    """Normalize embedded font Unicode mappings, retaining visible glyph geometry."""
    import re
    import unicodedata
    seen = set()
    for page in document:
        for font in page.get_fonts():
            kind, value = document.xref_get_key(font[0], 'ToUnicode')
            if kind != 'xref': continue
            ref = int(value.split()[0])
            if ref in seen: continue
            seen.add(ref)
            cmap = document.xref_stream(ref).decode('ascii')
            mappings = {}
            for block in re.findall(r'beginbfrange(.*?)endbfrange', cmap, re.S):
                for a,b,values in re.findall(r'<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>\s*\[([^]]+)\]',block):
                    for code,value in zip(range(int(a,16),int(b,16)+1),re.findall(r'<([0-9a-fA-F]+)>',values)):
                        mappings[code]=bytes.fromhex(value.zfill((len(value)+3)//4*4)).decode('utf-16-be')
                for a,b,c in re.findall(r'<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>',block):
                    start,end,unicode_start = int(a,16),int(b,16),int(c,16)
                    for code in range(start,end+1):
                        mappings[code] = chr(unicode_start+code-start)
            for block in re.findall(r'beginbfchar(.*?)endbfchar', cmap, re.S):
                for a,b in re.findall(r'<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>',block):
                    mappings[int(a,16)] = bytes.fromhex(b.zfill((len(b)+3)//4*4)).decode('utf-16-be')
            if not mappings: continue
            header=cmap[:cmap.index('endcodespacerange')+len('endcodespacerange')]
            entries=[f'<{code:04x}> <{unicodedata.normalize("NFKC",text).encode("utf-16-be").hex()}>' for code,text in mappings.items()]
            body=''
            for start in range(0,len(entries),100):
                batch=entries[start:start+100]
                body+=f'\n{len(batch)} beginbfchar\n'+'\n'.join(batch)+'\nendbfchar\n'
            document.update_stream(ref,(header+body+'endcmap CMapName currentdict /CMap defineresource pop end end').encode())


def build(output):
    import html
    import pymupdf
    document = pymupdf.open()
    for number,(title,paragraphs) in enumerate(PAGES,1):
        page=document.new_page(width=595.28,height=841.89)
        content='<div dir="rtl"><h1>'+html.escape(title)+'</h1>'
        content+=''.join('<p>'+html.escape(p)+'</p>' for p in paragraphs)
        content+=f'<p class="footer">صفحه {number} از ۴ | راهنمای آزمایشی سپهر</p></div>'
        spare,scale=page.insert_htmlbox(pymupdf.Rect(45,40,550,805),content,
            archive=pymupdf.Archive('/usr/share/fonts/truetype/dejavu'),
            css='@font-face{font-family:Persian;src:url(DejaVuSans.ttf)} * {font-family:Persian} body{font-size:12px;line-height:1.85;color:#193b37} h1{font-size:22px;color:#164f43;margin-bottom:22px} p{margin-bottom:18px} .footer{font-size:10px;color:#68786c}',scale_low=1)
        if spare<0: raise RuntimeError(f'Page {number} overflows')
    canonical_font_maps(document)
    document.set_metadata({'title':'قوانین بانکی فارسی - سپهر آزمایشی'})
    document.save(output,garbage=4,deflate=True)
    document.close()
    with pymupdf.open(output) as check:
        for page,(_,paragraphs) in zip(check,PAGES):
            import unicodedata
            normal=lambda text: ''.join(c for c in unicodedata.normalize('NFKC',text) if c.isalnum())
            for paragraph in paragraphs:
                assert normal(paragraph) in normal(page.get_text())
            assert 'آزمایشی' in page.get_text()
            assert page.get_text('words')
            assert page.search_for('آزمایشی')
            traces=page.get_texttrace()
            assert traces and all(t['type'] != 3 for t in traces), 'Invisible text is forbidden'
            assert not page.get_images(), 'Raster text is forbidden'
    print('Verified: four pages of visible, searchable text with real glyph positions.')

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'data/bank_documents/persian_demo_rules.pdf')
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    build(args.output)
    print(f'{args.output}: {args.output.stat().st_size:,} bytes; {len(PAGES)} pages')
