# Offline walkthrough

From the repository root, run:

```bash
PYTHONPATH=src python3 -m craft_core.demo --output demo-output
```

No EDA executable, model endpoint, API token or GPU is used. All inputs are synthetic, including the measurement and verification fields.

The command creates a new directory and refuses to overwrite an existing one:

| File | Purpose |
| --- | --- |
| `protocol.json` | Scoring semantics, units and tolerances selected before the example prediction. |
| `prediction_record.json` | Prediction and its candidate/source/protocol binding. |
| `prediction_commit.json` | Content hash and local commitment timestamps. |
| `receipt.json` | Receipt retained for later verification. |
| `execution_launch.json` | Demonstrates authorization ordering; no process is launched. |
| `outcome.json` | Explicitly labeled synthetic outcome. |
| `evaluation.json` | Separate physical-response, QoR and risk accounting. |
| `missing_evidence_example.json` | The same example with missing original-object continuity. |
| `probability_example.json` | Three-class prediction scored against a synthetic neutral outcome. |
| `skill_candidate.json` | One allowed change to the initial policy; no promotion is performed. |
| `summary.json` | Full-denominator accounting and the synthetic-example label. |

In the example, net delay changes from 2.0 to 1.8 ns while setup WNS remains 0.10 ns. The physical-response forecast is supported, but the forecast of increased WNS is refuted. These values illustrate different evaluation axes; they do not describe a circuit optimization result.

The fixed forecast is an engineering template, so native-model conditional accuracy remains `null`. Unknown evidence also remains unknown rather than becoming a failed prediction.
