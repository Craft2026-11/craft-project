"""Evaluator-only forecast scoring. Unknown evidence is never a negative label.

Scoring rules and units must be bound BEFORE execution. Natural-language
forecasts and old records without that binding are retained, not reinterpreted
by a judge with access to outcomes. No EDA or planner callback exists here.
"""
from collections import Counter
from copy import deepcopy
import math

from ._json import digest

VERSION='prediction-reliability-v1'
DIRECTIONS=('increase','decrease','unchanged','nondecrease','nonincrease')


def default_protocol():
    rules={}
    for name in ('setup_wns_ns','setup_tns_ns','hold_wns_ns','hold_tns_ns'):
        rules[name]={'axis':'qor','unit':'ns','abs_tolerance':.001}
    for name in ('setup_violating_paths','hold_violating_paths','route_drc'):
        rules[name]={'axis':'qor','unit':'count','abs_tolerance':0.}
    for name,unit,tolerance in (('cell_area','um^2',.001),('power_mw','mW',1e-6),('leakage_power_mw','mW',1e-9)):
        rules[name]={'axis':'qor','unit':unit,'abs_tolerance':tolerance}
    for name in ('timing_path_net_delay_ns','timing_path_cell_delay_ns','timing_path_data_delay_ns','timing_path_total_delay_ns','clock_skew_ns'):
        rules[name]={'axis':'mechanism','unit':'ns','abs_tolerance':.001}
    rules['density_unevenness_ratio_pct']={'axis':'mechanism','unit':'percent','abs_tolerance':.01}
    rules['density_bins_over_threshold_pct']={'axis':'mechanism','unit':'percent','abs_tolerance':.01}
    rules['original_hold_mean_data_increment_ns']={'axis':'mechanism','unit':'ns','abs_tolerance':.001}
    return {'schema_version':1,'version':VERSION,'metric_rules':rules,'directions':list(DIRECTIONS),
        'numeric_directions':'Finite numeric values encode sign only; zero encodes unchanged, not calibrated magnitude',
        'risk_target':'post_action_setup_hold_drc_violation; completed flow, three physical strict checks and finite WNS/TNS/path-count/DRC measurements required',
        'mechanism_guard':'execution verified AND complete mechanism measurement AND original-object continuity verified AND target response measured',
        'claim_aggregation':'All declared claims must be evaluable; all must match to support a multi-metric forecast',
        'denominators':'All prospective interventions retained; accuracy conditional on evaluable assertions, not abstentions or failures',
        'root_truth':'No independent natural root-cause labels inferred from mechanism or QoR'}


def explicit_net_protocol():
    """Prospective opt-in; the historical v1 protocol and its hash stay fixed."""
    value=default_protocol()
    value['version']='prediction-reliability-explicit-net-v2'
    value['metric_rules']['timing_path_data_segment_net_delay_ns']={
        'axis':'mechanism','unit':'ns','abs_tolerance':.001}
    return value


def validate_protocol(protocol):
    baseline=(explicit_net_protocol() if isinstance(protocol,dict) and
              protocol.get('version')=='prediction-reliability-explicit-net-v2' else default_protocol())
    if not isinstance(protocol,dict) or set(protocol)!=set(baseline):
        raise ValueError('Complete frozen prediction scoring protocol required')
    if any(protocol[key]!=baseline[key] for key in baseline if key!='metric_rules'):
        raise ValueError('Unknown prediction scoring semantics/version')
    rules=protocol['metric_rules']
    if not isinstance(rules,dict) or not rules:
        raise ValueError('Explicit registered metric rules required')
    for name,spec in rules.items():
        if (name not in baseline['metric_rules'] or not isinstance(spec,dict) or set(spec)!= {'axis','unit','abs_tolerance'}
                or any(spec[key]!=baseline['metric_rules'][name][key] for key in ('axis','unit'))
                or not finite(spec['abs_tolerance']) or spec['abs_tolerance']<0):
            raise ValueError('Invalid metric, unit or scoring tolerance: '+str(name))
    return deepcopy(protocol)


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def _direction(value):
    if isinstance(value,str) and value in DIRECTIONS: return value
    if finite(value): return 'increase' if value>0 else 'decrease' if value<0 else 'unchanged'
    return None


