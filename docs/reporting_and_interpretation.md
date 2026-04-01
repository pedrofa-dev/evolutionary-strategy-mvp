# Reporting And Interpretation

This document explains how to read the current reporting layer without overstating what the evidence says.

## Reporting Goal

The reporting system is designed to answer one question:

What is the next experiment decision?

It is not designed to maximize metric dumping.

The active research line currently uses policy v2 genomes. For new campaigns, policy v2 is the only active runtime lane; any legacy-shaped snapshots should be interpreted as historical records. When interpreting campaigns, treat the following as the canonical signal-family vocabulary:

- `trend`
- `momentum`
- `breakout`
- `range`
- `volatility`

When documenting or reviewing these families and their rules, use trading terminology in English and make these points explicit:

- what it measures
- trading meaning
- interpretation
- limitation

## Three-Level Artifact Model

Each multiseed campaign is organized into three levels.

Level 1:

- `multiseed_quick_summary.txt`
- always generated
- should fit in one screen
- intended for immediate go / no-go judgment

Level 2:

- `analysis/multiseed_champions_summary.txt`
- generated for decision support
- explains verdict, likely bottleneck, and recommended next action

Level 3:

- `debug/`
- contains detailed diagnostics
- preserves deeper artifacts without polluting the campaign root

## Canonical Automatic Reevaluation Artifacts

Automatic post-multiseed reevaluation keeps:

- human-readable canonical artifacts as `.txt`
- structured canonical artifacts as `.json`

Current automatic artifact names:

- `debug/post_multiseed_validation/post_multiseed_reevaluation_summary.txt`
- `debug/post_multiseed_validation/external/external_reevaluation_report.txt`
- `debug/post_multiseed_validation/external/external_reevaluated_champions.json`
- `debug/post_multiseed_validation/audit/audit_reevaluation_report.txt`
- `debug/post_multiseed_validation/audit/audit_reevaluated_champions.json`

Per-champion JSON snapshots remain under:

- `debug/post_multiseed_validation/external/champions/`
- `debug/post_multiseed_validation/audit/champions/`

Automatic CSV duplication is intentionally not generated in the post-multiseed path.

## Verdict Layer

The decision layer is explicit and deterministic.

Current verdict categories:

- `NO_EDGE_DETECTED`
- `OVERFIT_SUSPECT`
- `WEAK_PROMISING`
- `ROBUST_CANDIDATE`
- `DATASET_LIMIT`
- `GENOME_POLICY_LIMIT`
- `INSUFFICIENT_DIVERSITY`

These verdicts are interpretations, not replacements for evaluation metrics.

## Likely Bottleneck Layer

The reporting layer also distinguishes the most likely current limit:

- signal-space limit
- generalization limit
- dataset coverage limit
- genome or policy limit
- no clear limit

This exists to make the next change explicit instead of drifting into vague experimentation.

## How To Read `NOT_RUN`

`NOT_RUN` means the corresponding post-run validation layer did not execute because the required datasets were unavailable.

It does not mean:

- the strategy passed
- the strategy failed
- robustness was demonstrated

When both external and audit are `NOT_RUN`, the correct interpretation is closer to:

- promising but unconfirmed
- missing evidence prevents stronger generalization claims

## Fallback Warnings

Automatic post-multiseed reevaluation normally resolves datasets from persisted execution context.

If persisted dataset-root context is missing, the system may fall back defensively to `data/datasets`.

When that happens, the system should not pretend the resolution was fully canonical.

It reports:

- a console warning
- a report warning
- `dataset_resolution_fallback_used=true`
- the fallback reason, currently `missing_persisted_dataset_root_context`

## Mixed Catalog Scope

Some campaigns may contain runs that point to different dataset catalogs or roots.

When that happens, reports expose it directly with:

- `catalog_scope_mode = single_catalog | mixed_catalogs`
- `dataset_root_scope_mode = single_root | mixed_roots`
- lists of catalog ids and dataset roots
- a `run_id -> catalog_id -> dataset_root` mapping

Mixed scope is not inherently invalid, but it weakens any casual assumption that the campaign was evaluated against one uniform post-run context.

## What Counts As Stronger Evidence

Evidence is stronger when:

- multiple seeds agree
- multiple configs agree
- validation remains positive
- external remains informative and does not collapse
- audit remains informative and does not collapse
- claims do not rely on fallback resolution or missing layers

Evidence is weaker when:

- only one config family dominates
- champions are extremely low-trade
- validation gaps are high
- external or audit are missing
- automatic resolution had to use fallbacks

## Practical Reading Order

Use this order:

1. quick summary
2. analysis summary
3. reevaluation summary
4. debug artifacts if something still looks ambiguous

Do not start from raw debug outputs unless you are investigating a contradiction or a suspected bug.
