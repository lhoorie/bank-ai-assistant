# Scenario evaluation

- [Scenario dataset](scenarios.json): 22 questions and expected behavior; questions use product names rather than PDF filenames.
- [Latest recorded evaluation](evaluation/mammoth-12-scenarios.json): 12 distinct scenarios with real assistant responses where available, tool traces, per-metric judgments and aggregate coverage.
- [Evaluation dashboard](http://localhost:8000/evaluation): browse reports and expand each scenario.

## Recorded run

Candidate: `nvidia/nemotron-3.5-lightning:free`, run in an isolated temporary assistant server. Judge: `baseten/mammoth-1:free`. Two batches were combined without dropping failures. The primary application's model configuration at capture time was separate from this test server.

Of 12 scenarios, 10 received judgments: 6 passed and 4 failed. Two requests failed while generating assistant responses and have no judge scores. Pass rate is 50% of all cases and 60% of judged cases. HTTP success alone does not imply answer correctness.

| Scenario | Result |
| --- | --- |
| `account-opening` | `pass` |
| `lost-card` | `pass` |
| `monthly-expenses` | `api_error` |
| `city-expenses` | `pass` |
| `missing-policy` | `fail` |
| `sara-balance` | `api_error` |
| `ambiguous-customer` | `pass` |
| `persian-opening` | `fail` |
| `out-of-scope` | `pass` |
| `no-operations` | `pass` |
| `persian-transfer` | `fail` |
| `persian-dispute` | `fail` |

## Metric means and coverage

Scores are custom model judgments on a 0–1 scale, not canonical RAGAS metrics. Unavailable scores and infrastructure errors are excluded from metric means; coverage matters when interpreting each mean.

| Metric | Mean | Scored / total |
| --- | --- | --- |
| `faithfulness` | 0.542 | 6 / 12 |
| `completeness` | 0.625 | 10 / 12 |
| `context_relevance` | 1.000 | 7 / 12 |
| `answer_relevance` | 0.650 | 10 / 12 |
| `correctness` | 0.625 | 10 / 12 |

Mean successful assistant latency: 22.984 seconds; p95: 47.900 seconds. Judge latency is excluded. References are the dataset's expected-behavior rubrics; these are not exhaustive human-written gold answers. Ten other dataset scenarios were not attempted in this report. Model judgments require manual review, especially failures and safety cases.

## Reproduce

With the app running and provider credentials configured in `.env`:

```bash
# List all 22 questions without calling models:
python -m scripts.run_scenarios --list
# Fresh evaluation of the same 12 scenario IDs:
docker compose exec assistant python -m scripts.evaluate_scenarios \
  --model baseten/mammoth-1:free \
  --ids account-opening lost-card monthly-expenses city-expenses missing-policy \
    sara-balance ambiguous-customer persian-opening out-of-scope no-operations \
    persian-transfer persian-dispute \
  --output examples/evaluation/new-run.json
```

Fresh evaluations use the running assistant's model and data; match the recorded candidate configuration for comparisons. Each completed case checkpoints the report. Reusing an output path overwrites it. Review new reports before committing them. Archived capture files were removed; the capture and local-tool scripts still generate their own outputs when invoked.
