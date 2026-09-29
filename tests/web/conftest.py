import json
from pathlib import Path

import pytest
from atpm.main import app
from atpm.specification import Specification
from fastapi.testclient import TestClient


@pytest.fixture
def spec():
    return Specification.model_validate(json.loads(Path('specs/payment.json').read_text())).model_dump()


@pytest.fixture
def unsafe(spec):
    ship = next(t for t in spec['transitions'] if t['event'] == 'ship')
    ship['from_states'] = spec['variables']['status']['values']
    ship['guard'] = {'not': ['$shipped']}
    return spec


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('ATPM_DB', str(tmp_path / 'test.sqlite3'))
    with TestClient(app) as client:
        yield client
