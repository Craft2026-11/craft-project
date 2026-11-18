from copy import deepcopy
import json

import pytest

from craft_core._json import digest
from craft_core.evaluation import default_protocol,validate_protocol,evaluate_prediction,summarize_evaluations


def case():
    protocol=default_protocol()
    binding={'source_fingerprint':'a'*64,'effective_signature':'b'*64,'evaluation_protocol_sha256':'c'*64,
        'evaluation_protocol_digest':digest(protocol),'predictor_id':'test','controller_version':'test-v1','design_split':'engineering','forecast_role':'native'}
    record={'binding':binding,'prediction':{'source_evidence_complete':True,
        'expected_physical_change':{'metric_directions':{'timing_path_net_delay_ns':'decrease'}},
        'expected_qor':{'metric_directions':{'setup_wns_ns':'increase'}},'constraint_risk':{'prediction':'no_risk'}}}
    outcome={**{key:binding[key] for key in ('source_fingerprint','effective_signature','evaluation_protocol_sha256')},
        'execution_status':'completed','qor_before':{'setup_wns_ns':-1.},'qor_after':{'setup_wns_ns':1.},
        'mechanism_before':{'timing_path_net_delay_ns':2.},'mechanism_after':{'timing_path_net_delay_ns':1.},
        'verification':{'execution_verified':True,'measurement_complete':True,
            'original_object_continuity_verified':True,'mechanism_supported':True,'intervention_observed':True},
        'strict_gate':{'mode':'strict','checks':{'flow_complete':True,'setup_clean':True,'hold_clean':True,'drc_clean':True},
            'violation_metrics':{'setup_wns_ns':1.,'setup_tns_ns':0.,'setup_violating_paths':0,
                'hold_wns_ns':.04,'hold_tns_ns':0.,'hold_violating_paths':0,'route_drc':0}},
        'post_attribution':{'asserted':True,'kind':'bounded_mechanism','prediction_identity_verified':True},
        'actual_costs':{'make_seconds':10.,'executor_wall_seconds':12.,'inspect_seconds':None}}
    return record,outcome,protocol


def test_independent_scores_and_full_counts():
    row=evaluate_prediction(*case())
    assert all(score['status']=='supported' for score in row['scores'].values())
    assert row['attribution']['status']=='evidence_supported'
    result=summarize_evaluations([row])
    assert result['mechanism']['conditional_accuracy']=={'numerator':1,'denominator':1,'value':1.}
    assert result['attribution']['natural_root_cause_accuracy'] is None
    assert result['actual_costs']['inspect_seconds']['unknown_records']==1
    assert result['actual_costs']['executor_wall_seconds']['additive_total_claim'] is False


@pytest.mark.parametrize('guard',['execution_verified','measurement_complete','original_object_continuity_verified'])
def test_qor_gain_does_not_replace_missing_mechanism_evidence(guard):
    record,outcome,protocol=case()
    outcome['verification'][guard]=False
    row=evaluate_prediction(record,outcome,protocol)
    assert row['scores']['qor']['status']=='supported'
    assert row['scores']['mechanism']['status']=='not_evaluable'
    assert row['attribution']['status']=='unsupported_evidence'


def test_refutation_requires_evaluable_measurements_and_remains_independent_of_qor():
    record,outcome,protocol=case()
    outcome['mechanism_after']['timing_path_net_delay_ns']=3.
    outcome['verification']['mechanism_supported']=False
    row=evaluate_prediction(record,outcome,protocol)
    assert row['scores']['mechanism']['status']=='refuted'
    assert row['scores']['qor']['status']=='supported'
    assert row['attribution']['status']=='contradicted'


def test_partial_multi_metric_measurement_is_not_a_full_hit():
    record,outcome,protocol=case()
    record['prediction']['expected_physical_change']['metric_directions']['clock_skew_ns']='decrease'
    row=evaluate_prediction(record,outcome,protocol)
    assert row['scores']['mechanism']['status']=='not_evaluable'
    assert row['scores']['mechanism']['claims']['timing_path_net_delay_ns']['status']=='supported'


