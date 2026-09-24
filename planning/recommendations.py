"""Pace to registration close and management recommendations from plan, utilization and recent trend."""
from __future__ import annotations

import pandas as pd

from planning.categories import GROUPS, PLANNING_CATEGORIES, UNMAPPED, convert_quantities
from planning.metrics import REGISTRATION_GROUPS

WINDOW = 7
EVENT_COLUMNS = ['Group', 'Planning Category', 'Date', 'Places']
ORDER_DATE = 'Order form received from company'
DEFAULT_CLOSE_DATE = '2026-09-30'


def build_events(attributed, dates, orders):
    """Dated units of utilization: reserved places for Corporate (order-form date), registrations for every other group."""
    frames = []
    if attributed is not None and not attributed.empty:
        registered = pd.DataFrame({'Group': attributed['Group'].to_numpy(), 'Planning Category': attributed['Planning Category'].to_numpy(),
            'Date': pd.to_datetime(dates.to_numpy()), 'Places': 1})
        frames.append(registered[registered['Group'].isin(REGISTRATION_GROUPS) & registered['Planning Category'].ne(UNMAPPED)])
    rows = []
    sources = [('Corporate', orders, lambda o: o.get('milestones', {}).get(ORDER_DATE) or o.get('created_at'))]
    for group, records, date_of in sources:
        for record in records:
            if record.get('cancelled'):
                continue
            when = pd.to_datetime(date_of(record), errors='coerce')
            for category, places in convert_quantities(record['quantities']).items():
                if category in PLANNING_CATEGORIES and places:
                    rows.append({'Group': group, 'Planning Category': category, 'Date': when, 'Places': places})
    if rows:
        frames.append(pd.DataFrame(rows))
    frames = [frame for frame in frames if not frame.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=EVENT_COLUMNS)


def _status(plan, used, projected, days_left):
    if pd.isna(used):
        return 'Upload registrations'
    if not plan:
        return 'No plan' if used else ''
    if not days_left:
        return 'Closed'
    if projected > plan * 1.05:
        return 'Ahead of plan'
    if projected >= plan:
        return 'On track'
    return 'Slightly behind' if projected >= plan * 0.9 else 'Behind'


def pace_table(plan, utilized, events, latest, close_date, by_category=False):
    """Plan, utilized, recent pace and projection at close per group (or group × category).

    Pace uses the 7 complete days before the latest registration date (that day is usually partial).
    """
    latest = pd.Timestamp(latest).normalize()
    days_left = max((pd.Timestamp(close_date).normalize() - latest).days, 0)
    recent_start = latest - pd.Timedelta(days=WINDOW)
    previous_start = recent_start - pd.Timedelta(days=WINDOW)
    dated = events.dropna(subset=['Date'])
    dated = dated.assign(Date=pd.to_datetime(dated['Date']), Places=pd.to_numeric(dated['Places']))
    recent = dated[(dated['Date'] >= recent_start) & (dated['Date'] < latest)]
    previous = dated[(dated['Date'] >= previous_start) & (dated['Date'] < recent_start)]
    if by_category:
        index = pd.MultiIndex.from_product([GROUPS, PLANNING_CATEGORIES], names=['Group', 'Category'])
        planned = pd.Series(plan.loc[GROUPS, PLANNING_CATEGORIES].to_numpy().ravel(), index=index)
        used = pd.Series(utilized.loc[GROUPS, PLANNING_CATEGORIES].to_numpy().ravel(), index=index)
        keys = ['Group', 'Planning Category']
    else:
        index = pd.Index(GROUPS, name='Group')
        planned, used, keys = plan.sum(axis=1), utilized.sum(axis=1, min_count=1), ['Group']
    count = lambda frame: frame.groupby(keys)['Places'].sum().rename_axis(index.names).reindex(index).fillna(0)
    table = pd.DataFrame({'Plan': planned.reindex(index), 'Utilized': used.reindex(index)})
    table['Remaining'] = table['Plan'] - table['Utilized']
    table['Last 7 days'] = count(recent)
    table['Previous 7 days'] = count(previous)
    table['Week on week %'] = (table['Last 7 days'] / table['Previous 7 days'].replace(0, float('nan')) - 1) * 100
    table['Per day'] = table['Last 7 days'] / WINDOW
    table['Needed per day'] = table['Remaining'].clip(lower=0) / days_left if days_left else float('nan')
    table['Projected at close'] = table['Utilized'] + table['Per day'] * days_left
    table['Projected vs plan'] = table['Projected at close'] - table['Plan']
    table['Status'] = [_status(p, u, pr, days_left) for p, u, pr in zip(table['Plan'], table['Utilized'], table['Projected at close'])]
    return table


