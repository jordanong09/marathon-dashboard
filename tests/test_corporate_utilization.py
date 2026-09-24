import math

import pandas as pd

from planning.corporate_utilization import company_category_usage, unused_places

COMPANIES = [{'id': 'c1', 'name': 'Acme'}, {'id': 'c2', 'name': 'Globex'}]
ORDERS = [
    {'company_id': 'c1', 'quantities': {'Full Marathon': 5, 'Half Marathon': 21}, 'cancelled': False,
        'milestones': {'Links disseminated': '2026-09-01'}, 'completed_steps': {}},
    {'company_id': 'c1', 'quantities': {'5 km': 10}, 'cancelled': False, 'milestones': {}, 'completed_steps': {}},
    {'company_id': 'c2', 'quantities': {'10 km': 8}, 'cancelled': True, 'milestones': {}, 'completed_steps': {}},
]
LINKS = {'c1': ['ACME'], 'c2': []}
DATA = pd.DataFrame({'Corporate Group': ['ACME'] * 4 + ['Other'],
    'Grouped Category': ['BYD Marathon', 'BYD Marathon Crew Challenge', 'BYD Marathon', 'adidas Half Marathon', '5km']})


def test_usage_per_company_and_category():
    usage = company_category_usage(COMPANIES, ORDERS, LINKS, DATA).set_index(['Company', 'Category'])
    assert usage.loc[('Acme', 'Full Marathon')].to_dict() == {'Reserved': 5, 'Paid': 0, 'Released': 5, 'Registered': 3}
    assert usage.loc[('Acme', 'Half Marathon'), 'Registered'] == 1
    assert usage.loc[('Acme', '5 km'), 'Released'] == 0
    assert ('Globex', '10 km') not in usage.index  # cancelled orders and empty categories are left out


def test_usage_without_upload_has_no_registrations():
    usage = company_category_usage(COMPANIES, ORDERS, LINKS, None)
    assert usage['Registered'].isna().all()


def test_unused_places_ranked_by_gap():
    usage = company_category_usage(COMPANIES, ORDERS, LINKS, DATA)
    unused = unused_places(usage, 'Reserved')
    assert unused[['Company', 'Category', 'Unused']].values.tolist() == [
        ['Acme', 'Half Marathon', 20], ['Acme', '5 km', 10], ['Acme', 'Full Marathon', 2]]
    assert math.isclose(unused.iloc[0]['Utilization %'], 1 / 21 * 100)
