import math

import pandas as pd

from planning.categories import DEFAULT_CAPACITY, GROUPS, PLANNING_CATEGORIES
from planning.metrics import (capacity_series, gaps, group_summary, plan_matrix, unmatched_codes,
    utilized_matrix)


def plan_doc(**cells):
    allocation = {g: {c: 0 for c in PLANNING_CATEGORIES} for g in GROUPS}
    for (group, category), value in cells.items():
        allocation[group][category] = value
    return {'capacity': dict(DEFAULT_CAPACITY), 'allocation': allocation}


def attributed(rows):
    return pd.DataFrame(rows, columns=['Group', 'Subgroup', 'Planning Category', 'Promo Code', 'Campaign', 'Conflict', 'Other Matches'])


def test_plan_matrix_and_capacity():
    doc = plan_doc()
    doc['allocation']['Corporate']['Full Marathon'] = 200
    assert plan_matrix(doc).loc['Corporate', 'Full Marathon'] == 200
    assert capacity_series(doc)['Full Marathon'] == 13000


def test_utilized_uses_reservations_issuances_and_registrations():
    orders = [{'quantities': {'BYD Marathon': 50, 'BYD Marathon Crew Challenge': 10}, 'cancelled': False},
        {'quantities': {'Full Marathon': 99}, 'cancelled': True}]
    issuances = [{'quantities': {'5 km': 7}, 'cancelled': False}]
    registrations = attributed([
        ['Campaign', 'Early', 'Half Marathon', 'EARLY', 'Early', False, ''],
        ['Local Retail', '', '10 km', '', '', False, ''],
        ['Local Retail', '', 'Unmapped', '', '', False, ''],
        ['Corporate', 'Acme', 'Full Marathon', '', '', False, '']])
    result = utilized_matrix(orders, issuances, registrations)
    assert result.loc['Corporate', 'Full Marathon'] == 60
    assert result.loc['Complimentary', '5 km'] == 7
    assert result.loc['Campaign', 'Half Marathon'] == 1
    assert result.loc['Local Retail'].sum() == 1


def test_utilized_without_upload_is_nan_for_registration_groups():
    result = utilized_matrix([], [], None)
    assert result.loc['Corporate'].sum() == 0
    assert result.loc['Campaign'].isna().all()


def test_group_summary_totals():
    doc = plan_doc()
    doc['allocation']['Corporate']['5 km'] = 100
    plan = plan_matrix(doc)
    utilized = utilized_matrix([{'quantities': {'5 km': 120}, 'cancelled': False}], [], None)
    summary = group_summary(plan, utilized)
    assert summary.loc['Corporate', 'Remaining'] == -20
    assert summary.loc['Total', 'Plan'] == 100
    assert math.isnan(summary.loc['Campaign', 'Utilized'])


def test_gaps_report_over_allocation_oversold_and_low_utilization():
    doc = plan_doc()
    doc['allocation']['Corporate']['5 km'] = 100
    doc['allocation']['Complimentary']['Kids 600 m'] = 3000
    plan = plan_matrix(doc)
    utilized = utilized_matrix([{'quantities': {'5 km': 120}, 'cancelled': False}], [], None)
    messages = gaps(plan, utilized, capacity_series(doc), None)
    levels = [level for level, _ in messages]
    text = ' | '.join(message for _, message in messages)
    assert 'Corporate · 5 km: 20 over plan' in text
    assert 'Kids 600 m: plan exceeds capacity by 500' in text
    assert 'Complimentary: 0% of plan utilized' in text
    assert levels == sorted(levels, key=['error', 'warning', 'info'].index)


def test_unmatched_codes():
    registrations = attributed([
        ['Local Retail', '', '5 km', 'MEDIC', '', False, ''],
        ['Local Retail', '', '5 km', 'MEDIC', '', False, ''],
        ['Campaign', 'Early', '5 km', 'EARLY', 'Early', False, '']])
    assert unmatched_codes(registrations).to_dict() == {'MEDIC': 2}
