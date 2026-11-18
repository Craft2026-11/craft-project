# Design and integration

The package separates a pre-execution prediction from the measured outcome supplied later. It never asks a language model to decide whether its own prediction was correct.

## Prediction records

`craft_core.commit.commit_prediction(directory, prediction=..., binding=...)` writes a prediction record and commit receipt into an existing fresh directory. The binding identifies the candidate, source, constraints, accessible evidence, controller, predictor and experience versions. Predictions include a hypothesis, target, operator, expected physical change, expected QoR, constraint risk and falsification conditions.

Call `authorize_launch` immediately before your own executor. It verifies the record, hashes and binding and writes a launch receipt. **It does not execute an EDA command or grant operating-system permissions.** A second launch or a retrospectively added prediction is refused.

`verify_prediction_archive` checks saved records without comparing their monotonic clock to the current boot. The checks provide local consistency and ordering evidence, not signed attestation. A party who can replace all files and receipts controls this local record; use separate trusted storage if stronger integrity is required.

## Independent evaluation axes

`evaluate_prediction(record, outcome, protocol)` consumes caller-supplied observations. The integration must obtain measurements from real tools and validate their identity before filling verification fields.

| Axis | Required evidence | Interpretation |
| --- | --- | --- |
| Physical response | Paired measurements, verified execution, complete measurement and original-object continuity | Whether the declared directional response is supported. |
| QoR | Completed execution and finite paired values under the bound protocol | Whether the forecast about the measured metric is supported. |
| Constraint risk | Consistent setup, hold and DRC measurements and strict checks | Whether the predicted post-action physical risk matches. |

A physical response can be supported without a QoR benefit. Missing or nonfinite values are not replaced by zeros. Tool failure is not labeled as a measured violation. Unstructured prose is not retrospectively interpreted by an outcome-aware judge.

The evaluation protocol must be bound before execution. Its metric units and tolerances are explicit. The default values are implementation defaults for these components; they do not supply experiment settings missing from the manuscript.

## Denominators and prediction roles

`summarize_evaluations` reports both evaluable coverage and accuracy conditional on evaluable assertions. Abstentions, failures and missing evidence remain in the complete intervention count. Distinct controllers, splits, model identities or scoring protocols are not pooled into one claimed accuracy.

The offline demo uses `forecast_role="engineering_template"`. Its fixed forecasts are excluded from native-model accuracy, even when their observable directions happen to match the synthetic values. The evaluator does not independently certify the role a caller supplies.

`probability.score` provides multiclass Brier scoring and a 0.6 confidence threshold inherited from the extracted implementation. Pass valid beneficial / neutral / harmful probabilities, e.g. those returned by `distribution` or `prefix_distribution`. The confidence threshold is an implementation detail, not a universal confidence guarantee.

## Bounded skill candidates

`default_program()` returns a fresh policy. `mutate(program, patch)` accepts only registered typed patches, retains the parent fingerprint and increments the version. It cannot introduce fields for modifying evaluators or tool permissions.

`compatible` requires exact design, technology, toolchain, constraint, evaluator and stage scope. The helpers do not establish the truth of scope strings; that remains an adapter responsibility.

This release does not include the full experience store, prospective paired shadow validation, promotion or rollback controller. A successfully created candidate is **not a validated or deployed policy**.

## External integration responsibilities

To build an actual optimization system around these components, supply:

1. A report/evidence adapter with measured values and identity checks.
2. A planner or LLM client that produces candidate actions and predictions.
3. A legal action compiler, isolated executor and licensed/configured EDA flow.
4. A measured outcome adapter and acceptance policy.
5. The complete experience-validation and promotion lifecycle, if used.

Do not load a PDK, tool binary, private netlist or API credential into this repository. The package itself performs no network calls and has no credential configuration.
