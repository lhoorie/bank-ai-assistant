"""Record SQL and calculator outputs without calling a language model."""
import json
from pathlib import Path
from app.seed import seed
from app.tools import query, calculate

seed()
result = {
    'note': 'Actual local tool outputs; not provider-backed LLM responses.',
    'expenses': query("SELECT substr(transaction_date,1,7) AS month, SUM(amount_irr) AS expenses_irr "
                   "FROM transactions WHERE status='completed' AND direction='debit' GROUP BY month ORDER BY month"),
    'calculator': calculate('(4500000-3000000)/3000000*100'),
}
Path('examples/tool-results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print('Saved examples/tool-results.json')
