# Tracking reward ablation exact outputs

These files were generated from the seven exact W&B run IDs with `run.scan_history()` called once per metric. No value was estimated from a screenshot.

## Statistical interpretation

- Final statistics use the last 100 non-null records per run and metric.
- All seven supplied runs use one seed. Temporal SD is within-run training-window variability, not cross-seed SD.
- No significance test is performed.
- Positive error/cost change means the value increased relative to Full (normally worse). Positive episode-length change means the length increased (normally better).
- Time-out event share is not a strict success rate because termination conditions may overlap.

## Main files

- `<slug>_history_exact.csv`: independently scanned metrics outer-joined on `_step`.
- `all_history_exact.csv`: all seven run histories.
- `run_metadata_exact.json/.csv`: run ID, name, timestamps, state, config, summary, and W&B URL.
- `checkpoint_summary_exact.csv`: checkpoint state dictionaries, iteration, SHA256, and policy-std statistics.
- `final100_summary_exact.csv`: mean, temporal SD, min, max, median, N, and actual step bounds for every metric/configuration.
- `table1_tracking_accuracy_exact.csv`: tracking/episode-length table.
- `table2_physical_quality_exact.csv`: physical-quality/policy-std table.
- `termination_summary_exact.csv`: final-window termination totals and time-out event share.
- `figures/`: eight PNG/PDF figures plus exact plotted-data CSVs.
- `validation_report.txt/.json`: data-quality and methodology checks.

## Validation result

- Status: `FAIL`
- Errors: 9
- Warnings: 0
