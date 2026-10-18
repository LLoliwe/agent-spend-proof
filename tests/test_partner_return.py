"""Fraud/false-green checks for vendor-neutral partner evidence."""
import importlib.util
from pathlib import Path
import json
import subprocess
import sys

import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'pryntor-ops' / 'partner_return.py'
spec = importlib.util.spec_from_file_location('partner_return', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(mode='local_simulation', aligned=True):
    rows = []
    for provider in ('alpha', 'beta'):
        for trial in (1, 2):
            rows.append({
                'provider': provider, 'task_id': 'permissioned-read',
                'trial': trial if aligned or provider == 'alpha' else trial + 2,
                'mode': mode, 'outcome': 'success' if trial == 1 else 'failure',
                'latency_ms': 10 if trial == 1 else 20,
                'cost_usd': '0.00',
                'evidence_ref': 'fixture:synthetic-case' if mode != 'authorized_live' else 'sha256:independent-run-file'
            })
    return {'schema_version': 1, 'niche': 'agent-connection', 'environment': 'synthetic-python-311',
            'independent_reviewed': False, 'records': rows}


def test_synthetic_is_not_live_benchmark():
    result = module.analyse(fixture())
    assert result['comparability'] == 'SIMULATED_NOT_VENDOR_PERFORMANCE'
    assert result['public_claim_allowed'] is False
    assert result['provider_summaries'][0]['success_rate'] == .5


def test_mismatched_trials_not_comparable():
    assert module.analyse(fixture(aligned=False))['comparability'] == 'NOT_COMPARABLE_TASK_MISMATCH'


def test_live_requires_independent_review():
    result = module.analyse(fixture(mode='authorized_live'))
    assert result['comparability'] == 'MEASURED_AWAITING_INDEPENDENT_REVIEW'
    assert result['public_claim_allowed'] is False


def test_review_attestation_still_not_public_approval():
    data = fixture(mode='authorized_live')
    data['independent_reviewed'] = True
    result = module.analyse(data)
    assert result['comparability'] == 'REVIEWED_LIVE_ATTESTATION_ONLY'
    assert result['public_claim_allowed'] is False


def test_docs_only_never_reports_performance():
    data = fixture()
    for r in data['records']:
        r.update(mode='documentation_only', outcome='not_tested', latency_ms=None, cost_usd=None)
    result = module.analyse(data)
    assert result['comparability'] == 'DOCUMENTATION_ONLY_NOT_TESTED'
    assert all(row['success_rate'] is None for row in result['provider_summaries'])


@pytest.mark.parametrize('field,value', [('cost_usd','NaN'),('cost_usd','-1'),('cost_usd','USD 2'),
                                         ('latency_ms',-4),('latency_ms',float('inf')),
                                         ('trial',0),('trial',True),('mode','paid_unsanctioned')])
def test_bad_value_rejected(field,value):
    data = fixture()
    data['records'][0][field] = value
    with pytest.raises(module.InvalidEvidence): module.analyse(data)


def test_duplicate_trial_rejected():
    data = fixture()
    data['records'].append(data['records'][0].copy())
    with pytest.raises(module.InvalidEvidence,match='duplicate'):module.analyse(data)


def test_secret_field_rejected():
    data = fixture()
    data['records'][0]['api_key'] = 'do-not-include'
    with pytest.raises(module.InvalidEvidence,match='disallowed'):module.analyse(data)


def test_fake_live_fixture_rejected():
    data = fixture(mode='authorized_live')
    data['records'][0]['evidence_ref'] = 'fixture:not-live'
    with pytest.raises(module.InvalidEvidence,match='fixture'):module.analyse(data)


def test_missing_cost_does_not_fake_zero_cost():
    data = fixture()
    data['records'][0]['cost_usd'] = None
    result = module.analyse(data)
    assert result['provider_summaries'][0]['cost_per_success_usd'] is None


def test_invalid_documentation_measurement_rejected():
    data = fixture()
    data['records'][0]['mode'] = 'documentation_only'
    data['records'][0]['outcome'] = 'not_tested'
    with pytest.raises(module.InvalidEvidence): module.analyse(data)


def test_mixed_modes_not_comparable():
    data = fixture()
    for r in data['records'][2:]:
        r['mode']='authorized_live'; r['evidence_ref']='sha256:real-run'
    assert module.analyse(data)['comparability'] == 'NOT_COMPARABLE'


def test_cli_synthetic_output(tmp_path):
    input_path=tmp_path/'source.json'; output_path=tmp_path/'report.json'
    input_path.write_text(json.dumps(fixture()))
    result = subprocess.run([sys.executable,str(SOURCE),str(input_path),'--output',str(output_path)],capture_output=True,text=True)
    assert result.returncode == 0,result.stderr
    output=json.loads(output_path.read_text())
    assert output['public_claim_allowed'] is False


def test_cli_rejects_corrupt_data(tmp_path):
    input_path=tmp_path/'source.json'; input_path.write_text('not json')
    result=subprocess.run([sys.executable,str(SOURCE),str(input_path)],capture_output=True,text=True)
    assert result.returncode == 2
