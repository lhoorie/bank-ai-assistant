"""Bounded native PDF extraction with in-memory Persian/English OCR fallback."""
import os
import threading
import unicodedata
from pathlib import Path
import pymupdf
from app.model import ModelError

PDF_LOCK = threading.Lock()  # MuPDF must not be used concurrently by request threads.
EXTRACTION_VERSION = 'pymupdf-1.26.7-persian-v2'


def normalize(text):
    text = unicodedata.normalize('NFKC', text)
    return text.translate(str.maketrans({'ي':'ی', 'ك':'ک', '\ufeff':None,
                                       '\u200b':None, '\u200e':None, '\u200f':None}))


def needs_ocr(text):
    letters = [c for c in text if c.isalpha()]
    if not letters or text.count('\ufffd') > max(2, len(text) * .02):
        return True
    # Detect a clear visual-order failure, never reverse mixed text or numbers.
    words = set(text.split())
    common = {'برای', 'افتتاح', 'حساب', 'موجودی', 'بانک', 'مشتری', 'قوانین', 'شماره', 'دریافت'}
    return len(words & {w[::-1] for w in common}) >= 3 and len(words & common) < 2


def extract_pages(path):
    path = Path(path)
    if path.stat().st_size > int(os.getenv('PDF_MAX_MB','20')) * 1024 * 1024:
        raise ModelError(f'{path.name}: PDF exceeds PDF_MAX_MB.')
    dpi = max(100, min(300, int(os.getenv('PDF_OCR_DPI','200'))))
    tessdata = Path(os.getenv('PDF_TESSDATA', str(Path(__file__).parent/'tessdata')))
    force = os.getenv('PDF_FORCE_OCR','false').lower() == 'true'
    with PDF_LOCK:
        try:
            with pymupdf.open(path) as document:
                if document.needs_pass:
                    raise ModelError(f'{path.name}: PDF is password-protected; provide an unlocked copy.')
                if len(document) > int(os.getenv('PDF_MAX_PAGES','100')):
                    raise ModelError(f'{path.name}: PDF exceeds PDF_MAX_PAGES.')
                pages = []
                ocr_count = 0
                for number, page in enumerate(document, 1):
                    text = normalize(page.get_text('text', sort=False))
                    method = 'native'
                    if force or needs_ocr(text):
                        if not text.strip() and not page.get_images() and not page.get_drawings():
                            continue  # genuinely blank page
                        ocr_count += 1
                        if ocr_count > int(os.getenv('PDF_MAX_OCR_PAGES','20')):
                            raise ModelError(f'{path.name}: OCR exceeds PDF_MAX_OCR_PAGES.')
                        if not all((tessdata/(lang+'.traineddata')).is_file() for lang in ('fas','eng')):
                            raise ModelError('Persian/English OCR language files are missing; check PDF_TESSDATA.')
                        pixels = page.rect.width * page.rect.height * (dpi/72)**2
                        if pixels > 16000000:
                            raise ModelError(f'{path.name}, page {number}: page too large for bounded OCR.')
                        tp = page.get_textpage_ocr(language='fas+eng', dpi=dpi, full=True, tessdata=str(tessdata))
                        text = normalize(page.get_text(textpage=tp, sort=False))
                        method = 'ocr'
                        if not any(c.isalpha() for c in text) or text.count('\ufffd') > max(2,len(text)*.02):
                            raise ModelError(f'{path.name}, page {number}: no readable text; provide a clearer PDF.')
                    pages.append((number, text, method))
                    if sum(len(p[1]) for p in pages) > 1000000:
                        raise ModelError(f'{path.name}: extracted text exceeds one million characters.')
                if not pages:
                    raise ModelError(f'{path.name}: no readable text was found.')
                return pages
        except ModelError:
            raise
        except Exception as exc:
            raise ModelError(f'{path.name}: PDF extraction failed; check the file and OCR setup.') from exc
