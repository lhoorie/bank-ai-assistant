"""Read-only access to locally generated evaluation reports."""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix='/api/evaluations', tags=['evaluation'])
REPORTS = Path(__file__).resolve().parents[1] / 'examples' / 'evaluation'
MAX_BYTES = 20 * 1024 * 1024


def read_report(name):
    # Accept direct JSON children only; reject traversal and symlinks escaping storage.
    if Path(name).name != name or not name.endswith('.json'):
        raise HTTPException(404, 'Report not found')
    path = REPORTS / name
    if path.is_symlink() or not path.is_file():
        raise HTTPException(404, 'Report not found')
    if path.stat().st_size > MAX_BYTES:
        raise HTTPException(413, 'Report exceeds 20 MB')
    try:
        report = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(report, dict) or not isinstance(report.get('results'), list) or not isinstance(report.get('summary'), dict):
            raise ValueError()
        return report
    except (ValueError, UnicodeError):
        raise HTTPException(422, 'Invalid evaluation report')


@router.get('')
def list_reports():
    reports = []
    for path in sorted(REPORTS.glob('*.json'), reverse=True):
        try:
            report = read_report(path.name)
        except (HTTPException, OSError):
            continue
        reports.append({'name': path.name, 'created_at': report.get('created_at'),
                        'judge_model': report.get('judge_model'), 'summary': report['summary']})
    return {'reports': reports}


@router.get('/{name}')
def report_detail(name: str):
    return read_report(name)
