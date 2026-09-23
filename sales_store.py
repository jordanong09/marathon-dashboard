"""Versioned local sales records with atomic writes and backup history."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
from datetime import datetime, timezone, date
import uuid

STAGES = ['Waiting for order form','Finance to issue invoice','Awaiting payment','Verifying payment','Release link by SGIM','Links disseminated']
MILESTONES = ['Order form received from company','Invoice issued','Payment reported received','Payment verified','Link released by SGIM','Links disseminated']

def new_store():
    return {'schema_version':1,'revision':0,'companies':[],'orders':[],'targets':{},'history':[]}

def read_store(path):
    if not path.exists():
        return new_store()
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version')!=1 or not all(k in data for k in ['revision','companies','orders','targets','history']):
        raise ValueError('Unsupported or incomplete sales file. Restore a backup before saving.')
    return data

def milestone_date(order, label):
    """Return recorded dates without reinterpreting the former confirmation field."""
    return order.get('milestones', {}).get(label)


def completed(order, label):
    return bool(milestone_date(order, label) or order.get('completed_steps', {}).get(label))


def review_flags(order):
    flags = []
    for label in MILESTONES:
        if completed(order, label) and not milestone_date(order, label):
            flags.append(label + ': date missing')
    last = max((i for i,m in enumerate(MILESTONES) if completed(order,m)), default=-1)
    for label in MILESTONES[:last]:
        if not completed(order,label): flags.append(label + ': completion not recorded')
    if order.get('milestones', {}).get('Order confirmed') or order.get('sent_date') or (order.get('previous_workflow') and not completed(order,MILESTONES[0])):
        flags.append('Previous sent/confirmation dates retained; confirm actual order-form receipt date')
    if completed(order, 'Invoice issued') and not order.get('invoice', '').strip():
        flags.append('Invoice reference missing')
    if completed(order, 'Links disseminated') and not completed(order, 'Payment verified'):
        flags.append('Links disseminated; payment verification not recorded')
    return flags


def waiting_days(order):
    if order.get('cancelled') or completed(order, 'Links disseminated'):
        return None
    dates = [milestone_date(order, m) for m in MILESTONES if milestone_date(order, m)]
    return (date.today() - date.fromisoformat(max(dates))).days if dates else None


def validate_order(order):
    previous = None
    missing = False
    # Existing records keep the old validation until explicitly edited into v2.
    legacy = order.get('workflow_version') != 2
    labels = ['Order confirmed'] + MILESTONES[1:] if legacy else MILESTONES
    values = ([order.get('sent_date')] if legacy else []) + [order['milestones'].get(k) for k in labels]
    for value in values:
        if not value:
            missing = True
            continue
        current = date.fromisoformat(value)
        if missing and legacy:
            raise ValueError('Complete earlier workflow steps before later steps.')
        if previous and current < previous:
            raise ValueError('Known milestone dates must follow chronological order.')
        if current > date.today():
            raise ValueError('Completed milestone dates cannot be in the future.')
        previous = current
    if not order['quantities'] or any(type(v) != int or v < 0 for v in order['quantities'].values()) or sum(order['quantities'].values()) <= 0:
        raise ValueError('Enter at least one place, using non-negative whole numbers.')
    if legacy and order['milestones'].get('Invoice issued') and not order.get('invoice', '').strip():
        raise ValueError('An invoice reference is required before marking the invoice issued.')
    for label, value in order.get('completed_steps', {}).items():
        if label not in MILESTONES or type(value) is not bool:
            raise ValueError('Invalid workflow completion status.')


def save_store(path, data, expected_revision, action):
    """Reject stale edits; retain the previous file and atomically replace the current one."""
    path.parent.mkdir(parents=True,exist_ok=True)
    lock=path.with_suffix('.lock')
    try:
        descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError as error:
        raise ValueError('Another save is in progress. Retry shortly; if it persists, ask an administrator to inspect the save lock.') from error
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        os.close(descriptor)
        current=read_store(path)
        if current['revision']!=expected_revision:
            raise ValueError('These records changed in another session. Reload before saving your changes.')
        for order in data['orders']:
            validate_order(order)
        result=copy.deepcopy(data)
        result['revision']=current['revision']+1
        now=datetime.now(timezone.utc).isoformat()
        result['saved_at']=now
        result['history'].append({'at':now,'action':action,'revision':result['revision']})
        if path.exists():
            backups=path.parent/'backups'; backups.mkdir(exist_ok=True)
            (backups/f"sales-{current['revision']}-{uuid.uuid4().hex[:8]}.json").write_bytes(path.read_bytes())
        with temporary.open('w',encoding='utf-8') as stream:
            json.dump(result,stream,indent=2); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary,path)
        return result
    finally:
        temporary.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)

def stage(order):
    if order.get('cancelled'):
        return 'Cancelled / released'
    if completed(order, 'Links disseminated'):
        return '✓ Complete'
    # Later evidence is preserved even when earlier historical dates are absent.
    for i in range(len(MILESTONES)-2, -1, -1):
        if completed(order, MILESTONES[i]):
            return STAGES[i+1]
    return STAGES[0]


def summarize(orders,categories):
    rows=[]
    for cat in categories:
        active=[o for o in orders if not o.get('cancelled')]
        rows.append({'Category':cat,'Reserved':sum(o['quantities'].get(cat,0) for o in active),
            'Paid':sum(o['quantities'].get(cat,0) for o in active if completed(o, 'Payment verified')),
            'Released':sum(o['quantities'].get(cat,0) for o in active if completed(o, 'Links disseminated'))})
    return rows