@pytest.mark.parametrize('missing',[None,float('nan'),float('inf'),True])
def test_missing_nonfinite_or_boolean_is_never_a_zero_measurement(missing):
    record,outcome,protocol=case()
    outcome['qor_after']['setup_wns_ns']=missing
    assert evaluate_prediction(record,outcome,protocol)['scores']['qor']['status']=='not_evaluable'


@pytest.mark.parametrize('state,expected',[('tool_failure','execution_failed'),('time_budget_exhausted','execution_failed'),
    ('exception_unknown','execution_unknown'),(None,'not_executed')])
def test_execution_failure_or_unknown_is_not_a_constraint_or_mechanism_refutation(state,expected):
    record,outcome,protocol=case()
    outcome['execution_status']=state
    row=evaluate_prediction(record,outcome,protocol)
    assert all(score['status']==expected for score in row['scores'].values())
    assert row['attribution']['status']=='unsupported_evidence'


@pytest.mark.parametrize('change,direction,expected',[(.0005,'unchanged','supported'),(.002,'unchanged','refuted'),
    (-.0005,'nondecrease','supported'),(-.002,'nondecrease','refuted'),(-.02,-1.,'supported'),(.02,True,'not_evaluable')])
def test_frozen_units_tolerance_and_sign_only_native_directions(change,direction,expected):
    record,outcome,protocol=case()
    record['prediction']['expected_qor']['metric_directions']['setup_wns_ns']=direction
    outcome['qor_after']['setup_wns_ns']=outcome['qor_before']['setup_wns_ns']+change
    assert evaluate_prediction(record,outcome,protocol)['scores']['qor']['status']==expected


def test_abstention_remains_in_full_denominator_without_zero_accuracy():
    record,outcome,protocol=case()
    hit=evaluate_prediction(record,outcome,protocol)
    for name in ('expected_qor','expected_physical_change','constraint_risk'):
        record['prediction'][name]={'prediction':'abstain','reason':'unknown'}
    outcome['post_attribution']={}
    abstention=evaluate_prediction(record,outcome,protocol)
    result=summarize_evaluations([hit,abstention])
    assert result['mechanism']['evaluable_coverage']['value']==.5
    assert result['mechanism']['conditional_accuracy']['value']==1.
    assert result['mechanism']['explicit_abstentions']==1
    alone=summarize_evaluations([abstention])
    assert alone['mechanism']['conditional_accuracy']['value'] is None
    assert alone['attribution']['wrong_or_unsupported_over_assertions']['value'] is None


def test_prose_is_not_judged_with_knowledge_of_outcome():
    record,outcome,protocol=case()
    record['prediction']['expected_qor']={'setup_wns':'within 0.001ns of source'}
    assert evaluate_prediction(record,outcome,protocol)['scores']['qor']['status']=='unstructured'


def test_source_incomplete_retains_abstention_and_coverage_failure_separately():
    record,outcome,protocol=case()
    record['prediction']['source_evidence_complete']=False
    record['prediction']['expected_qor']={'prediction':'abstain'}
    row=evaluate_prediction(record,outcome,protocol)
    assert row['scores']['qor']['status']=='source_incomplete'
    assert summarize_evaluations([row])['qor']['explicit_abstentions']==1


def test_legacy_record_cannot_receive_a_retrospective_scoring_rubric():
    record,outcome,protocol=case()
    del record['binding']['evaluation_protocol_sha256']
    row=evaluate_prediction(record,outcome,protocol)
    assert row['status']=='legacy_unscored'
    assert summarize_evaluations([row])['risk']['conditional_accuracy']['value'] is None


@pytest.mark.parametrize('key',['source_fingerprint','effective_signature','evaluation_protocol_sha256'])
def test_outcome_identity_must_match_prediction(key):
    record,outcome,protocol=case()
    outcome[key]='d'*64
    with pytest.raises(ValueError,match='identity mismatch'): evaluate_prediction(record,outcome,protocol)


