from pathlib import Path
import pytest
import pymupdf
from app.pdf_text import extract_pages, normalize, needs_ocr
from app.model import ModelError


def test_persian_normalization_and_direction_checks():
    assert normalize('ﺣﺴﺎﺏ ي ك\u200f') == 'حساب ی ک'
    assert not needs_ocr('برای افتتاح حساب موجودی کافی لازم است. Sara 123')
    assert needs_ocr('یارب حاتتفا باسح یدوجوم')
    assert needs_ocr('��� unreadable')


def test_native_text_and_page_numbers(tmp_path):
    path=tmp_path/'native.pdf'
    with pymupdf.open() as doc:
        doc.new_page().insert_text((40,40),'Account minimum 2000000 IRR. Sara 123.')
        doc.new_page().insert_text((40,40),'Replacement card costs 120000 IRR.')
        doc.save(path)
    pages=extract_pages(path)
    assert [p[0] for p in pages] == [1,2]
    assert all(p[2]=='native' for p in pages)
    assert '2000000 IRR' in pages[0][1]


def test_password_protected_and_page_limit(tmp_path, monkeypatch):
    path=tmp_path/'encrypted.pdf'
    with pymupdf.open() as doc:
        doc.new_page().insert_text((40,40),'Example')
        doc.save(path,encryption=pymupdf.PDF_ENCRYPT_AES_256,user_pw='secret',owner_pw='owner')
    with pytest.raises(ModelError,match='password-protected'):extract_pages(path)
    path=tmp_path/'long.pdf'
    with pymupdf.open() as doc:
        doc.new_page();doc.new_page();doc.save(path)
    monkeypatch.setenv('PDF_MAX_PAGES','1')
    with pytest.raises(ModelError,match='PDF_MAX_PAGES'):extract_pages(path)


def test_scanned_page_uses_real_ocr_in_memory(tmp_path):
    path=tmp_path/'scan.pdf'
    with pymupdf.open() as source:
        page=source.new_page()
        page.insert_text((60,80),'Account minimum balance 2000000 IRR',fontsize=20)
        pixmap=page.get_pixmap(matrix=pymupdf.Matrix(2,2))
        with pymupdf.open() as scan:
            p=scan.new_page();p.insert_image(p.rect,stream=pixmap.tobytes('png'));scan.save(path)
    pages=extract_pages(path)
    assert pages[0][2]=='ocr'
    assert '2000000' in pages[0][1]
    assert sorted(p.name for p in tmp_path.iterdir()) == ['scan.pdf']


def test_blank_or_broken_pdf_is_not_silently_indexed(tmp_path):
    blank=tmp_path/'blank.pdf'
    with pymupdf.open() as doc:doc.new_page();doc.save(blank)
    with pytest.raises(ModelError,match='no readable text'):extract_pages(blank)
    broken=tmp_path/'broken.pdf';broken.write_bytes(b'not a PDF')
    with pytest.raises(ModelError,match='extraction failed'):extract_pages(broken)
