"""An explicitly synthetic, offline walkthrough of the released components."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from ._json import digest
from .commit import authorize_launch, commit_prediction, file_sha, verify_prediction_archive
from .evaluation import default_protocol, evaluate_prediction, summarize_evaluations
from .probability import distribution, score
from .skills import default_program, mutate


def fixtures(protocol_sha, protocol):
    """Hand-authored examples, not recorded design measurements or LLM output."""
    binding = {
        'candidate_id': 'synthetic-candidate-001',
        'effective_signature': digest({'example_action': 'reduce_target_net_delay'}),
        'source_fingerprint': digest({'synthetic_design': 'example-001'}),
        'constraint_fingerprint': digest({'synthetic_clock_ns': 10.0}),
        'evidence_access_scope': ['synthetic_timing_path'],
        'predictor_id': 'synthetic-fixture',
        'design_split': 'engineering',
        'controller_version': 'craft-core-demo-0.1.0',
        'memory_version': None,
        'skill_version': 'example-v1',
        'evaluation_protocol_sha256': protocol_sha,
        'evaluation_protocol_digest': digest(protocol),
        # A deterministic fixture is not a native LLM prediction.
        'forecast_role': 'engineering_template',
    }
    prediction = {
        'hypothesis': 'Illustrative local edit may reduce the same path net delay.',
        'target': {'path': 'example_source/Q -> example_sink/D'},
        'operator': 'synthetic_local_edit',
        'source_evidence_complete': True,
        'expected_physical_change': {'metric_directions': {'timing_path_net_delay_ns': 'decrease'}},
        'expected_qor': {'metric_directions': {'setup_wns_ns': 'increase'}},
        'constraint_risk': {'prediction': 'no_risk'},
        'falsification_conditions': ['Target net delay does not decrease.', 'Setup WNS does not improve.'],
    }
    outcome = {
        **{key: binding[key] for key in ('source_fingerprint', 'effective_signature', 'evaluation_protocol_sha256')},
        'execution_status': 'completed',
        'qor_before': {'setup_wns_ns': 0.10},
        'qor_after': {'setup_wns_ns': 0.10},
        'mechanism_before': {'timing_path_net_delay_ns': 2.0},
        'mechanism_after': {'timing_path_net_delay_ns': 1.8},
        'verification': {'execution_verified': True, 'measurement_complete': True,
                         'original_object_continuity_verified': True, 'intervention_observed': True},
        'strict_gate': {'mode': 'strict',
            'checks': {'flow_complete': True, 'setup_clean': True, 'hold_clean': True, 'drc_clean': True},
            'violation_metrics': {'setup_wns_ns': 0.10, 'setup_tns_ns': 0., 'setup_violating_paths': 0,
                'hold_wns_ns': 0.02, 'hold_tns_ns': 0., 'hold_violating_paths': 0, 'route_drc': 0}},
        'post_attribution': {'asserted': False},
        'actual_costs': {},
        'data_kind': 'synthetic_example',
        'execution_note': 'All measurement and verification fields are fixtures. No EDA tool was run.',
    }
    return binding, prediction, outcome


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')


def run(output):
    output = Path(output)
    # An existing directory is never reused: a new demo cannot overwrite a record.
    output.mkdir(parents=True, exist_ok=False)
    protocol = default_protocol()
    write_new(output / 'protocol.json', protocol)
    binding, prediction, outcome = fixtures(file_sha(output / 'protocol.json'), protocol)
    receipt = commit_prediction(output, prediction=prediction, binding=binding)
    write_new(output / 'receipt.json', receipt)
    authorize_launch(output, receipt=receipt, binding=binding)
    # Demonstrate record ordering only; this receipt does not invoke an executor.
    write_new(output / 'outcome.json', outcome)
    record = verify_prediction_archive(output, receipt=receipt, binding=binding)
    evaluation = evaluate_prediction(record, outcome, protocol)
    write_new(output / 'evaluation.json', evaluation)
    missing = deepcopy(outcome)
    missing['verification']['original_object_continuity_verified'] = False
    partial = evaluate_prediction(record, missing, protocol)
    write_new(output / 'missing_evidence_example.json', partial)
    program = default_program()
    revision = mutate(program, 'require_delay_decomposition')
    write_new(output / 'skill_candidate.json', {'status': 'candidate_only', 'base': program, 'candidate': revision,
        'note': 'No prospective validation or policy promotion is performed in this demo.'})
    forecasts = distribution(0.7, 0.2)
    write_new(output / 'probability_example.json', score(forecasts, 'Neutral'))
    write_new(output / 'summary.json', {'data_kind': 'synthetic_example',
        'scope': 'Offline component demonstration; no EDA, LLM or paper benchmark reproduction.',
        'forecast_accounting': summarize_evaluations([evaluation, partial])})
    return {
        'data_kind': 'synthetic_example',
        'physical_response': evaluation['scores']['mechanism']['engineering_observation']['status'],
        'qor_prediction': evaluation['scores']['qor']['engineering_observation']['status'],
        'missing_evidence': partial['scores']['mechanism']['engineering_observation']['status'],
        'skill_revision': 'candidate_only',
        'eda_or_llm_executed': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('demo-output'), help='A new directory; existing directories are refused.')
    args = parser.parse_args()
    try:
        result = run(args.output)
    except FileExistsError:
        parser.exit(2, 'Output already exists. Choose a new --output directory.\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
