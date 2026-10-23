from app.timing import timed
import ast
import math
import operator
import sqlite3
import time
import sqlglot
from sqlglot import exp
from app.seed import DB

SCHEMA = '''SQLite: customers(id INTEGER PRIMARY KEY, name TEXT, city TEXT);
accounts(id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id),
account_type TEXT, opening_balance_irr INTEGER);
transactions(id INTEGER PRIMARY KEY, account_id INTEGER REFERENCES accounts(id),
transaction_date TEXT ISO YYYY-MM-DD, amount_irr INTEGER positive,
direction TEXT: credit or debit, status TEXT: completed/pending/failed, category TEXT).
All amounts are integer Iranian rials (IRR), NOT tomans. Convert to tomans only if explicitly
requested (10 IRR = 1 toman). Expenses = completed debit transactions; income = completed
credit transactions. Exclude pending/failed transactions from totals and balances.
Balance = opening_balance_irr + completed credits - completed debits.
Opening balances precede all sample transactions. Avoid double counting opening balances
when joining transactions: aggregate transactions per account first.
Sample dates are Gregorian September/October 2026. All data is fictional.
There is no authenticated customer: ask for a customer name/id when an ambiguous request
such as "my balance" cannot be resolved; never assume an identity.'''

@timed('sql_execution')
def query(sql):
    if not isinstance(sql, str) or len(sql) > 8000:
        raise ValueError('SQL must be a string of at most 8000 characters.')
    try:
        statements = sqlglot.parse(sql, read='sqlite')
    except sqlglot.errors.ParseError as exc:
        raise ValueError('Invalid SQL syntax.') from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise ValueError('Only a single SELECT statement is allowed.')
    tree = statements[0]
    if any(isinstance(n, (exp.DDL, exp.DML, exp.Into)) for n in tree.walk()):
        raise ValueError('SQL modification is forbidden.')
    allowed_functions = {'sum', 'count', 'avg', 'min', 'max', 'round', 'coalesce',
                         'strftime', 'date', 'substr', 'lower', 'upper', 'abs'}
    safe = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE}
    def authorize(action, a, b, database, source):
        if action in safe:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ and a in {'customers', 'accounts', 'transactions'}:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION and (b or '').lower() in allowed_functions:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    with sqlite3.connect(DB.resolve().as_uri() + '?mode=ro', uri=True) as conn:
        conn.execute('PRAGMA query_only=ON')
        conn.set_authorizer(authorize)
        deadline = time.monotonic() + 2
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        cursor = conn.execute(sql)
        rows = cursor.fetchmany(201)
        return {'sql': sql, 'columns': [x[0] for x in cursor.description],
                'rows': rows[:200], 'truncated': len(rows) > 200}

def calculate(expression):
    if not isinstance(expression, str) or len(expression) > 300:
        raise ValueError('Expression is too long.')
    ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.USub: operator.neg, ast.UAdd: operator.pos}
    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = node.value
        elif isinstance(node, ast.BinOp) and type(node.op) in ops:
            value = ops[type(node.op)](visit(node.left), visit(node.right))
        elif isinstance(node, ast.UnaryOp) and type(node.op) in ops:
            value = ops[type(node.op)](visit(node.operand))
        else:
            raise ValueError('Only numbers and + - * / parentheses are allowed.')
        if not math.isfinite(value) or abs(value) > 1e15:
            raise ValueError('Calculation exceeds numeric limits.')
        return value
    return {'expression': expression, 'result': visit(ast.parse(expression, mode='eval').body)}
