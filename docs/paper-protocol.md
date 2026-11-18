# Manuscript protocol reference

This reference follows the manuscript snapshot supplied on 17 November 2026. It describes the full paper experiments, not the portable demo. The source archive and commercial technology assets are not distributed here.

## Benchmarks and budgets

| Design | SKY130 clock (ns) | SKY130 cells | 28 nm clock (ns) | 28 nm cells | Budget |
| --- | ---: | ---: | ---: | ---: | ---: |
| CPU Tile | 20.0 | 13891 | 20.0 | 14992 | 8 h |
| NoCRouter | 30.0 | 51108 | 20.0 | 54530 | 16 h |
| RISC-V CPU | 40.0 | 123040 | 30.0 | 136416 | 40 h |

The manuscript aims to support approximately 20–40 optimization iterations through these time budgets; this is not a fixed evaluation count for every run.

## Tools and models

- Logic synthesis: Cadence Genus.
- Physical design: Cadence Innovus.
- Power analysis: Cadence Joules 201.
- Process nodes: SKY130 and a commercial 28 nm PDK.
- LLM backbones: Qwen3.5, Llama 3.1 and Ministral 3.
- Hardware: two Intel Xeon Platinum 8462Y+ processors and one NVIDIA H100.
- Cross-toolchain study: Yosys–OpenROAD, reported separately.

Model sizes, sampling parameters and other unreported settings are not inferred. The core package does not provision any of these tools or models.

## Representative action candidates

The manuscript reports 46 tool parameters and 6 physical adjustments. The table below reproduces its 17 representative entries; it does not enumerate the entire action space.

| Stage | Parameter / adjustment | Candidates |
| --- | --- | --- |
| Logic synthesis | `syn_generic_effort` | low, medium, high |
| Logic synthesis | `syn_map_effort` | low, medium, high |
| Logic synthesis | `syn_opt_effort` | none, low, medium, high |
| Floorplan | `std_density` | 0.50, 0.60, 0.70, 0.75, 0.80 |
| Floorplan | `core_margin` | io, pin |
| Floorplan | `core_Left/Bottom/Right/Top` | 1.0, 2.5, 5.0 |
| Placement | `place_global_cong_effort` | low, medium, high, auto |
| Placement | `cell_padding` | 0, 1, 2, 3, 4 |
| CTS | `useful_skew` | false, true |
| CTS | `useful_skew_ccopt_effort` | none, standard, medium, extreme |
| CTS | `clone_clock_gates` | false, true |
| Routing | `hold_target_slack` | 2%, 2.5%, 5% |
| Routing | `setup_target_slack` | 2%, 2.5%, 5% |
| Routing | `postroute_cong_effort` | low, medium, high |
| Physical adjustments | `Timing constraint` | Decrease, Unchanged, Increase |
| Physical adjustments | `Floorplan die size` | Decrease, Unchanged, Increase |
| Physical adjustments | `Macro placement` | Left, Right, Up, Down |

## Reading the reported metrics

Effective Clock Period is `ECP = target clock period − WNS`; lower is better. Timing comparisons remain tied to their design, process and experiment settings. ECP alone does not establish signoff.

The agent comparison table reports ECP and TNS in ns; area is µm² for CPU Tile and NoCRouter and mm² for RISC-V CPU. Power units are not explicitly specified in the source tables. The tuner table does not independently declare its area units. Missing units are not reconstructed.

Repeat-run means and standard deviations are preserved as reported rather than recomputed from rounded samples. Diagnostic/experience ablation, repeated-run stability, open-source-toolchain layouts and skill-adaptation examples are separate studies.

Sources: Experimental Setup; Benchmark Designs with Two Process Nodes; Primary EDA Tool Parameters and Physical Adjustments; and the manuscript experimental comparison tables.