def _empty(status,reason): return {'status':status,'reason':reason,'claims':{}}


def _execution_unavailable(outcome):
    status=outcome.get('execution_status')
    if status in {'tool_failure','genus_stall','time_budget_exhausted','failed'}: return 'execution_failed'
    return 'not_executed' if status in (None,'not_attempted') else 'execution_unknown'


def _score_metrics(forecast,axis,outcome,protocol):
    if isinstance(forecast,dict) and forecast.get('prediction') in ('abstain','unknown'):
        return _empty('abstention','Explicit refusal retained in full denominator')
    if not isinstance(forecast,dict) or not isinstance(forecast.get('metric_directions'),dict) or not forecast['metric_directions']:
        return _empty('unstructured','No structured directional assertions; do not infer directions from prose')
    if outcome.get('execution_status')!='completed':
        return _empty(_execution_unavailable(outcome),'No completed physical outcome')
    if axis=='mechanism':
        verified=outcome.get('verification',{})
        if not all(verified.get(key) is True for key in
                   ('execution_verified','measurement_complete','original_object_continuity_verified')) or type(verified.get('intervention_observed')) is not bool:
            return _empty('not_evaluable','Missing execution/measurement/original-object continuity evidence')
    before=outcome.get(axis+'_before',{})
    after=outcome.get(axis+'_after',{})
    claims={}
    for metric,expected in forecast['metric_directions'].items():
        spec=protocol['metric_rules'].get(metric)
        direction=_direction(expected)
        if not spec or spec['axis']!=axis or direction is None:
            claims[metric]={'status':'not_evaluable','reason':'Unregistered metric/axis or invalid direction'}
            continue
        old,new=before.get(metric),after.get(metric)
        if not finite(old) or not finite(new):
            claims[metric]={'status':'not_evaluable','reason':'Missing finite paired measurement'}
            continue
        change=new-old
        if not finite(change):
            claims[metric]={'status':'not_evaluable','reason':'Nonfinite measurement delta'}
            continue
        tolerance=spec['abs_tolerance']
        hit={'increase':change>tolerance,'decrease':change < -tolerance,'unchanged':abs(change)<=tolerance,
             'nondecrease':change>=-tolerance,'nonincrease':change<=tolerance}[direction]
        claims[metric]={'status':'supported' if hit else 'refuted','expected_direction':direction,
            'before':old,'after':new,'delta':change,'unit':spec['unit'],'abs_tolerance':tolerance}
    statuses=[row['status'] for row in claims.values()]
    status='not_evaluable' if 'not_evaluable' in statuses else 'refuted' if 'refuted' in statuses else 'supported'
    return {'status':status,'claims':claims,'reason':'Frozen all-claims rule; per-metric refutations retained even when overall coverage is incomplete'}


def _score_risk(forecast,outcome):
    value=forecast.get('prediction') if isinstance(forecast,dict) else None
    if value in ('abstain','unknown'): return _empty('abstention','Explicit constraint-risk abstention')
    if value not in ('risk','no_risk'):
        return _empty('unstructured','No risk/no_risk forecast for the frozen physical-strict target')
    if outcome.get('execution_status')!='completed':
        return _empty(_execution_unavailable(outcome),'Tool failure is not a measured constraint violation')
    gate=outcome.get('strict_gate',{})
    checks=gate.get('checks',{})
    physical=[checks.get(key) for key in ('setup_clean','hold_clean','drc_clean')]
    if gate.get('mode')!='strict' or checks.get('flow_complete') is not True or not all(type(item) is bool for item in physical):
        return _empty('not_evaluable','All physical strict checks must be measured independently of action admission')
    metrics=gate.get('violation_metrics',{})
    required=('setup_wns_ns','setup_tns_ns','setup_violating_paths','hold_wns_ns','hold_tns_ns','hold_violating_paths','route_drc')
    if not all(finite(metrics.get(key)) for key in required):
        return _empty('not_evaluable','Missing finite physical constraint measurements; fail-closed gate is not a failure label')
    for key in ('setup_violating_paths','hold_violating_paths','route_drc'):
        if metrics[key]<0 or not float(metrics[key]).is_integer():
            return _empty('not_evaluable','Invalid physical violation count')
    measured=[all(metrics[key]>=0 for key in (prefix+'_wns_ns',prefix+'_tns_ns')) and metrics[prefix+'_violating_paths']==0
        for prefix in ('setup','hold')]+[metrics['route_drc']==0]
    if measured!=physical or any(key in outcome.get('qor_after',{}) and outcome['qor_after'][key]!=metrics[key] for key in required):
        return _empty('not_evaluable','Strict checks and scalar measurements do not share a consistent report frame')
    actual='no_risk' if all(physical) else 'risk'
    return {'status':'supported' if value==actual else 'refuted','predicted':value,'actual':actual,
        'reason':'Post-action physical constraint violation only; no QoR or root-cause inference'}


