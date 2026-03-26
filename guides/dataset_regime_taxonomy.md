# Dataset Regime Taxonomy

This taxonomy defines a small shared vocabulary for labeling curated datasets.

Its purpose is descriptive metadata for dataset curation, analysis, and reporting.

It is **not** a source of trading logic, evaluation logic, or champion policy.

## Dimensions

### `regime_primary`

Use one primary market regime label:

- `bull`
- `bear`
- `lateral`
- `transition`

### `regime_secondary`

Use one secondary behavior label:

- `breakout`
- `recovery`
- `capitulation`
- `range`
- `trend`
- `event_driven`
- `post_shock`

### `volatility`

Use one volatility label:

- `low`
- `medium`
- `high`

### `event_tag`

Use a short event tag when relevant. If no specific event applies, use `none`.

Examples:

- `none`
- `merge`
- `ftx`
- `spot_btc_etf`
- `spot_eth_etf`
- `macro_shock`

## Usage Guidance

- Keep labels simple and stable over time.
- Prefer consistency over precision.
- Use the smallest reasonable set of labels for a dataset window.
- If a window does not fit perfectly, choose the closest practical label rather than inventing a new one immediately.

## Future Extension

This taxonomy is intentionally minimal.

If future dataset catalogs need more detail, extend it carefully and only when the added label improves cross-run analysis or auditability.
