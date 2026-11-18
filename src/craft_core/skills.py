"""Allowlisted declarative skill edits; a proposed edit is not an approved policy."""
from copy import deepcopy
import hashlib
import json
import math

SCHEMA = 'craft-experience-skills-v1'
EVENTS = ('target', 'strict', 'regional')
PATCHES = {
    'require_delay_decomposition': ('diagnosis', 'delay_check', 'required'),
    'prioritize_counterevidence': ('diagnosis', 'counterevidence', 'first'),
    'timing_evidence_first': ('evidence', 'priority', 'timing_first'),
    'routing_evidence_first': ('evidence', 'priority', 'routing_first'),
    'expand_retrieval': ('evidence', 'retrieval_limit', 5),
    'shrink_forecast_quarter': ('prediction', 'history_weight', .25),
    'shrink_forecast_half': ('prediction', 'history_weight', .5),
    'require_more_prediction_support': ('prediction', 'minimum_support', 5),
}
for _event in EVENTS:
    PATCHES['shrink_event_'+_event]=('prediction',_event+'_history_weight',.25)

RULE_VALUES = {
    'diagnosis': {'delay_check': ('advisory', 'required'), 'counterevidence': ('report', 'first')},
    'evidence': {'priority': ('stage_first', 'timing_first', 'routing_first'), 'retrieval_limit': (3, 5)},
    'prediction': {'history_weight': (0., .25, .5), 'minimum_support': (3, 5)},
}
SCOPE_KEYS = ('design', 'design_fingerprint', 'technology', 'toolchain', 'constraints', 'evaluator', 'stage')
CAUSES = ('insufficient_evidence', 'diagnosis_mismatch_possible', 'cross_stage_omission_possible',
          'forecast_overconfidence', 'operator_mismatch_possible', 'supported_in_scope')



def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def seal(value):
    body = deepcopy(value); body.pop('sha256', None)
    return {**body, 'sha256': fingerprint(body)}


def unseal(value):
    body = deepcopy(value); signature = body.pop('sha256', None)
    if fingerprint(body) != signature:
        raise ValueError('Experience/skill integrity mismatch')
    return body


def validate_scope(scope):
    if set(scope) != set(SCOPE_KEYS) or any(not isinstance(v, str) or not v or v == 'unknown' for v in scope.values()):
        raise ValueError('Complete design/PDK/toolchain/constraint/evaluator scope required')


def compatible(a, b):
    validate_scope(a); validate_scope(b)
    return a == b


def validate_program(program):
    if set(program) != {'schema', 'version', 'parent', 'rules'} or program['schema'] != SCHEMA:
        raise ValueError('Exact skill program schema required')
    if type(program['version']) is not int or program['version'] < 1:
        raise ValueError('Invalid skill version')
    if program['parent'] is not None and (not isinstance(program['parent'], str) or len(program['parent']) != 64):
        raise ValueError('Invalid skill parent')
    if set(program['rules']) != set(RULE_VALUES): raise ValueError('Unknown skill')
    for skill, fields in RULE_VALUES.items():
        optional={e+'_history_weight' for e in EVENTS} if skill=='prediction' else set()
        actual=set(program['rules'][skill])
        if not set(fields)<=actual or actual-set(fields)-optional:raise ValueError('Unknown skill field')
        for key in actual & optional:
            if type(program['rules'][skill][key]) is not float or program['rules'][skill][key] not in (0.,.25,.5):raise ValueError('Invalid event weight')
        for k, allowed in fields.items():
            v = program['rules'][skill][k]
            if not any(type(v) is type(x) and v == x for x in allowed):
                raise ValueError('Skill patch outside typed allowlist')
    return deepcopy(program)


def mutate(program, patch):
    validate_program(program)
    if patch not in PATCHES: raise ValueError('Unknown bounded patch')
    s, k, v = PATCHES[patch]
    if program['rules'][s].get(k) == v: raise ValueError('No-op is not skill evolution')
    changed = deepcopy(program); changed['rules'][s][k] = v
    changed.update(parent=fingerprint(program), version=program['version']+1)
    return validate_program(changed)


def apply_forecast(program, raw, support):
    validate_program(program); settings=program['rules']['prediction']; result={}
    for event in EVENTS:
        p=raw.get(event); stat=support[event]
        if p is not None and (type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1):raise ValueError('Invalid forecast')
        w=settings.get(event+'_history_weight',settings['history_weight']) if stat['n']>=settings['minimum_support'] else 0.
        result[event]=(1-w)*p+w*stat['mean'] if p is not None else None
    return result


def score_forecasts(raw, labels):
    if set(raw)!=set(EVENTS):raise ValueError('All forecast events required')
    return {k:(raw[k]-int(labels[k]))**2 for k in EVENTS if type(labels.get(k)) is bool
            and type(raw.get(k)) in (int,float) and math.isfinite(raw[k]) and 0<=raw[k]<=1}


def default_program():
    """Return an independent initial program with no experience weighting."""
    return {'schema': 'craft-experience-skills-v1', 'version': 1, 'parent': None, 'rules': {'diagnosis': {'delay_check': 'advisory', 'counterevidence': 'report'}, 'evidence': {'priority': 'stage_first', 'retrieval_limit': 3}, 'prediction': {'history_weight': 0.0, 'minimum_support': 3}}}
