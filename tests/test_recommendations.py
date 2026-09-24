import math

import pandas as pd

from planning.categories import GROUPS, PLANNING_CATEGORIES
from planning.metrics import empty_matrix
from planning.recommendations import build_events, pace_table, recommendations

LATEST = pd.Timestamp('2026-09-24')
CLOSE = '2026-09-30'  # 6 days left


def matrix(**cells):
    frame = empty_matrix()
    for key, value in cells.items():
        group, category = key.split('__')
        frame.loc[group.replace('_', ' '), category.replace('_', ' ')] = value
    return frame


def registrations(group, category, dates):
    return pd.DataFrame({'Group': group, 'Planning Category': category, 'Date': pd.to_datetime(dates), 'Places': 1})


def test_build_events_uses_order_and_issue_dates_and_skips_cancelled():
    attributed = pd.DataFrame({'Group': ['Local Retail', 'Corporate', 'Campaign'], 'Planning Category': ['5 km', '5 km', 'Unmapped']})
    dates = pd.Series(pd.to_datetime(['2026-09-20', '2026-09-20', '2026-09-20']))
    orders = [{'quantities': {'BYD Marathon': 4}, 'cancelled': False, 'milestones': {'Order form received from company': '2026-09-18'}},
        {'quantities': {'5 km': 9}, 'cancelled': True, 'milestones': {}}]
    issuances = [{'quantities': {'10 km': 3}, 'cancelled': False, 'date': '2026-09-19'}]
    events = build_events(attributed, dates, orders, issuances)
    assert sorted(map(tuple, events[['Group', 'Planning Category', 'Places']].values.tolist())) == [
        ('Complimentary', '10 km', 3), ('Corporate', 'Full Marathon', 4), ('Local Retail', '5 km', 1)]


def test_pace_table_projects_to_close_from_last_seven_complete_days():
    plan = matrix(Corporate__Full_Marathon=100, Local_Retail__Full_Marathon=50)
    utilized = matrix(Corporate__Full_Marathon=40, Local_Retail__Full_Marathon=45)
    utilized.loc['Campaign'] = 0
    utilized.loc['International Retail'] = 0
    days = pd.date_range('2026-09-17', '2026-09-23')  # the 7 complete days before LATEST
    events = pd.concat([registrations('Local Retail', 'Full Marathon', list(days) * 2),  # 14 in the window
        registrations('Local Retail', 'Full Marathon', ['2026-09-12'] * 7),  # previous window
        registrations('Local Retail', 'Full Marathon', ['2026-09-24'] * 50)])  # partial latest day ignored
    events = pd.concat([events, pd.DataFrame({'Group': ['Corporate'], 'Planning Category': ['Full Marathon'],
        'Date': [pd.Timestamp('2026-09-20')], 'Places': [7]})])
    table = pace_table(plan, utilized, events, LATEST, CLOSE)
    retail, corporate = table.loc['Local Retail'], table.loc['Corporate']
    assert retail['Last 7 days'] == 14 and retail['Previous 7 days'] == 7 and retail['Week on week %'] == 100
    assert retail['Per day'] == 2 and retail['Projected at close'] == 45 + 2 * 6 and retail['Status'] == 'Ahead of plan'
    assert corporate['Per day'] == 1 and corporate['Needed per day'] == 10 and corporate['Projected vs plan'] == -54
    assert corporate['Status'] == 'Behind'
    by_category = pace_table(plan, utilized, events, LATEST, CLOSE, by_category=True)
    assert by_category.loc[('Local Retail', 'Full Marathon'), 'Projected vs plan'] == 7


def test_recommendations_cover_momentum_shortfall_and_rebalancing():
    plan = matrix(Corporate__Full_Marathon=100, Local_Retail__Full_Marathon=50)
    utilized = matrix(Corporate__Full_Marathon=40, Local_Retail__Full_Marathon=45)
    utilized.loc['Campaign'] = 0
    utilized.loc['International Retail'] = 0
    events = registrations('Local Retail', 'Full Marathon', list(pd.date_range('2026-09-17', '2026-09-23')) * 2)
    groups = pace_table(plan, utilized, events, LATEST, CLOSE)
    categories = pace_table(plan, utilized, events, LATEST, CLOSE, by_category=True)
    unallocated = pd.Series(0.0, index=PLANNING_CATEGORIES)
    items = recommendations(groups, categories, unallocated, days_left=6)
    titles = [title for _, title, _ in items]
    assert titles[0] == 'Momentum: Local Retail'
    assert 'Behind plan: Corporate' in titles
    rebalance = next(text for _, title, text in items if title == 'Rebalance Full Marathon')
    assert 'from Corporate to Local Retail' in rebalance and 'about 7 places' in rebalance


def test_closed_registration_gives_single_message():
    empty = empty_matrix()
    groups = pace_table(empty, empty, pd.DataFrame(columns=['Group', 'Planning Category', 'Date', 'Places']), LATEST, '2026-09-01')
    assert math.isnan(groups.loc['Corporate', 'Needed per day'])
    items = recommendations(groups, groups, pd.Series(0.0, index=PLANNING_CATEGORIES), days_left=0)
    assert [title for _, title, _ in items] == ['Registration has closed']
