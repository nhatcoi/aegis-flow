import io
import json
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor

from atpm.engine import initial_state
from atpm.generation import archive, generate, load_machine
from atpm.testing import exercise

TRUSTED = {'provider_verified': True, 'amount_matches': True, 'currency_matches': True}


def test_generated_zip_runs_without_project_imports(spec, tmp_path):
    artifact = generate(spec)
    with zipfile.ZipFile(io.BytesIO(archive(artifact))) as bundle:
        bundle.extractall(tmp_path)
    runner = ('import sys, unittest; sys.path.insert(0, "."); '
              'suite=unittest.defaultTestLoader.discover("."); '
              'result=unittest.TextTestRunner().run(suite); sys.exit(not result.wasSuccessful())')
    completed = subprocess.run([sys.executable, '-I', '-c', runner],
                               cwd=tmp_path, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert 'OK' in completed.stderr


def test_spec_text_is_data_not_executable_code(spec, tmp_path):
    marker = tmp_path / 'injected'
    spec['description'] = f'"""; __import__("pathlib").Path({str(marker)!r}).touch(); #'
    machine = load_machine(generate(spec))
    assert machine['SPEC']['description'] == spec['description']
    assert not marker.exists()


def test_monitor_enforcement_and_observation(unsafe):
    machine = load_machine(generate(unsafe))
    enforcing = machine['new_monitor']()
    blocked = enforcing.process('1', 'ship')
    assert blocked['verdict'] == 'BLOCKED'
    assert enforcing.state == initial_state(unsafe)
    observing = machine['new_monitor']()
    observed = observing.process('1', 'ship', enforce=False)
    assert observed['verdict'] == 'VIOLATED'
    assert observing.state['shipped']


def test_deduplication_and_conflicting_event_ids(spec):
    monitor = load_machine(generate(spec))['new_monitor']()
    monitor.process('start', 'start')
    assert monitor.process('capture', 'confirm', TRUSTED)['verdict'] == 'ACCEPTED'
    assert monitor.process('capture', 'confirm', TRUSTED)['verdict'] == 'DUPLICATE'
    assert monitor.process('capture', 'ship')['verdict'] == 'REJECTED'
    assert monitor.state['captured_count'] == 1
    assert not monitor.state['shipped']


def test_payment_scenarios_pass_safe_fail_unsafe(spec, unsafe):
    # unsafe fixture shares spec instance, so restore strict shipping for the safe case.
    safe = json.loads(json.dumps(spec))
    shipping = next(t for t in safe['transitions'] if t['event'] == 'ship')
    shipping['from_states'] = ['SUCCEEDED']
    shipping['guard'] = '$capture_verified'
    # Refund scenarios report SKIP on the basic model, which is not a defect.
    assert not any(t['verdict'] == 'FAIL' for t in exercise(safe)['results'])
    assert any(t['verdict'] == 'FAIL' for t in exercise(unsafe)['results'])


def test_spec_save_conflict_and_invalid_payload(client):
    current = client.get('/api/spec').json()
    spec = current['spec']
    spec['name'] = 'Version two'
    saved = client.put('/api/spec', json={'spec': spec, 'expected_hash': current['spec_hash']})
    assert saved.status_code == 200
    assert client.put('/api/spec', json={'spec': spec, 'expected_hash': current['spec_hash']}).status_code == 409
    spec['transitions'][0]['guard'] = {'eq': ['$unknown', True]}
    assert client.post('/api/verify', json={'spec': spec}).status_code == 422


def test_run_is_versioned_persistent_and_atomic(client, spec):
    run = client.post('/api/runs', json={'spec': spec}).json()
    def send(event, event_id, inputs=None):
        return client.post(f'/api/runs/{run["id"]}/events', json={
            'event': event, 'event_id': event_id, 'inputs': inputs or {}})
    send('start', '1')
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: send('confirm', '2', TRUSTED), range(2)))
    assert all(response.status_code == 200 for response in responses)
    stored = client.get(f'/api/runs/{run["id"]}').json()
    assert stored['state']['captured_count'] == 1
    assert sorted(e['verdict'] for e in stored['events'][1:]) == ['ACCEPTED', 'DUPLICATE']
    current = client.get('/api/spec').json()
    current['spec']['variables']['shipped']['initial'] = True
    client.put('/api/spec', json={'spec': current['spec'], 'expected_hash': current['spec_hash']})
    after = send('ship', '3').json()
    assert after['spec_hash'] == run['spec_hash']
    assert after['state']['shipped']
    # Restore a fresh monitor from the persisted state and event IDs each request.
    assert send('confirm', '2', TRUSTED).json()['events'][-1]['verdict'] == 'DUPLICATE'


