"""Plan, utilized and remaining matrices (groups x planning categories)."""
from __future__ import annotations

import pandas as pd

from planning.categories import GROUPS, PLANNING_CATEGORIES, UNMAPPED, convert_quantities

REGISTRATION_GROUPS = ['Campaign', 'Local Retail', 'International Retail']
LEVELS = ['error', 'warning', 'info']


def empty_matrix(fill=0.0):
    return pd.DataFrame(fill, index=GROUPS, columns=PLANNING_CATEGORIES, dtype=float)


def capacity_series(plan_doc):
    return pd.Series({c: plan_doc['capacity'].get(c, 0) for c in PLANNING_CATEGORIES}, dtype=float)


def plan_matrix(plan_doc):
    matrix = empty_matrix()
    for group, row in plan_doc['allocation'].items():
        for category, value in row.items():
            if group in matrix.index and category in matrix.columns:
                matrix.loc[group, category] = value
    return matrix


def sum_quantities(records):
    """Total non-cancelled quantities by planning category."""
    total = pd.Series(0.0, index=PLANNING_CATEGORIES)
    for record in records:
        if record.get('cancelled'):
            continue
        for category, value in convert_quantities(record['quantities']).items():
            if category in total.index:
                total[category] += value
    return total


def registered_matrix(attributed):
    mapped = attributed[attributed['Planning Category'].ne(UNMAPPED)]
    counts = pd.crosstab(mapped['Group'], mapped['Planning Category'])
    return counts.reindex(index=GROUPS, columns=PLANNING_CATEGORIES, fill_value=0).astype(float)


def utilized_matrix(corporate_orders, issuances, attributed):
    """Corporate = reserved, Complimentary = issued, others = registrations (NaN without an upload)."""
    matrix = empty_matrix(float('nan'))
    matrix.loc['Corporate'] = sum_quantities(corporate_orders)
    matrix.loc['Complimentary'] = sum_quantities(issuances)
    if attributed is not None:
        matrix.loc[REGISTRATION_GROUPS] = registered_matrix(attributed).loc[REGISTRATION_GROUPS]
    return matrix


def group_summary(plan, utilized):
    used = utilized.sum(axis=1, min_count=1)
    summary = pd.DataFrame({'Plan': plan.sum(axis=1), 'Utilized': used})
    summary.loc['Total'] = [plan.to_numpy().sum(), used.sum(min_count=1)]
    summary['Remaining'] = summary.Plan - summary.Utilized
    summary['% utilized'] = summary.Utilized / summary.Plan.replace(0, float('nan')) * 100
    return summary


def unmatched_codes(attributed):
    codes = attributed.loc[attributed['Promo Code'].ne('') & attributed['Campaign'].eq(''), 'Promo Code']
    return codes.value_counts()


def gaps(plan, utilized, capacity, attributed, low_share=0.5):
    """Return (level, message) pairs ordered error → warning → info."""
    items = []
    remaining = plan - utilized
    for group in GROUPS:
        if not plan.loc[group].any():
            used = utilized.loc[group].sum(min_count=1)
            if pd.notna(used) and used > 0:
                items.append(('warning', f'{group}: {used:,.0f} utilized but no plan allocation yet'))
            continue
        for category in PLANNING_CATEGORIES:
            value = remaining.loc[group, category]
            if pd.notna(value) and value < 0:
                items.append(('error', f'{group} · {category}: {-value:,.0f} over plan'))
    unallocated = capacity - plan.sum()
    for category, value in unallocated.items():
        if value < 0:
            items.append(('error', f'{category}: plan exceeds capacity by {-value:,.0f}'))
        elif value > 0:
            items.append(('info', f'{category}: {value:,.0f} places not yet allocated to a group'))
    for group in GROUPS:
        planned, used = plan.loc[group].sum(), utilized.loc[group].sum(min_count=1)
        if planned > 0 and pd.notna(used) and used < planned * low_share:
            items.append(('warning', f'{group}: {used / planned:.0%} of plan utilized ({used:,.0f} of {planned:,.0f})'))
    if attributed is not None and not attributed.empty:
        for label, group in [('Unlinked', 'Corporate'), ('Unconfigured', 'Complimentary')]:
            count = int((attributed['Group'].eq(group) & attributed['Subgroup'].eq(label)).sum())
            if count:
                items.append(('warning', f'{count:,} {group.lower()} registrations are {label.lower()}: link their registration names in the {group} tab'))
        unmatched = unmatched_codes(attributed)
        if len(unmatched):
            items.append(('info', f'{len(unmatched):,} promo codes ({int(unmatched.sum()):,} registrations) are not in any campaign'))
    return sorted(items, key=lambda item: LEVELS.index(item[0]))