def _score_attribution(outcome):
    claim=outcome.get('post_attribution',{})
    if claim.get('asserted') is False: return {'status':'refused','strong_assertion':False}
    if claim.get('asserted') is not True: return {'status':'not_reported','strong_assertion':None}
    if outcome.get('execution_status')!='completed':
        return {'status':'unsupported_evidence','strong_assertion':True,'reason':'No completed physical execution'}
    if claim.get('kind')!='bounded_mechanism' or claim.get('prediction_identity_verified') is not True:
        return {'status':'unsupported_evidence','strong_assertion':True,'reason':'Root truth or prediction identity not independently established'}
    verified=outcome.get('verification',{})
    complete=all(verified.get(key) is True for key in
        ('execution_verified','measurement_complete','original_object_continuity_verified')) and type(verified.get('intervention_observed')) is bool
    if not complete or type(verified.get('mechanism_supported')) is not bool:
        return {'status':'unsupported_evidence','strong_assertion':True}
    if verified['mechanism_supported'] and verified['intervention_observed'] is not True:
        return {'status':'unsupported_evidence','strong_assertion':True,'reason':'A supported causal attribution requires a measured target response'}
    return {'status':'evidence_supported' if verified['mechanism_supported'] else 'contradicted','strong_assertion':True,
        'scope':'Bounded mechanism verification, never natural root-cause accuracy'}


def evaluate_prediction(record,outcome,protocol=None):
    binding=record.get('binding',{})
    base={'source_fingerprint':binding.get('source_fingerprint'),'effective_signature':binding.get('effective_signature'),
        'predictor_id':binding.get('predictor_id'),'design_split':binding.get('design_split'),
        'controller_version':binding.get('controller_version'),'memory_version':binding.get('memory_version'),
        'skill_version':binding.get('skill_version'),'evaluation_protocol_digest':binding.get('evaluation_protocol_digest'),
        'forecast_role':binding.get('forecast_role'),'model_identity_digest':digest(binding.get('prediction_model_identity')),
        'execution_status':outcome.get('execution_status'),
        'actual_costs':{key:value if finite(value) and value>=0 else None for key,value in outcome.get('actual_costs',{}).items()}}
    if not binding.get('evaluation_protocol_sha256') or protocol is None:
        return {**base,'status':'legacy_unscored','reason':'No prospectively bound scoring rubric; never backfill it',
            'scores':{axis:_empty('legacy_unscored','No precommitted rubric') for axis in ('mechanism','qor','risk')},
            'attribution':{'status':'legacy_unscored','strong_assertion':None}}
    protocol=validate_protocol(protocol)
    if binding.get('forecast_role') not in {'native','common_head','engineering_template'}:
        raise ValueError('Scored records require an explicit predictor/head role')
    if binding.get('evaluation_protocol_digest')!=digest(protocol):
        raise ValueError('Scoring rubric differs from committed protocol digest')
    for key in ('source_fingerprint','effective_signature','evaluation_protocol_sha256'):
        if outcome.get(key)!=binding.get(key): raise ValueError('Prediction/outcome identity mismatch: '+key)
    prediction=record['prediction']
    scores={'mechanism':_score_metrics(prediction['expected_physical_change'],'mechanism',outcome,protocol),
        'qor':_score_metrics(prediction['expected_qor'],'qor',outcome,protocol),
        'risk':_score_risk(prediction['constraint_risk'],outcome)}
    abstained={axis:score['status']=='abstention' for axis,score in scores.items()}
    if prediction.get('source_evidence_complete') is not True:
        scores={axis:_empty('source_incomplete','Incomplete pre-action source cannot support formal prediction accuracy') for axis in scores}
    elif binding.get('forecast_role')=='engineering_template':
        scores={axis:{**_empty('engineering_only','Engineering template is not a native/common-head accuracy comparison'),
            'engineering_observation':score} for axis,score in scores.items()}
    for axis,score in scores.items(): score['forecast_abstained']=abstained[axis]
    return {**base,'status':'evaluated','protocol_version':protocol['version'],'scores':scores,
        'attribution':_score_attribution(outcome),'independent_root_cause_accuracy':None,
        'attribution_owner':outcome.get('post_attribution',{}).get('owner'),
        'axes':deepcopy(outcome.get('verification',{})),
        'scope':'Offline forecast/attribution accounting. Attribution covers explicitly linked controller claims, not unparsed LLM prose. No action ranking, memory update, or root-truth inference.'}


