import pytest

import sales_backend


def test_require_supabase_blocks_local(monkeypatch):
    monkeypatch.setattr(sales_backend.st, 'secrets', {'sales_storage': {'backend': 'local', 'require_supabase': True}})
    with pytest.raises(ValueError, match='must store records in Supabase'):
        sales_backend.settings()


def test_local_default(monkeypatch):
    monkeypatch.setattr(sales_backend.st, 'secrets', {})
    assert sales_backend.settings()['backend'] == 'local'
