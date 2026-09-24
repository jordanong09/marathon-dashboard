"""Detect promo-code campaigns from registrations, suggest merges and track when they ran."""
from __future__ import annotations

import copy
import re
import uuid

import pandas as pd

MIN_AUTO_REGISTRATIONS = 5
AUTO_NOTE = 'Detected automatically from registration promo codes'
GROUP_COLUMNS = ['Prefix', 'Suggested name', 'Kind', 'Codes', 'Registrations', 'First registered', 'Last registered']


def code_prefix(code):
    """Family of a code: its leading letters, ignoring separators ('RG-SIM-1', 'RGSIM2' -> 'RGSIM').

    Codes whose leading letters are shorter than 3 characters are their own family ('A1', 'X7K2PQ').
    """
    normalized = re.sub(r'[^0-9A-Z]', '', str(code).strip().upper())
    letters = re.match(r'[A-Z]*', normalized).group()
    return letters if len(letters) >= 3 else (normalized or str(code).strip().upper())


def _name_for(prefix, codes):
    return prefix if len(codes) > 1 else codes[0]


def detect_code_groups(codes, dates, claimed):
    """One row per family of promo codes that no campaign claims, largest first.

    codes: cleaned code per registration ('' = none); dates: registration date per registration.
    A family with several distinct codes is suggested as one campaign named after the family;
    a lone code is suggested under its own name.
    """
    frame = pd.DataFrame({'Code': codes.to_numpy(), 'Date': pd.to_datetime(dates.to_numpy())})
    frame = frame[frame['Code'].ne('') & ~frame['Code'].isin(claimed)]
    if frame.empty:
        return pd.DataFrame(columns=GROUP_COLUMNS)
    frame['Prefix'] = frame['Code'].map(code_prefix)
    grouped = frame.groupby('Prefix').agg(Codes=('Code', lambda s: sorted(s.unique())), Registrations=('Code', 'size'),
        First=('Date', 'min'), Last=('Date', 'max')).reset_index()
    grouped = grouped.rename(columns={'First': 'First registered', 'Last': 'Last registered'})
    grouped['Kind'] = grouped['Codes'].map(lambda c: 'Family' if len(c) > 1 else 'Single code')
    grouped['Suggested name'] = [_name_for(p, c) for p, c in zip(grouped['Prefix'], grouped['Codes'])]
    return grouped.sort_values(['Registrations', 'Prefix'], ascending=[False, True]).reset_index(drop=True)[GROUP_COLUMNS]


def absorb_detected(campaigns, groups, min_registrations=MIN_AUTO_REGISTRATIONS, make_id=lambda: uuid.uuid4().hex):
    """Return (campaigns, created, extended).

    New codes of a family that already has an automatic campaign join it (a single-code campaign is
    renamed to the family once it has siblings). Other families with at least min_registrations become
    new automatic campaigns. Manually created campaigns are never changed.
    """
    campaigns = copy.deepcopy(campaigns)
    auto = {c['prefix']: c for c in campaigns if c.get('auto') and c.get('prefix')}
    names = {c['name'].casefold() for c in campaigns}
    claimed = {code for c in campaigns for code in c['codes']}
    created, extended = [], []
    for group in groups.to_dict('records'):
        fresh = [code for code in group['Codes'] if code not in claimed]
        if not fresh:
            continue
        prefix = group['Prefix']
        if prefix in auto:
            campaign = auto[prefix]
            was_single = campaign['name'] in campaign['codes'] and len(campaign['codes']) == 1
            campaign['codes'] += fresh
            if was_single and prefix.casefold() not in names:
                names.discard(campaign['name'].casefold())
                campaign['name'] = prefix
                names.add(prefix.casefold())
            extended.append(campaign['name'])
        elif group['Registrations'] >= min_registrations:
            name = _name_for(prefix, fresh)
            if name.casefold() in names:
                name = f'{name} (auto)'
            if name.casefold() in names:
                continue
            campaign = {'id': make_id(), 'name': name, 'type': 'shared', 'codes': fresh, 'cap': None,
                'start': None, 'end': None, 'notes': AUTO_NOTE, 'auto': True, 'prefix': prefix}
            campaigns.append(campaign)
            auto[prefix] = campaign
            names.add(name.casefold())
            created.append(name)
        else:
            continue
        claimed.update(fresh)
    return campaigns, created, extended


def suggest_merges(campaigns):
    """Families of codes spread over more than one campaign: [{'prefix', 'ids', 'campaigns'}]."""
    families = {}
    for campaign in campaigns:
        keys = {code_prefix(code) for code in campaign['codes']}
        if len(keys) == 1:
            families.setdefault(keys.pop(), []).append(campaign)
    return [{'prefix': prefix, 'ids': [c['id'] for c in members], 'campaigns': [c['name'] for c in members]}
        for prefix, members in sorted(families.items()) if len(members) > 1]


def merge_campaigns(campaigns, ids, name):
    """Combine the given campaigns into the first one: all codes, summed caps, widest planned dates."""
    members = [c for c in campaigns if c['id'] in ids]
    keeper = copy.deepcopy(members[0])
    caps = [c.get('cap') for c in members]
    starts = [c['start'] for c in members if c.get('start')]
    ends = [c['end'] for c in members if c.get('end')]
    keeper.update(name=name, codes=list(dict.fromkeys(code for c in members for code in c['codes'])),
        cap=sum(caps) if all(cap is not None for cap in caps) else None,
        start=min(starts) if starts else None, end=max(ends) if ends else None,
        notes='; '.join(dict.fromkeys(c.get('notes', '') for c in members if c.get('notes'))),
        auto=all(c.get('auto') for c in members), prefix=code_prefix(keeper['codes'][0]))
    return [keeper if c['id'] == keeper['id'] else c for c in campaigns if c['id'] == keeper['id'] or c['id'] not in ids]


def campaign_activity(campaign_names, dates):
    """Per campaign: first and last registration date, total code uses and uses in the last 7 days of data."""
    frame = pd.DataFrame({'Campaign': campaign_names.to_numpy(), 'Date': pd.to_datetime(dates.to_numpy())})
    latest = frame['Date'].max()
    frame = frame[frame['Campaign'].ne('')]
    if frame.empty:
        return pd.DataFrame(columns=['Campaign', 'First registered', 'Last registered', 'Code uses', 'Last 7 days'])
    frame['Recent'] = frame['Date'] >= latest - pd.Timedelta(days=6)
    activity = frame.groupby('Campaign').agg(First=('Date', 'min'), Last=('Date', 'max'), Uses=('Date', 'size'),
        Recent=('Recent', 'sum')).reset_index()
    return activity.rename(columns={'First': 'First registered', 'Last': 'Last registered', 'Uses': 'Code uses', 'Recent': 'Last 7 days'})
