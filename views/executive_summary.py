"""Executive view: plan, utilized and remaining for every group and category."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from planning.metrics import gaps, group_summary
from views.common import fmt, style_numbers


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

    st.markdown('### By group')
    st.dataframe(summary.style.format({'Plan': '{:,.0f}', 'Utilized': '{:,.0f}', 'Remaining': '{:,.0f}', '% utilized': '{:.0f}%'},
        na_rep='—').map(lambda v: 'color:#B42318' if isinstance(v, float) and v < 0 else '', subset=['Remaining']), width='stretch')
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
