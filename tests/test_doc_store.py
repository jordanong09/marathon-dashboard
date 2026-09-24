import pytest

import doc_store
import sales_backend


def test_read_returns_seed(local_store):
    plan = doc_store.read('plan')
    assert plan['revision'] == 0 and plan['capacity']['Full Marathon'] == 13000
    assert doc_store.read('campaigns')['campaigns'] == []


def test_save_bumps_revision_and_rejects_stale(local_store):
    plan = doc_store.read('plan')
    plan['allocation']['Corporate']['5 km'] = 10
    saved = doc_store.save('plan', plan, 0, 'Plan saved')
    assert saved['revision'] == 1 and saved['history'][-1]['action'] == 'Plan saved'
    assert doc_store.read('plan')['allocation']['Corporate']['5 km'] == 10
    with pytest.raises(ValueError, match='changed in another session'):
        doc_store.save('plan', plan, 0, 'stale')


def test_plan_validation(local_store):
    plan = doc_store.read('plan')
    plan['capacity']['5 km'] = -1
    with pytest.raises(ValueError, match='Capacity for 5 km'):
        doc_store.save('plan', plan, 0, 'x')


def campaign(name, codes, **extra):
    return {'id': name, 'name': name, 'type': 'shared', 'codes': codes, 'cap': None, 'start': None, 'end': None, 'notes': ''} | extra


def test_campaign_code_clash_rejected(local_store):
    doc = doc_store.read('campaigns')
    doc['campaigns'] = [campaign('A', ['X1', 'X2']), campaign('B', ['X2'])]
    with pytest.raises(ValueError, match='1 code\\(s\\) already belong to another campaign: X2'):
        doc_store.save('campaigns', doc, 0, 'x')


def test_campaign_names_unique_and_dates_ordered(local_store):
    doc = doc_store.read('campaigns')
    doc['campaigns'] = [campaign('A', []), campaign('a', [])]
    with pytest.raises(ValueError, match='unique'):
        doc_store.save('campaigns', doc, 0, 'x')
    doc['campaigns'] = [campaign('A', [], start='2026-10-02', end='2026-10-01')]
    with pytest.raises(ValueError, match='end date'):
        doc_store.save('campaigns', doc, 0, 'x')


def test_complimentary_validation(local_store):
    doc = doc_store.read('complimentary')
    doc['programmes'] = [{'id': 'p1', 'name': 'KOL', 'tags': ['KOL'], 'notes': ''},
        {'id': 'p2', 'name': 'Media', 'tags': ['kol'], 'notes': ''}]
    with pytest.raises(ValueError, match='only one programme'):
        doc_store.save('complimentary', doc, 0, 'x')
    doc['programmes'] = doc['programmes'][:1]
    doc['issuances'] = [{'id': 'i1', 'programme_id': 'p1', 'date': '2026-09-01', 'recipient': 'KOLs',
        'quantities': {'5 km': 0}, 'notes': '', 'cancelled': False, 'cancel_reason': ''}]
    with pytest.raises(ValueError, match='at least one'):
        doc_store.save('complimentary', doc, 0, 'x')
    doc['issuances'][0]['quantities'] = {'5 km': 5}
    assert doc_store.save('complimentary', doc, 0, 'ok')['revision'] == 1


def test_supabase_read_and_save(monkeypatch):
    calls = []
    monkeypatch.setattr(sales_backend, 'settings', lambda: {'backend': 'supabase', 'url': 'u', 'secret_key': 'k'})

    def fake_call(config, function, payload):
        calls.append((function, payload))
        if function == 'marathon_doc_read':
            return {'schema_version': 1, 'revision': 3, 'history': []}
        return payload['p_data'] | {'revision': 4}

    monkeypatch.setattr(sales_backend, 'call', fake_call)
    doc = doc_store.read('plan')
    assert doc['revision'] == 3 and 'capacity' in doc
    assert doc_store.save('plan', doc, 3, 'x')['revision'] == 4
    assert calls[1][0] == 'marathon_doc_save' and calls[1][1]['p_expected_revision'] == 3


def test_supabase_bad_response(monkeypatch):
    monkeypatch.setattr(sales_backend, 'settings', lambda: {'backend': 'supabase'})
    monkeypatch.setattr(sales_backend, 'call', lambda *a: ['nope'])
    with pytest.raises(ValueError, match='unexpected record format'):
        doc_store.read('plan')
