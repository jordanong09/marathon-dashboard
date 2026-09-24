import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def local_store(tmp_path, monkeypatch):
    """Force local storage in a temporary folder."""
    import doc_store
    import sales_backend
    import streamlit as st
    monkeypatch.setattr(sales_backend, 'settings', lambda: {'backend': 'local'})
    monkeypatch.setattr(doc_store, 'DATA_DIR', tmp_path)
    st.cache_data.clear()  # the stored registration snapshot is cached per process
    yield tmp_path
    st.cache_data.clear()