def test_api_surface_and_cross_origin_guard(client, spec):
    assert client.get('/api/health').json()['status'] == 'ok'
    assert client.get('/api/examples/missing').status_code == 404
    assert client.get('/api/runs/missing').status_code == 404
    assert client.post('/api/verify', json={'spec': spec, 'bound': 31}).status_code == 422
    assert client.post('/api/verify', json={'spec': spec}, headers={'origin': 'https://example.com'}).status_code == 403
    for route in ['/graph', '/verify', '/generate', '/tests', '/advisory']:
        result = client.post('/api' + route, json={'spec': spec})
        assert result.status_code == 200, result.text
        assert result.json()['spec_hash']
    downloaded = client.post('/api/download', json={'spec': spec})
    assert downloaded.headers['content-type'] == 'application/zip'
    with zipfile.ZipFile(io.BytesIO(downloaded.content)) as bundle:
        assert 'payment_machine.py' in bundle.namelist()


def test_dev_origin_allowlist_follows_the_configured_ui_port(client, spec, monkeypatch):
    blocked = client.post('/api/graph', json={'spec': spec}, headers={'origin': 'http://localhost:4173'})
    assert blocked.status_code == 403

    monkeypatch.setenv('ATPM_UI_PORT', '4173')
    for origin in ('http://localhost:4173', 'http://127.0.0.1:4173'):
        assert client.post('/api/graph', json={'spec': spec}, headers={'origin': origin}).status_code == 200
    assert client.post('/api/graph', json={'spec': spec},
                       headers={'origin': 'http://localhost:5173'}).status_code == 403

    monkeypatch.setenv('ATPM_UI_ORIGINS', 'http://localhost:3000/, https://lab.example.com')
    assert client.post('/api/graph', json={'spec': spec},
                       headers={'origin': 'http://localhost:3000'}).status_code == 200
    assert client.post('/api/graph', json={'spec': spec},
                       headers={'origin': 'https://lab.example.com'}).status_code == 200
    # An explicit list replaces the port rule instead of extending it.
    assert client.post('/api/graph', json={'spec': spec},
                       headers={'origin': 'http://localhost:4173'}).status_code == 403


def test_refund_example_is_served_and_verifies(client):
    spec = client.get('/api/examples/refund').json()['spec']
    assert any(t['event'] == 'refund_full' for t in spec['transitions'])
    checked = client.post('/api/verify', json={'spec': spec, 'bound': 8})
    assert checked.status_code == 200, checked.text
    assert {result['verdict'] for result in checked.json()['results']} == {'BOUNDED_SAFE'}
    advisory = client.post('/api/advisory', json={'spec': spec}).json()
    by_id = {item['id']: item['status'] for item in advisory['items']}
    assert by_id['refund_coverage'] == 'MODELED'


def test_advisory_endpoint_accepts_checker_and_test_results(client, spec):
    verification = client.post('/api/verify', json={'spec': spec, 'bound': 4}).json()
    tests = client.post('/api/tests', json={'spec': spec}).json()
    report = client.post('/api/advisory',
                         json={'spec': spec, 'verification': verification, 'tests': tests})
    assert report.status_code == 200, report.text
    body = report.json()
    assert body['items'] and body['severity_counts']['critical'] > 0
    # A clean run must not manufacture verification or test findings.
    assert 'verification_violated' not in {item['id'] for item in body['items']}
