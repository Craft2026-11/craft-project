# Release 0.1.0: scope and provenance

This is a selected source release from the CRAFT research implementation, repackaged as `craft_core`. It is not a complete optimizer, a frozen paper reproduction bundle, or a claim that the included demo generates the reported PPA results.

## Source extraction

| Public module | Origin and changes |
| --- | --- |
| `commit.py` | Prediction commitment module: renamed legacy artifact prefixes; always verifies committed hashes; requires a nonempty falsification list. |
| `evaluation.py` | Prediction reliability evaluator: replaced its compiler import with the same small canonical-JSON digest helper. |
| `probability.py` | Four independent probability and scoring functions extracted from the action-case implementation. |
| `skills.py` | Typed scope, policy validation, integrity, mutation and forecast helpers extracted from the experience-skill implementation. The original initial policy is embedded under a public schema name. |
| `demo.py` | New synthetic integration example that exercises the extracted functions without tools or model calls. |

EDA-dependent controller imports, workspace paths and campaign-specific entry points were not carried over. Tests include adapted independent evaluator tests and new tests for the packaged components. Original SVG artwork was created for this repository.

The core contains no bundled third-party source or runtime library. Development tests use pytest, installed separately under its own license. The repository's existing MIT license is retained.

## Included and excluded

Included: portable source, a synthetic offline demo, automated tests, manuscript protocol notes, project artwork and integration documentation.

Excluded: the full agent controller; complete diagnostic acquisition and action generation; commercial EDA executors; checkpoint databases; technology libraries; foundry files; design RTL/GDS/netlists; model weights; API credentials; experiment logs; unpublished raw measurements; and the complete prospective skill validation/promotion system.

The example's values, identities and verification fields are hand-authored fixtures. They must not be treated as EDA measurements, LLM outputs, independent causal evidence or benchmark results.

## Release verification

The component test suite checks record ordering, immutable binding, changed-content rejection, missing measurements, frozen scoring semantics, abstention accounting, exact scope and typed policy edits. A packaged installation and the documented command are also checked before publication. Tests are not a substitute for validating any future EDA integration.

## Planned extensions

Potential later releases include curated real-run trace exports, selected backend adapters and benchmark reproduction instructions. They will need explicit provenance, dependencies and redistribution boundaries. No unreleased component is exposed through a placeholder download.
