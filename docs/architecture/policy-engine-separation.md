# Policy Engine Separation

## Objective

Prepare the decision-policy layer for a future split between:

- code engines that provide policy behavior
- declarative policy definitions or assets

This phase does **not** change the runtime policy contract or decision
semantics. It only introduces a small explicit seam so the current built-in
policy can be treated as engine-provided code.

## Before

Before this change, the built-in policy lived directly as a runtime
`DecisionPolicy` implementation in:

- `src/evo_system/experimental_space/decision_policies.py`

The rest of the runtime consumed that policy directly through the existing
decision-policy registry.

## After

The built-in runtime policy still exists and is still the official contract
consumed by the environment.

What changed is that there is now an explicit built-in `PolicyEngine` in code:

- `src/evo_system/experimental_space/policy_engines/plugins/default_policy_engine.py`

That engine builds the same default runtime `DecisionPolicy` implementation.

## What Is Engine Code Now

Engine code is the layer that knows how to provide a runtime decision policy
from code.

In this phase that means:

- `DefaultPolicyEngine`

Its responsibility is only to construct the built-in runtime policy object.

## What Remains The Official Runtime Policy

The official runtime policy contract is still:

- `DecisionPolicy`

The active built-in runtime implementation is still:

- `DefaultDecisionPolicy`

The environment and evaluator-adjacent runtime paths still consume
`DecisionPolicy`, not `PolicyEngine`.

## What This Prepares For

This separation prepares future work where:

- code engines can provide policy behavior
- declarative policy assets can describe configurations or variants
- the core can keep a stable runtime contract while supporting richer loading
  and registration paths later

## What Is Not Supported Yet

- declarative decision policies are not operational yet
- runtime policy selection is not driven by policy-engine registries yet
- there is no plugin discovery flow for policy engines yet
- no business logic has been moved out of the current runtime decision policy

This keeps the refactor small, reversible, and behavior-safe.
