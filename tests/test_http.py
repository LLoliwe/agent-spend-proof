from uuid import uuid4
from fastapi.testclient import TestClient
from proof.app import app

client = TestClient(app)

def test_http_health_flags_live_disabled():
    r = client.get('/api/health')
    assert r.status_code == 200
    assert r.json()['real_money_moved'] is False
    r = client.get('/api/policy')
    assert r.json()['live_enabled'] is False

def test_http_create_simulate_and_replay_block():
    p = {
        'task_id': 'http-smoke', 'merchant': 'https://data.example.org',
        'service': 'report', 'amount_cents': 50, 'currency': 'USD',
        'idempotency_key': 'http-'+uuid4().hex,
    }
    response = client.post('/api/intents', json=p)
    assert response.status_code == 201
    assert response.json()['status'] == 'approved'
    id_ = response.json()['id']
    replay = client.post('/api/intents', json=p)
    assert replay.json()['idempotent_replay'] is True
    assert replay.json()['id'] == id_
    settled = client.post(f'/api/intents/{id_}/simulate', json={'outcome': 'delivered'})
    assert settled.json()['tx_hash'].startswith('SIM-')
    double = client.post(f'/api/intents/{id_}/simulate', json={'outcome': 'delivered'})
    assert double.status_code == 409
