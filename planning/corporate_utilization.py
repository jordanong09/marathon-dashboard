"""Corporate places versus registrations, per company and planning category."""
from __future__ import annotations

import pandas as pd

from planning.categories import PLANNING_CATEGORIES, to_planning_category
from sales_store import summarize

COLUMNS = ['Company', 'Category', 'Reserved', 'Paid', 'Released', 'Registered']


def company_category_usage(companies, orders, linked_names, data):
    """Long table of Reserved/Paid/Released/Registered per company and category.

    linked_names: {company id: [registration names]}. Registered is NaN without an upload.
    Rows with no places and no registrations are left out.
    """
    rows = []
    for company in companies:
        company_orders = [o for o in orders if o['company_id'] == company['id']]
        totals = pd.DataFrame(summarize(company_orders, PLANNING_CATEGORIES)).set_index('Category')
        registered = None
        if data is not None and not data.empty:
            matched = data[data['Corporate Group'].fillna('').astype(str).isin(linked_names.get(company['id'], []))]
            registered = matched['Grouped Category'].map(to_planning_category).value_counts()
        for category in PLANNING_CATEGORIES:
            count = float('nan') if registered is None else int(registered.get(category, 0))
            reserved, paid, released = (int(totals.loc[category, column]) for column in ('Reserved', 'Paid', 'Released'))
            if reserved or released or (registered is not None and count):
                rows.append({'Company': company['name'], 'Category': category, 'Reserved': reserved,
                    'Paid': paid, 'Released': released, 'Registered': count})
    return pd.DataFrame(rows, columns=COLUMNS)


def unused_places(usage, basis):
    """Company/category pairs with places not yet registered, largest gap first. basis: 'Reserved' or 'Released'."""
    frame = usage.dropna(subset=['Registered']).copy()
    frame['Unused'] = (frame[basis] - frame['Registered']).astype(int)
    frame = frame[frame['Unused'] > 0]
    frame['Utilization %'] = frame['Registered'] / frame[basis] * 100
    return frame.sort_values(['Unused', 'Company'], ascending=[False, True])[
        ['Company', 'Category', basis, 'Registered', 'Unused', 'Utilization %']].reset_index(drop=True)