def _round(value):
    return int(round(value / 10) * 10) if value >= 20 else int(round(value))


def recommendations(group_pace, category_pace, unallocated, days_left):
    """Plain-language (level, title, text) items for management, most useful first."""
    if not days_left:
        return [('info', 'Registration has closed', 'Projections stop at the close date; the tables show final utilization against plan.')]
    items = []
    known = group_pace[group_pace['Utilized'].notna()]
    moving = known[known['Last 7 days'].gt(0)]
    if not moving.empty:
        top = moving['Last 7 days'].idxmax()
        row = moving.loc[top]
        trend = '' if pd.isna(row['Week on week %']) else f" ({row['Week on week %']:+.0f}% vs the previous 7 days)"
        follow = (f"It still has {row['Remaining']:,.0f} places to fill against plan — keep pushing while demand is strong."
            if row['Remaining'] > 0 else 'It has already reached its plan — consider giving it more places.')
        items.append(('success', f'Momentum: {top}', f"{top} added {row['Last 7 days']:,.0f} places in the last 7 days{trend}, more than any other group. {follow}"))
        growing = moving[moving['Previous 7 days'].ge(10) & moving['Week on week %'].ge(25)].drop(index=top, errors='ignore')
        if not growing.empty:
            fastest = growing['Week on week %'].idxmax()
            items.append(('success', f'Accelerating: {fastest}', f"{fastest} is up {growing.loc[fastest, 'Week on week %']:.0f}% week on week."))
    behind = known[known['Plan'].gt(0) & known['Projected vs plan'].lt(0)].sort_values('Projected vs plan')
    for group, row in behind.head(2).iterrows():
        items.append(('warning', f'Behind plan: {group}', f"{group} needs {row['Needed per day']:,.0f} places a day to reach its plan of "
            f"{row['Plan']:,.0f} by close but is averaging {row['Per day']:,.1f}. At this pace it ends about {-row['Projected vs plan']:,.0f} short."))
    moves = []
    for category in PLANNING_CATEGORIES:
        rows = category_pace.xs(category, level='Category')
        rows = rows[rows['Utilized'].notna()]
        spare = (rows['Plan'] - rows['Projected at close']).where(rows['Plan'].gt(0) & rows['Projected vs plan'].lt(0)).dropna()
        demand = rows['Projected vs plan'].where(rows['Projected vs plan'].gt(0)).dropna()
        if demand.empty:
            continue
        receiver, excess = demand.idxmax(), demand.max()
        free = unallocated.get(category, 0)
        if free > 0:
            moves.append((min(free, excess), ('info', f'Allocate {category}',
                f"{category} has {free:,.0f} unallocated places and {receiver} is on course to exceed its plan by about "
                f"{_round(excess)}. Consider allocating up to {_round(min(free, excess))} places to {receiver}.")))
        elif not spare.empty:
            donor = spare.idxmax()
            move = min(spare.max(), excess)
            moves.append((move, ('info', f'Rebalance {category}',
                f"{receiver} is on course to exceed its {category} plan by about {_round(excess)}, while {donor} is projected to leave "
                f"about {_round(spare.max())} unused. Consider moving about {_round(move)} places from {donor} to {receiver}.")))
    items += [item for _, item in sorted(moves, key=lambda pair: -pair[0])[:3]]
    if not items:
        items.append(('success', 'On track', 'Every planned group is on pace to meet its plan by close.'))
    return items
