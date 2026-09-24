"""Named planning documents (plan, complimentary, campaigns) with revision checks.

Local JSON is for development; deployments use Supabase RPCs (see supabase_setup.sql).
"""
from __future__ import annotations

import copy
import json
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import sales_backend
from planning.categories import DEFAULT_CAPACITY, GROUPS, PLANNING_CATEGORIES

DATA_DIR = Path(os.environ.get('MARATHON_DATA_DIR', Path(__file__).parent / 'planning_data'))
NAMES = ('plan', 'complimentary', 'campaigns')


def seed(name):
    base = {'schema_version': 1, 'revision': 0, 'history': []}
    if name == 'plan':
        return base | {'capacity': dict(DEFAULT_CAPACITY),
            'allocation': {group: {category: 0 for category in PLANNING_CATEGORIES} for group in GROUPS}}
    if name == 'complimentary':
        return base | {'programmes': [], 'issuances': []}
    if name == 'campaigns':
        return base | {'campaigns': []}
    raise ValueError(f'Unknown planning document: {name}')


def _merge(name, stored):
    if stored is None:
        return seed(name)
    if not isinstance(stored, dict) or stored.get('schema_version') != 1:
        raise ValueError('Supabase returned an unexpected record format. Saving has been stopped.')
    return seed(name) | stored


def _whole(value, label):
    if type(value) is not int or value < 0:
        raise ValueError(f'{label} must be a whole number of 0 or more.')


def _past_date(value, label):
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f'{label} must be a valid date.') from None
    if parsed > date.today():
        raise ValueError(f'{label} cannot be in the future.')


def _unique_names(items, label):
    names = [str(item.get('name', '')).strip().casefold() for item in items]
    if not all(names):
        raise ValueError(f'Every {label} needs a name.')
    if len(names) != len(set(names)):
        raise ValueError(f'{label.capitalize()} names must be unique.')


def validate(name, data):
    if data.get('schema_version') != 1 or not isinstance(data.get('history'), list):
        raise ValueError('Unsupported planning document format.')
    if name == 'plan':
        for category in PLANNING_CATEGORIES:
            _whole(data['capacity'].get(category), f'Capacity for {category}')
        for group in GROUPS:
            for category in PLANNING_CATEGORIES:
                _whole(data['allocation'].get(group, {}).get(category), f'{group} · {category}')
    elif name == 'complimentary':
        _unique_names(data['programmes'], 'programme')
        tags = [tag.casefold() for programme in data['programmes'] for tag in programme['tags']]
        if len(tags) != len(set(tags)):
            raise ValueError('A registration tag can be linked to only one programme.')
        ids = {programme['id'] for programme in data['programmes']}
        for item in data['issuances']:
            if item['programme_id'] not in ids:
                raise ValueError('An issuance refers to a programme that no longer exists.')
            _past_date(item['date'], 'Issue date')
            for category, value in item['quantities'].items():
                _whole(value, f'Issued places for {category}')
            if sum(item['quantities'].values()) <= 0:
                raise ValueError('Enter at least one issued place.')
            if item.get('cancelled') and not str(item.get('cancel_reason', '')).strip():
                raise ValueError('Enter a reason when cancelling an issuance.')
    elif name == 'campaigns':
        _unique_names(data['campaigns'], 'campaign')
        owner, clashes = {}, set()
        for campaign in data['campaigns']:
            if campaign['type'] not in ('shared', 'unique'):
                raise ValueError('Campaign type must be shared or unique.')
            if campaign.get('cap') is not None:
                _whole(campaign['cap'], 'Campaign cap')
            if campaign.get('start') and campaign.get('end') and campaign['start'] > campaign['end']:
                raise ValueError(f"{campaign['name']}: the end date must be on or after the start date.")
            for code in campaign['codes']:
                if not isinstance(code, str) or not code.strip():
                    raise ValueError('Promo codes cannot be blank.')
                if owner.get(code, campaign['name']) != campaign['name']:
                    clashes.add(code)
                owner[code] = campaign['name']
        if clashes:
            shown = ', '.join(sorted(clashes)[:10])
            raise ValueError(f'{len(clashes)} code(s) already belong to another campaign: {shown}')
    else:
        raise ValueError(f'Unknown planning document: {name}')


def _path(name, folder):
    return Path(folder) / f'{name}.json'


def _read_local(name, path):
    return _merge(name, json.loads(path.read_text(encoding='utf-8')) if path.exists() else None)


def read(name, folder=None):
    if name not in NAMES:
        raise ValueError(f'Unknown planning document: {name}')
    config = sales_backend.settings()
    if config.get('backend') == 'supabase':
        return _merge(name, sales_backend.call(config, 'marathon_doc_read', {'p_name': name}))
    return _read_local(name, _path(name, folder or DATA_DIR))


def save(name, data, expected_revision, action, folder=None):
    validate(name, data)
    config = sales_backend.settings()
    if config.get('backend') == 'supabase':
        result = sales_backend.call(config, 'marathon_doc_save', {'p_name': name, 'p_data': data,
            'p_expected_revision': expected_revision, 'p_action': action})
        return _merge(name, result)
    return _save_local(name, _path(name, folder or DATA_DIR), data, expected_revision, action)


def _save_local(name, path, data, expected_revision, action):
    """Reject stale edits; keep a backup and atomically replace the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix('.lock')
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError('Another save is in progress. Retry shortly; if it persists, ask an administrator to inspect the save lock.') from None
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        os.close(descriptor)
        current = _read_local(name, path)
        if current['revision'] != expected_revision:
            raise ValueError('These records changed in another session. Reload before saving your changes.')
        result = copy.deepcopy(data)
        result['revision'] = current['revision'] + 1
        now = datetime.now(timezone.utc).isoformat()
        result['saved_at'] = now
        result['history'] = current['history'] + [{'at': now, 'action': action, 'revision': result['revision']}]
        if path.exists():
            backups = path.parent / 'backups'
            backups.mkdir(exist_ok=True)
            (backups / f"{name}-{current['revision']}-{uuid.uuid4().hex[:8]}.json").write_bytes(path.read_bytes())
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        return result
    finally:
        temporary.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)
