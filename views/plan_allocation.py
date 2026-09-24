"""Executive-owned plan: category capacity and group allocations."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from planning.categories import GROUPS, PLANNING_CATEGORIES
from views.common import save_doc, style_numbers


def plan_frame(plan_doc):
    rows = [{'Row': 'Capacity', **plan_doc['capacity']}]
    rows += [{'Row': group, **plan_doc['allocation'].get(group, {})} for group in GROUPS]
    return pd.DataFrame(rows, columns=['Row'] + PLANNING_CATEGORIES).fillna(0)


def frame_to_plan(frame):
    values = frame.set_index('Row')[PLANNING_CATEGORIES]
    if values.isna().any().any():
        raise ValueError('Every cell needs a number (use 0 for none).')
    row = lambda name: {category: int(values.loc[name, category]) for category in PLANNING_CATEGORIES}
    return {'capacity': row('Capacity'), 'allocation': {group: row(group) for group in GROUPS}}


def render_plan_allocation(ctx):
    st.subheader('Plan Allocation')
    plan_doc = ctx['docs']['plan']
    st.caption(f"Saved revision {plan_doc['revision']} · {plan_doc.get('saved_at', 'not saved yet')}")
    st.caption('Set total capacity per category, then allocate places to each group. Stakeholders split their allocation inside their own tab.')
    edited = st.data_editor(plan_frame(plan_doc), hide_index=True, disabled=['Row'], width='stretch',
        key=f"plan_editor_{plan_doc['revision']}",
        column_config={c: st.column_config.NumberColumn(min_value=0, step=1, required=True) for c in PLANNING_CATEGORIES})
    try:
        changed = frame_to_plan(edited)
    except ValueError as error:
        st.error(str(error))
        return
    capacity = pd.Series(changed['capacity'])
    allocated = pd.DataFrame(changed['allocation']).T.sum()
    check = pd.DataFrame([allocated, capacity - allocated], index=['Allocated to groups', 'Unallocated'])[PLANNING_CATEGORIES]
    check['Total'] = check.sum(axis=1)
    st.dataframe(style_numbers(check), width='stretch')
    if (capacity - allocated).lt(0).any():
        st.error('Group allocations exceed capacity in at least one category. You can still save, but the plan is oversold.')
    note = st.text_input('Note for this save (optional)', key='plan_note')
    if st.button('Save plan', type='primary'):
        save_doc('plan', plan_doc | changed, 'Plan saved' + (': ' + note.strip() if note.strip() else ''))
    st.download_button('Download plan (CSV)', edited.to_csv(index=False), 'plan-allocation.csv', 'text/csv')
    if plan_doc['history']:
        with st.expander('Save history'):
            st.dataframe(pd.DataFrame(plan_doc['history'][::-1]), hide_index=True, width='stretch')