def test_tolerance_cannot_be_changed_after_commit():
    record,outcome,protocol=case()
    protocol['metric_rules']['setup_wns_ns']['abs_tolerance']=100.
    with pytest.raises(ValueError,match='digest'): evaluate_prediction(record,outcome,protocol)


@pytest.mark.parametrize('spec',[None,{'axis':'qor','unit':'s','abs_tolerance':.001},
    {'axis':'qor','unit':'ns','abs_tolerance':float('nan')},{'axis':'qor','unit':'ns','abs_tolerance':True}])
def test_protocol_requires_registered_units_and_finite_tolerances(spec):
    protocol=default_protocol()
    protocol['metric_rules']['setup_wns_ns']=spec
    with pytest.raises(ValueError): validate_protocol(protocol)


def test_physical_risk_not_action_admission_and_not_engineering_gate():
    record,outcome,protocol=case()
    outcome['strict_gate']['accepted']=False
    outcome['strict_gate']['checks']['action_execution_verified']=False
    assert evaluate_prediction(record,outcome,protocol)['scores']['risk']['status']=='supported'
    outcome['strict_gate']['mode']='engineering_seed'
    assert evaluate_prediction(record,outcome,protocol)['scores']['risk']['status']=='not_evaluable'


def test_fail_closed_gate_without_measurements_is_not_a_risk_label():
    record,outcome,protocol=case()
    del outcome['strict_gate']['violation_metrics']['hold_wns_ns']
    outcome['strict_gate']['checks']['hold_clean']=False
    assert evaluate_prediction(record,outcome,protocol)['scores']['risk']['status']=='not_evaluable'


def test_inconsistent_report_frame_is_not_scored_as_risk_hit():
    record,outcome,protocol=case()
    outcome['strict_gate']['violation_metrics']['setup_wns_ns']=-1.
    assert evaluate_prediction(record,outcome,protocol)['scores']['risk']['status']=='not_evaluable'


def test_unknown_cost_is_json_safe_and_not_a_measured_zero():
    record,outcome,protocol=case()
    outcome['actual_costs']['inspect_seconds']=float('inf')
    row=evaluate_prediction(record,outcome,protocol)
    assert row['actual_costs']['inspect_seconds'] is None
    json.dumps(row,allow_nan=False)
    assert summarize_evaluations([row])['actual_costs']['inspect_seconds']['known_records']==0


def test_root_truth_not_invented_and_unsupported_vs_contradicted_separated():
    record,outcome,protocol=case()
    outcome['post_attribution']['kind']='natural_root_cause'
    root=evaluate_prediction(record,outcome,protocol)
    outcome['post_attribution']['kind']='bounded_mechanism'
    outcome['verification']['mechanism_supported']=False
    contradicted=evaluate_prediction(record,outcome,protocol)
    result=summarize_evaluations([root,contradicted])
    assert result['attribution']['insufficient_evidence_strong_assertions']==1
    assert result['attribution']['contradicted_strong_assertions']==1


def test_different_methods_splits_and_rubrics_are_not_pooled():
    record,outcome,protocol=case()
    first=evaluate_prediction(record,outcome,protocol)
    second=deepcopy(first)
    second['design_split']='held_out'
    result=summarize_evaluations([first,second])
    assert result['pooled_accuracy'] is None and len(result['groups'])==2


def test_model_and_head_identity_prevent_pooling():
    record,outcome,protocol=case()
    first=evaluate_prediction(record,outcome,protocol)
    record['binding']['forecast_role']='common_head'
    record['binding']['prediction_model_identity']={'sha256':'d'*64}
    second=evaluate_prediction(record,outcome,protocol)
    assert len(summarize_evaluations([first,second])['groups'])==2


def test_engineering_template_observations_do_not_inflate_native_accuracy():
    record,outcome,protocol=case()
    record['binding']['forecast_role']='engineering_template'
    row=evaluate_prediction(record,outcome,protocol)
    assert row['scores']['qor']['status']=='engineering_only'
    assert row['scores']['qor']['engineering_observation']['status']=='supported'
    assert summarize_evaluations([row])['qor']['conditional_accuracy']['value'] is None
