import pandas as pd
import pytest

import registration_snapshot
import sales_backend

FRAME = pd.DataFrame({
    'Registration Date': ['01/09/2026 10:00', '02/09/2026 11:00', '03/09/2026 12:00'],
    'Full Name': ['Tan Ah Kow', 'Lim Mei Ling', 'Raj Kumar'],
    'Email': ['a@x.com', 'b@x.com', 'c@x.com'],
    'Category Name': ['5km Fun Run', 'BYD Marathon (42.195KM)', 'Standard Chartered 10km'],
    'Current Age': [34, 28, 41],
    'Group/Corporate Name': ['GROUP_REGISTRATION_SCB Batch 1 - Tan, Hui Hoon', 'COMPLIMENTARY_KOL', None],
    'Promo Code - Code': ['', 'EARLY10', ''],
})
USED = ['Registration Date', 'Category Name', 'Current Age', 'Group/Corporate Name', 'Promo Code - Code', None, 'Missing column']


def test_minimize_keeps_only_used_columns_and_drops_coordinator_names():
    reduced = registration_snapshot.minimize(FRAME, USED, 'Group/Corporate Name')
    assert list(reduced.columns) == ['Registration Date', 'Category Name', 'Current Age', 'Group/Corporate Name', 'Promo Code - Code']
    assert reduced['Group/Corporate Name'].tolist()[:2] == ['GROUP_REGISTRATION_SCB Batch 1', 'COMPLIMENTARY_KOL']
    assert pd.isna(reduced['Group/Corporate Name'].iloc[2])
    assert 'Tan' not in reduced.to_csv()


def test_encode_decode_round_trip():
    reduced = registration_snapshot.minimize(FRAME, USED, 'Group/Corporate Name')
    restored = registration_snapshot.decode(registration_snapshot.encode(reduced))
    assert restored['Current Age'].tolist() == [34, 28, 41]
    assert restored['Registration Date'].tolist() == reduced['Registration Date'].tolist()


def test_local_save_read_and_delete(local_store):
    assert registration_snapshot.read_meta() is None
    reduced = registration_snapshot.minimize(FRAME, USED, 'Group/Corporate Name')
    meta = registration_snapshot.save(reduced, 'registrations.csv', {'category': 'Category Name', 'age': None})
    assert meta['rows'] == 3 and meta['file_name'] == 'registrations.csv' and meta['uploaded_at']
    assert meta['selection'] == {'category': 'Category Name'}
    assert registration_snapshot.read_meta() == meta
    frame, stored = registration_snapshot.read()
    assert stored == meta and frame.shape == (3, 5)
    registration_snapshot.delete()
    assert registration_snapshot.read_meta() is None and registration_snapshot.read() is None


def test_supabase_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(sales_backend, 'settings', lambda: {'backend': 'supabase', 'url': 'u', 'secret_key': 'k'})

    def fake_call(config, function, payload):
        calls.append((function, payload))
        if function == 'marathon_snapshot_save':
            return payload['p_meta'] | {'uploaded_at': '2026-09-25T01:12:00+00:00'}
        if function == 'marathon_snapshot_read':
            return {'meta': {'rows': 1, 'uploaded_at': 't'}, 'content': registration_snapshot.encode(pd.DataFrame({'A': [1]}))}
        return None

    monkeypatch.setattr(sales_backend, 'call', fake_call)
    meta = registration_snapshot.save(pd.DataFrame({'A': [1, 2]}), 'f.csv')
    assert meta['uploaded_at'] == '2026-09-25T01:12:00+00:00' and calls[0][1]['p_meta']['rows'] == 2
    frame, stored = registration_snapshot.read()
    assert frame['A'].tolist() == [1] and stored['rows'] == 1
    assert registration_snapshot.read_meta() is None
    registration_snapshot.delete()
    assert [name for name, _ in calls] == ['marathon_snapshot_save', 'marathon_snapshot_read', 'marathon_snapshot_meta', 'marathon_snapshot_delete']


def test_supabase_bad_response(monkeypatch):
    monkeypatch.setattr(sales_backend, 'settings', lambda: {'backend': 'supabase'})
    monkeypatch.setattr(sales_backend, 'call', lambda *a: ['nope'])
    with pytest.raises(ValueError, match='unexpected'):
        registration_snapshot.read_meta()