def _rate(numerator,denominator):
    return {'numerator':numerator,'denominator':denominator,'value':numerator/denominator if denominator else None}


def summarize_evaluations(rows):
    group_keys=('predictor_id','controller_version','memory_version','skill_version','design_split','evaluation_protocol_digest',
        'forecast_role','model_identity_digest')
    groups={}
    for row in rows:
        identity=tuple(row.get(key) for key in group_keys)
        groups.setdefault(identity,[]).append(row)
    if len(groups)>1:
        return {'interventions_in_full_denominator':len(rows),'pooled_accuracy':None,
            'groups':[{'identity':dict(zip(group_keys,key)),'summary':summarize_evaluations(value)} for key,value in groups.items()],
            'scope':'Do not pool distinct controller/split/scoring protocols into one claimed accuracy'}
    result={'interventions_in_full_denominator':len(rows),'record_status_counts':dict(Counter(row['status'] for row in rows)),
        'execution_status_counts':dict(Counter(row.get('execution_status') or 'unknown' for row in rows))}
    for axis in ('mechanism','qor','risk'):
        counts=Counter(row['scores'][axis]['status'] for row in rows)
        evaluated=counts['supported']+counts['refuted']
        result[axis]={'status_counts':dict(counts),'evaluable_coverage':_rate(evaluated,len(rows)),
            'explicit_abstentions':sum(row['scores'][axis].get('forecast_abstained') is True or row['scores'][axis]['status']=='abstention' for row in rows),
            'conditional_accuracy':_rate(counts['supported'],evaluated),
            'observed_hits_over_all_interventions':_rate(counts['supported'],len(rows))}
    counts=Counter(row['attribution']['status'] for row in rows)
    asserted=sum(row['attribution'].get('strong_assertion') is True for row in rows)
    invalid=counts['contradicted']+counts['unsupported_evidence']
    result['attribution']={'status_counts':dict(counts),'contradicted_strong_assertions':counts['contradicted'],
        'insufficient_evidence_strong_assertions':counts['unsupported_evidence'],
        'reported_attribution_coverage':_rate(sum(counts[key] for key in ('refused','evidence_supported','contradicted','unsupported_evidence')),len(rows)),
        'wrong_or_unsupported_over_assertions':_rate(invalid,asserted),'wrong_or_unsupported_over_all':_rate(invalid,len(rows)),
        'natural_root_cause_accuracy':None}
    keys=sorted({key for row in rows for key in row.get('actual_costs',{})})
    result['actual_costs']={key:{'known_sum_seconds':sum(row['actual_costs'][key] for row in rows
        if finite(row.get('actual_costs',{}).get(key)) and row['actual_costs'][key]>=0),
        'known_records':sum(finite(row.get('actual_costs',{}).get(key)) and row['actual_costs'][key]>=0 for row in rows),
        'unknown_records':sum(not finite(row.get('actual_costs',{}).get(key)) or row['actual_costs'][key]<0 for row in rows),
        'additive_total_claim':False} for key in keys}
    result['scope']='Full denominators retained. Costs have explicit overlapping scopes; unknown is not zero; no statistical independence claimed.'
    return result
