"""Executive view: plan, utilized and remaining for every group and category."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from planning.metrics import gaps, group_summary
from planning.recommendations import build_events, pace_table, recommendations
from views.common import fmt, pct, registration_dates, style_numbers


def _one_decimal(value):
    return '—' if pd.isna(value) else f'{value:,.1f}'


def render_executive_summary(ctx):
    st.subheader('Executive Summary')
    plan, utilized, capacity = ctx['plan'], ctx['utilized'], ctx['capacity']
    summary = group_summary(plan, utilized)
    unallocated = capacity - plan.sum()
    tiles = [('Capacity', capacity.sum()), ('Planned', summary.loc['Total', 'Plan']),
        ('Utilized', summary.loc['Total', 'Utilized']), ('Remaining', summary.loc['Total', 'Remaining']),
        ('Unallocated', unallocated.sum())]
    for column, (label, value) in zip(st.columns(5), tiles):
        column.metric(label, fmt(value))
    if not plan.to_numpy().any():
        st.info('No group allocations saved yet. Open Plan Allocation to set the plan.')
    if ctx['data'] is None:
        st.caption('Campaign and retail utilization come from registrations. Upload the registration CSV in the sidebar; until then they show — and are left out of totals.')

    events = build_events(ctx['attributed'], registration_dates(ctx['data']), ctx['docs']['corporate']['orders'], ctx['docs']['complimentary']['issuances'])
    group_pace = pace_table(plan, utilized, events, ctx['latest_date'], ctx['close_date'])
    category_pace = pace_table(plan, utilized, events, ctx['latest_date'], ctx['close_date'], by_category=True)
    days_left = max((pd.Timestamp(ctx['close_date']) - ctx['latest_date']).days, 0)
    st.markdown('### Recommendations')
    st.caption(f"Based on the 7 complete days before {ctx['latest_date']:%d %b %Y} · {days_left} days to registration close "
        f"({pd.Timestamp(ctx['close_date']):%d %b %Y}, set in Plan Allocation).")
    for level, title, text in recommendations(group_pace, category_pace, unallocated, days_left):
        getattr(st, level)(f'**{title}** — {text}')

    st.markdown('### Pace to close')
    shown = group_pace.drop(columns=['Plan', 'Utilized', 'Remaining'])
    st.dataframe(style_numbers(shown, {'Week on week %': pct, 'Per day': _one_decimal, 'Needed per day': _one_decimal, 'Status': str}), width='stretch')
    st.caption('Last 7 / Previous 7 days: places reserved (Corporate, by order-form date), issued (Complimentary, by issue date) or registered '
        '(Campaign and Retail). Projected at close = utilized + current daily pace × days left.')
    with st.expander('Pace by group and category'):
        detail = category_pace[category_pace['Plan'].gt(0) | category_pace['Last 7 days'].gt(0)]
        st.dataframe(style_numbers(detail, {'Week on week %': pct, 'Per day': _one_decimal, 'Needed per day': _one_decimal, 'Status': str}), width='stretch')

    st.markdown('### By group')
    st.dataframe(style_numbers(summary, {'% utilized': pct}), width='stretch')
    st.caption('Utilized: Corporate = places reserved on active orders · Complimentary = slots issued · Campaign and Retail = registrations.')

    st.markdown('### By group and category')
    view = st.segmented_control('Show', ['Plan', 'Utilized', 'Remaining'], default='Remaining', key='summary_view') or 'Remaining'
    matrix = {'Plan': plan, 'Utilized': utilized, 'Remaining': plan - utilized}[view].copy()
    matrix.loc['Total'] = matrix.sum(min_count=1)
    matrix['Total'] = matrix.sum(axis=1, min_count=1)
    st.dataframe(style_numbers(matrix), width='stretch')
    capacity_rows = pd.DataFrame([capacity, plan.sum(), unallocated], index=['Capacity', 'Planned for groups', 'Unallocated'])
    capacity_rows['Total'] = capacity_rows.sum(axis=1)
    st.dataframe(style_numbers(capacity_rows), width='stretch')
    st.download_button('Download ' + view.lower() + ' table', matrix.to_csv(), f'executive-{view.lower()}.csv', 'text/csv')

    st.markdown('### Gaps')
    items = gaps(plan, utilized, capacity, ctx['attributed'])
    if not items:
        st.success('No gaps found.')
    for level, message in items:
        getattr(st, level)(message)

    attributed = ctx['attributed']
    if attributed is not None:
        with st.expander('Conflicts & data quality'):
            unmapped = int(attributed['Planning Category'].eq('Unmapped').sum())
            conflicts = attributed[attributed['Conflict']]
            st.write(f'{len(attributed):,} registrations · {unmapped:,} with an unrecognised category (not counted in any group) · '
                f'{len(conflicts):,} matched more than one group (each counted once, in the higher-priority group).')
            if len(conflicts):
                table = conflicts.groupby(['Group', 'Subgroup', 'Other Matches']).size().rename('Registrations').reset_index()
                st.dataframe(table, hide_index=True, width='stretch')
