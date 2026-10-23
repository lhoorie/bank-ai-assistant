"""Deterministic fictional banking data; no real banking rules or accounts."""
import sqlite3
from pathlib import Path
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DOCS = DATA / 'bank_documents'
DB = DATA / 'bank.db'

POLICIES = {
    'accounts.pdf': ('Account services - fictional demo rules', [
        'ADAN DEMO BANK - fictional sample data, not real bank policies',
        'Opening a demo account requires an identity document and a verified mobile number.',
        'The fictional minimum opening balance is 1000000 IRR.',
        'Demo account statements are available for the last 12 months.',
        'All database amounts are Iranian rials (IRR), not tomans.',
    ]),
    'cards.pdf': ('Card services - fictional demo rules', [
        'ADAN DEMO BANK - fictional sample data, not real bank policies',
        'Report a lost card immediately using the demo banking app or demo support.',
        'A fictional replacement card costs 50000 IRR and takes 3 business days.',
        'A replacement request requires identity verification.',
        'Never share your PIN, password or one-time password with the assistant.',
        'This assistant only answers questions; it cannot block cards or move money.',
    ]),
}

def seed():
    DOCS.mkdir(parents=True, exist_ok=True)
    for name, (title, lines) in POLICIES.items():
        path = DOCS / name
        if not path.exists():
            pdf = canvas.Canvas(str(path), invariant=1)
            pdf.setTitle(title)
            pdf.setFont('Helvetica-Bold', 16)
            pdf.drawString(40, 790, title)
            pdf.setFont('Helvetica', 10)
            for i, line in enumerate(lines):
                pdf.drawString(40, 755 - i * 24, line)
            pdf.save()
    with sqlite3.connect(DB) as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
            account_type TEXT NOT NULL, opening_balance_irr INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id),
            transaction_date TEXT NOT NULL, amount_irr INTEGER NOT NULL CHECK(amount_irr > 0),
            direction TEXT NOT NULL CHECK(direction IN ('credit','debit')),
            status TEXT NOT NULL CHECK(status IN ('completed','pending','failed')),
            category TEXT NOT NULL);
        ''')
        conn.executemany('INSERT OR IGNORE INTO customers VALUES (?,?,?)', [
            (1, 'Sara', 'Tehran'), (2, 'Ali', 'Shiraz'), (3, 'Mina', 'Tehran')])
        conn.executemany('INSERT OR IGNORE INTO accounts VALUES (?,?,?,?)', [
            (1, 1, 'current', 10000000), (2, 2, 'savings', 20000000),
            (3, 3, 'current', 15000000)])
        conn.executemany('INSERT OR IGNORE INTO transactions VALUES (?,?,?,?,?,?,?)', [
            (1, 1, '2026-09-05', 1000000, 'debit', 'completed', 'groceries'),
            (2, 2, '2026-09-12', 2000000, 'debit', 'completed', 'rent'),
            (3, 1, '2026-10-03', 1800000, 'debit', 'completed', 'groceries'),
            (4, 3, '2026-10-10', 2700000, 'debit', 'completed', 'rent'),
            (5, 2, '2026-10-11', 900000, 'debit', 'failed', 'shopping'),
            (6, 1, '2026-10-01', 5000000, 'credit', 'completed', 'salary'),
            (7, 3, '2026-10-12', 400000, 'debit', 'pending', 'shopping')])

if __name__ == '__main__':
    seed()
