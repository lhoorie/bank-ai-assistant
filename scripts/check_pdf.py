"""Inspect extracted PDF text without embeddings, indexing or disk output."""
import argparse
from pathlib import Path
from app.pdf_text import extract_pages

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('pdf',type=Path)
    args=parser.parse_args()
    for number,text,method in extract_pages(args.pdf):
        print(f'\n--- Page {number} | {method} | {len(text)} characters ---\n{text}')
