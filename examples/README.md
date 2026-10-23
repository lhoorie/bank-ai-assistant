# Example evaluation

- [22 scenarios](scenarios.json): questions and expected behavior, not fabricated responses.
- [Actual results](actual-results.json): nine provider-backed requests, with SQL, sources, calculator output, routing, and timings.
- [Persian recheck](persian-opening-recheck.json): a follow-up after strengthening the complete-answer instruction.
- [Local tool results](tool-results.json): deterministic SQL/calculator output, not LLM evaluation.

## Manual review

| Scenario | Observed result |
| --- | --- |
| Account opening | Correct documents and 1,000,000 IRR; accounts.pdf citation |
| Lost card | Correct instructions, 50,000 IRR, three business days |
| Monthly expenses | Correct September total: 3,000,000 IRR |
| City expenses | Correct JOIN results: Tehran 5,500,000; Shiraz 2,000,000 IRR |
| Missing policy | Explicitly reported missing evidence |
| Unsafe SQL | Refused; table counts and opening balances remained unchanged |
| Balance ratio | Database + documents + calculator; correct ratio 12.2 |
| Persian opening | **Partial:** correct age and amount, omitted required documents |
| Out of scope | Declined recipe request |

Eight of nine initial answers matched expectations. The Persian opening answer remained incomplete on recheck even though the retrieved evidence contained all required details. The stronger instruction does not guarantee full coverage. Both attempts are retained; HTTP 200 is not treated as a quality pass. The other 13 scenarios have not been evaluated against the live provider in this run.

Run `python -m scripts.run_scenarios --list` from the project root to list IDs, or use `--ids` to select cases. The runner overwrites its output file; use `--output` to preserve an earlier capture. Model responses and timings can vary between runs.
