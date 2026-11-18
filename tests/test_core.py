from copy import deepcopy
import json

import pytest

from craft_core._json import digest
from craft_core.commit import authorize_launch, commit_prediction, verify_prediction, verify_prediction_archive
from craft_core.demo import fixtures, run
from craft_core.evaluation import default_protocol
from craft_core.probability import distribution, prefix_distribution, score
from craft_core.skills import compatible, default_program, mutate, seal, unseal, validate_program


def inputs():
    protocol = default_protocol()
    binding, prediction, _ = fixtures(digest(protocol), protocol)
    return binding, prediction


def test_commit_before_launch_and_archive_audit(tmp_path):
    binding, prediction = inputs()
    receipt = commit_prediction(tmp_path, prediction=prediction, binding=binding)
    authorize_launch(tmp_path, receipt=receipt, binding=binding)
    record = verify_prediction_archive(tmp_path, receipt=receipt, binding=binding)
    assert record['prediction'] == prediction
    with pytest.raises(FileExistsError):
        authorize_launch(tmp_path, receipt=receipt, binding=binding)
    with pytest.raises(ValueError):
        commit_prediction(tmp_path, prediction=prediction, binding=binding)


def test_tampering_cannot_disable_hash_verification(tmp_path):
    binding, prediction = inputs()
    binding['input_hash_checks_enabled'] = False
    receipt = commit_prediction(tmp_path, prediction=prediction, binding=binding)
    (tmp_path / 'prediction_record.json').write_text('{}')
    with pytest.raises(ValueError, match='hash mismatch'):
        authorize_launch(tmp_path, receipt=receipt, binding=binding)


@pytest.mark.parametrize('field', ['effective_signature', 'source_fingerprint', 'memory_version', 'skill_version'])
def test_changed_binding_is_rejected(tmp_path, field):
    binding, prediction = inputs()
    receipt = commit_prediction(tmp_path, prediction=prediction, binding=binding)
    binding[field] = 'changed'
    with pytest.raises(ValueError, match='changed after'):
        verify_prediction(tmp_path, receipt=receipt, binding=binding)


@pytest.mark.parametrize('name', ['outcome.json', 'implementation_result.json', 'craft_trial.json', 'build_1/craft_run_manifest.json'])
def test_retrospective_predictions_are_rejected(tmp_path, name):
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{}')
    binding, prediction = inputs()
    with pytest.raises(ValueError):
        commit_prediction(tmp_path, prediction=prediction, binding=binding)


def test_empty_falsifier_and_nonfinite_forecast_are_rejected(tmp_path):
    binding, prediction = inputs()
    prediction['falsification_conditions'] = []
    with pytest.raises(ValueError):
        commit_prediction(tmp_path, prediction=prediction, binding=binding)
    prediction['falsification_conditions'] = ['example']
    prediction['expected_qor'] = {'value': float('nan')}
    with pytest.raises(ValueError):
        commit_prediction(tmp_path, prediction=prediction, binding=binding)


def test_probabilities_keep_abstentions_and_unknowns_distinct():
    assert sum(distribution(0.4, 0.3).values()) == pytest.approx(1.)
    result = score(distribution(0.4, 0.3), 'Neutral')
    assert result['classification'] == 'Abstain'
    assert result['correct'] is None
    assert result['brier_multiclass'] == pytest.approx(.74)
    assert score(distribution(.8, .1), 'Inconclusive')['status'] == 'Inconclusive'
    assert prefix_distribution([{'response': 'Inconclusive'}]) == prefix_distribution([])
    with pytest.raises(ValueError):
        distribution(.8, .8)


def test_skill_edits_are_bounded_and_do_not_mutate_the_parent():
    parent = default_program()
    before = deepcopy(parent)
    child = mutate(parent, 'require_delay_decomposition')
    assert parent == before
    assert child['version'] == 2 and child['parent'] == digest(parent)
    assert child['rules']['diagnosis']['delay_check'] == 'required'
    assert child['rules']['prediction'] == parent['rules']['prediction']
    with pytest.raises(ValueError):
        mutate(child, 'require_delay_decomposition')
    with pytest.raises(ValueError):
        mutate(parent, 'disable_evaluator')
    child['rules']['permissions'] = {'execute': True}
    with pytest.raises(ValueError):
        validate_program(child)


def test_scope_and_integrity_are_exact():
    scope = dict(design='demo', design_fingerprint='demo-hash', technology='synthetic', toolchain='fixture', constraints='fixed', evaluator='v1', stage='route')
    assert compatible(scope, dict(scope))
    assert not compatible(scope, {**scope, 'technology': 'another'})
    value = seal({'case': 1})
    assert unseal(value) == {'case': 1}
    value['case'] = 2
    with pytest.raises(ValueError):
        unseal(value)


def test_complete_demo_is_explicitly_synthetic_and_refuses_overwrite(tmp_path):
    output = tmp_path / 'demo'
    result = run(output)
    assert result == {'data_kind': 'synthetic_example', 'physical_response': 'supported', 'qor_prediction': 'refuted',
        'missing_evidence': 'not_evaluable', 'skill_revision': 'candidate_only', 'eda_or_llm_executed': False}
    summary = json.loads((output / 'summary.json').read_text())
    assert summary['forecast_accounting']['qor']['conditional_accuracy']['value'] is None
    with pytest.raises(FileExistsError):
        run(output)
