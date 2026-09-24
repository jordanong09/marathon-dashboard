"""Latest registration upload, reduced to the columns the app uses and shared with every user.

Only one snapshot is kept: each upload replaces it. Local JSON is for development; deployments use
the server-only Supabase functions in supabase_setup.sql.
"""
from __future__ import annotations

import base64
import gzip
import io
import json
import os
import uuid
from datetime import datetime, timezone

import pandas as pd

import doc_store
import sales_backend

GROUP_PREFIX = 'GROUP_REGISTRATION'


def minimize(frame, columns, group_column=None):
    """Keep only the selected source columns; drop coordinator names after ' - ' in group registrations."""
    keep = [column for column in dict.fromkeys(columns) if column and column in frame.columns]
    reduced = frame[keep].copy()
    if group_column in reduced:
        text = reduced[group_column].astype('string')
        is_group = text.str.upper().str.startswith(GROUP_PREFIX, na=False).to_numpy(dtype=bool)
        reduced[group_column] = reduced[group_column].astype(object)
        reduced.loc[is_group, group_column] = text[is_group].str.split(' - ', n=1).str[0].str.rstrip().astype(object)
    return reduced


def encode(frame):
    return base64.b64encode(gzip.compress(frame.to_csv(index=False).encode('utf-8'))).decode('ascii')


def decode(content):
    return pd.read_csv(io.BytesIO(gzip.decompress(base64.b64decode(content))))


def _path():
    return doc_store.DATA_DIR / 'registration_snapshot.json'


def _checked(result, allow_none=True):
    if result is None and allow_none:
        return None
    if not isinstance(result, dict):
        raise ValueError('Supabase returned an unexpected registration snapshot. Nothing has been changed.')
    return result


def save(frame, file_name, selection=None):
    """Replace the stored snapshot; return its metadata (file_name, rows, columns, selection, uploaded_at).

    selection: {role: source column} chosen at upload (e.g. 'promo_code': 'Promo Code - Code'), reused on load.
    """
    meta = {'file_name': file_name, 'rows': int(len(frame)), 'columns': [str(c) for c in frame.columns],
        'selection': {role: column for role, column in (selection or {}).items() if column}}
    content = encode(frame)
    config = sales_backend.settings()
    if config.get('backend') == 'supabase':
        return _checked(sales_backend.call(config, 'marathon_snapshot_save', {'p_meta': meta, 'p_content': content}), allow_none=False)
    meta['uploaded_at'] = datetime.now(timezone.utc).isoformat()
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps({'meta': meta, 'content': content}), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return meta


def read_meta():
    """Metadata of the stored snapshot, or None when nothing is stored."""
    config = sales_backend.settings()
    if config.get('backend') == 'supabase':
        return _checked(sales_backend.call(config, 'marathon_snapshot_meta', {}))
    path = _path()
    return json.loads(path.read_text(encoding='utf-8'))['meta'] if path.exists() else None


def read():
    """(frame, metadata) of the stored snapshot, or None."""
    config = sales_backend.settings()
    if config.get('backend') == 'supabase':
        stored = _checked(sales_backend.call(config, 'marathon_snapshot_read', {}))
    else:
        path = _path()
        stored = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    if not stored:
        return None
    return decode(stored['content']), stored['meta']


def delete():
    config = sales_backend.settings()
    if config.get('backend') == 'supabase':
        sales_backend.call(config, 'marathon_snapshot_delete', {})
    else:
        _path().unlink(missing_ok=True)
