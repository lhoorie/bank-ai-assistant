"""Capture API responses for manual scenario evaluation."""
import argparse
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ids', nargs='+', help='Run only these scenario IDs (default: all).')
    parser.add_argument('--list', action='store_true', help='List IDs without provider calls.')
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--output', type=Path, default=ROOT / 'examples/actual-results.json')
    args = parser.parse_args()
    cases = json.loads((ROOT / 'examples/scenarios.json').read_text(encoding='utf-8'))
    if args.list:
        for case in cases:
            print(f"{case['id']}: {case['question']}")
        return
    if args.ids:
        unknown = set(args.ids) - {c['id'] for c in cases}
        if unknown:
            parser.error('Unknown scenario IDs: ' + ', '.join(sorted(unknown)))
        cases = [c for c in cases if c['id'] in args.ids]
    results = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        req = Request(args.url.rstrip('/') + '/ask', data=json.dumps(
            {'question': case['question']}).encode(), headers={'Content-Type': 'application/json'})
        started = time.monotonic()
        try:
            with urlopen(req, timeout=300) as response:
                status, output = response.status, json.load(response)
        except HTTPError as exc:
            status = exc.code
            try:
                output = json.loads(exc.read())
            except ValueError:
                output = {'error': 'Non-JSON HTTP error response'}
        except (URLError, TimeoutError, ValueError):
            status, output = None, {'error': 'API unavailable, timed out, or returned invalid JSON'}
        results.append({**case, 'http_status': status,
                        'elapsed_seconds': round(time.monotonic()-started, 2), 'actual': output})
        # Save progress after each case; overwrite the selected output file.
        args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"{case['id']}: HTTP {status}, {results[-1]['elapsed_seconds']}s", flush=True)
    print(f'Saved {args.output}; manually review expected versus actual. HTTP 200 is not a quality pass.')


if __name__ == '__main__':
    main()
