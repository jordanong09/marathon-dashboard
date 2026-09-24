"""Detect promo-code campaigns from registrations and track when they ran."""
from __future__ import annotations

import copy
import re
import uuid

import pandas as pd

MIN_AUTO_REGISTRATIONS = 5
AUTO_NOTE = 'Detected automatically from registration promo codes'
GROUP_COLUMNS = ['Prefix', 'Codes', 'Registrations', 'First registered', 'Last registered']


def code_prefix(code):
    """Campaign stem of a code: trailing numbers removed, upper case ('EARLY10' -> 'EARLY')."""
    code = str(code).strip()
    stem = re.sub(r'[\s_\-]*\d+$', '', code).upper()
    return stem if len(stem) >= 2 else code.upper()


def detect_code_groups(codes, dates, claimed):
    """One row per stem of promo codes that no campaign claims, largest first.

    codes: cleaned code per registration ('' = none); dates: registration date per registration.
    """
    frame = pd.DataFrame({'Code': codes.to_numpy(), 'Date': pd.to_datetime(dates.to_numpy())})
    frame = frame[frame['Code'].ne('') & ~frame['Code'].isin(claimed)]
    if frame.empty:
        return pd.DataFrame(columns=GROUP_COLUMNS)
    frame['Prefix'] = frame['Code'].map(code_prefix)
    grouped = frame.groupby('Prefix').agg(Codes=('Code', lambda s: sorted(s.unique())), Registrations=('Code', 'size'),
        First=('Date', 'min'), Last=('Date', 'max')).reset_index()
    grouped = grouped.rename(columns={'First': 'First registered', 'Last': 'Last registered'})
    return grouped.sort_values(['Registrations', 'Prefix'], ascending=[False, True]).reset_index(drop=True)[GROUP_COLUMNS]


def absorb_detected(campaigns, groups, min_registrations=MIN_AUTO_REGISTRATIONS, make_id=lambda: uuid.uuid4().hex):
    """Return (campaigns, created, extended).

    New codes whose stem matches an automatic campaign join it. Other stems with at least
    min_registrations become new automatic campaigns. Manually created campaigns are never changed.
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
            auto[prefix]['codes'] += fresh
            extended.append(auto[prefix]['name'])
        elif group['Registrations'] >= min_registrations:
            name = prefix if prefix.casefold() not in names else f'{prefix} (auto)'
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
