"""Append-only prospective prediction authorization for new real EDA arms.

No outcome input is accepted. A missing prediction may explicitly abstain,
but cannot be manufactured from execution results or silently scored as wrong.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

VERSION = 'prospective-prediction-v1'
PREDICTION_FIELDS = ('hypothesis', 'target', 'operator', 'expected_physical_change',
                     'expected_qor', 'constraint_risk', 'falsification_conditions')
BINDING_FIELDS = ('candidate_id', 'effective_signature', 'source_fingerprint',
                  'constraint_fingerprint', 'evidence_access_scope', 'predictor_id',
                  'design_split', 'controller_version', 'memory_version', 'skill_version')


def file_sha(path):
    fingerprint=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            fingerprint.update(chunk)
    return fingerprint.hexdigest()


def _json_copy(value):
    # Also rejects nonfinite sentinels rather than committing ambiguous JSON.
    return json.loads(json.dumps(value, allow_nan=False, sort_keys=True))


def validate_prediction(prediction, binding):
    prediction, binding = _json_copy(prediction), _json_copy(binding)
    if not isinstance(prediction, dict) or not isinstance(binding, dict):
        raise ValueError('Prediction and execution binding must be objects')
    if any(name not in prediction or prediction[name] in (None, '', [], {}) for name in PREDICTION_FIELDS):
        raise ValueError('All seven prospective prediction fields are required; explicit abstention with reason is allowed')
    for name in PREDICTION_FIELDS[:-1]:
        if not isinstance(prediction[name], (str, dict)) or not prediction[name]:
            raise ValueError('Prediction field must be nonempty text or a structured object: ' + name)
    if any(name not in binding for name in BINDING_FIELDS):
        raise ValueError('Prediction execution/evidence/version binding incomplete')
    for name in ('candidate_id', 'effective_signature', 'source_fingerprint', 'constraint_fingerprint',
                 'predictor_id', 'design_split', 'controller_version'):
        if not isinstance(binding[name], str) or not binding[name].strip():
            raise ValueError('Nonempty prediction binding required: ' + name)
    scope = binding['evidence_access_scope']
    if not isinstance(scope, list) or any(not isinstance(item, str) or not item.strip() for item in scope) or len(scope) != len(set(scope)):
        raise ValueError('Explicit unique evidence access scope required, possibly empty')
    if binding['design_split'] not in ('development', 'training', 'validation', 'held_out', 'engineering'):
        raise ValueError('Explicit recognized design split required')
    for name in ('memory_version', 'skill_version'):
        if binding[name] is not None and (not isinstance(binding[name], str) or not binding[name].strip()):
            raise ValueError('Memory/skill version must be explicit string or null')
    if not isinstance(prediction['falsification_conditions'], list) or not prediction['falsification_conditions'] or any(
            not isinstance(item, str) or not item.strip() for item in prediction['falsification_conditions']):
        raise ValueError('Nonempty falsification conditions must be strings')
    return prediction, binding


def _create(path, value):
    with Path(path).open('x') as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    return file_sha(path)


def commit_prediction(directory, *, prediction, binding):
    """Commit once into an existing fresh arm directory; never overwrite/resume."""
    directory = Path(directory)
    prediction, binding = validate_prediction(prediction, binding)
    if not directory.is_dir():
        raise ValueError('Prediction requires an existing isolated arm directory')
    for name in ('prediction_record.json', 'prediction_commit.json', 'execution_launch.json',
                 'outcome.json', 'implementation_result.json', 'craft_trial.json'):
        if (directory / name).exists():
            raise ValueError('Prediction/launch already exists; no retrospective replacement or automatic restart')
    if any(directory.glob('build_*/craft_run_manifest.json')):
        raise ValueError('An execution manifest already exists; cannot retroactively commit a prediction')
    record_hash = _create(directory / 'prediction_record.json', {
        'schema_version': 1, 'protocol_version': VERSION, 'prediction': prediction, 'binding': binding})
    commit_hash = _create(directory / 'prediction_commit.json', {
        'protocol_version': VERSION, 'prediction_record_sha256': record_hash,
        'committed_utc': datetime.now(timezone.utc).isoformat(),
        'commit_monotonic_ns': time.monotonic_ns()})
    return {'protocol_version': VERSION, 'prediction_record_sha256': record_hash,
            'prediction_commit_sha256': commit_hash}


def verify_prediction(directory, *, receipt, binding):
    return _verify_prediction(directory,receipt=receipt,binding=binding,current_boot=True)


def verify_prediction_archive(directory, *, receipt, binding):
    """Content/order audit only; never grants launch authority.

    Monotonic stamps can belong to an older boot or another host. Keep their
    original positive/order checks, but do not compare them with this boot.
    """
    return _verify_prediction(directory,receipt=receipt,binding=binding,current_boot=False)


def _verify_prediction(directory, *, receipt, binding, current_boot):
    directory = Path(directory)
    if receipt.get('protocol_version') != VERSION:
        raise ValueError('Prediction protocol version mismatch')
    for name, key in (('prediction_record.json', 'prediction_record_sha256'),
                      ('prediction_commit.json', 'prediction_commit_sha256')):
        if file_sha(directory / name) != receipt.get(key):
            raise ValueError('Prediction precommit hash mismatch: ' + name)
    record = json.loads((directory / 'prediction_record.json').read_text())
    commit = json.loads((directory / 'prediction_commit.json').read_text())
    _, committed_binding = validate_prediction(record['prediction'], record['binding'])
    if committed_binding != _json_copy(binding):
        raise ValueError('Candidate/source/evidence/version changed after prediction commitment')
    if (record.get('schema_version') != 1 or record.get('protocol_version') != VERSION or commit.get('protocol_version') != VERSION
            or commit.get('prediction_record_sha256') != receipt['prediction_record_sha256']):
        raise ValueError('Prediction record/commit identity mismatch')
    stamp = commit.get('commit_monotonic_ns')
    if type(stamp) is not int or stamp <= 0 or (current_boot and stamp > time.monotonic_ns()):
        raise ValueError('Invalid prospective prediction commit clock')
    launch_path = directory / 'execution_launch.json'
    if launch_path.exists():
        launch = json.loads(launch_path.read_text())
        if (any(launch.get(key) != value for key, value in receipt.items())
                or type(launch.get('launch_monotonic_ns')) is not int
                or launch['launch_monotonic_ns'] < stamp
                or (current_boot and launch['launch_monotonic_ns'] > time.monotonic_ns())):
            raise ValueError('Launch receipt does not follow its committed prediction')
    return record


def authorize_launch(directory, *, receipt, binding):
    """Must be called immediately before the EDA subprocess executor."""
    verify_prediction(directory, receipt=receipt, binding=binding)
    return _create(Path(directory) / 'execution_launch.json', {
        **receipt, 'launched_utc': datetime.now(timezone.utc).isoformat(),
        'launch_monotonic_ns': time.monotonic_ns()})
