"""Complimentary programmes: tag links, issued slots and registrations."""
from __future__ import annotations

import uuid
from datetime import date

import pandas as pd
import streamlit as st

from planning.categories import PLANNING_CATEGORIES
from planning.metrics import sum_quantities
from views.common import needs_upload, quantity_editor, save_doc, target_strip


def _registered(attributed, programme):
    if attributed is None:
        return None
    rows = attributed[attributed['Group'].eq('Complimentary') & attributed['Subgroup'].eq(programme)]
    return rows['Planning Category'].value_counts()


def render_complimentary(ctx):
    st.subheader('Complimentary')
    target_strip(ctx, 'Complimentary')
    doc = ctx['docs']['complimentary']
    programmes, issuances = doc['programmes'], doc['issuances']
    names = {p['id']: p['name'] for p in programmes}
    data = ctx['data']
    found = [] if data is None else sorted(data['Complimentary Programme'].dropna().astype(str).str.strip().loc[lambda s: s.ne('')].unique())
    linked = {tag.casefold() for p in programmes for tag in p['tags']}
    unlinked = [tag for tag in found if tag.casefold() not in linked]
    overview, manage, issue, activity = st.tabs(['Overview', 'Programmes', 'Record issuance', 'Activity'])

    with overview:
        if not programmes:
            st.info('No programmes yet. Add one under Programmes.')
        rows, detail = [], []
        for p in programmes:
            issued = sum_quantities([i for i in issuances if i['programme_id'] == p['id']])
            registered = _registered(ctx['attributed'], p['name'])
            reg_total = None if registered is None else int(registered.sum())
            rows.append({'Programme': p['name'], 'Issued': int(issued.sum()), 'Registered': reg_total,
                'Conversion %': reg_total / issued.sum() * 100 if reg_total is not None and issued.sum() else None})
            for category in PLANNING_CATEGORIES:
                reg = None if registered is None else int(registered.get(category, 0))
                if issued[category] or reg:
                    detail.append({'Programme': p['name'], 'Category': category, 'Issued': int(issued[category]), 'Registered': reg})
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch',
                column_config={'Conversion %': st.column_config.NumberColumn(format='%.0f%%')})
            with st.expander('By category'):
                st.dataframe(pd.DataFrame(detail), hide_index=True, width='stretch')
        if unlinked:
            st.warning(f'{len(unlinked)} complimentary tags in the registration data are not linked to a programme: {", ".join(unlinked)}')
        needs_upload(ctx)

    with manage:
        with st.form('comp_new_programme', clear_on_submit=True):
            st.markdown('**Add programme**')
            name = st.text_input('Programme name')
            tags = st.multiselect('Registration tags (COMPLIMENTARY_…)', unlinked, help='Tags found in the uploaded registration data.')
            notes = st.text_area('Notes')
            if st.form_submit_button('Add programme'):
                changed = doc | {'programmes': programmes + [{'id': uuid.uuid4().hex, 'name': name.strip(), 'tags': tags, 'notes': notes}]}
                save_doc('complimentary', changed, 'Programme added: ' + name.strip())
        if programmes:
            key = st.selectbox('Edit programme', list(names), format_func=names.get, key='comp_edit_programme')
            programme = next(p for p in programmes if p['id'] == key)
            with st.form('comp_programme_' + key):
                name = st.text_input('Programme name', programme['name'])
                tags = st.multiselect('Registration tags', sorted(set(unlinked + programme['tags'])), default=programme['tags'])
                notes = st.text_area('Notes', programme.get('notes', ''))
                if st.form_submit_button('Save programme'):
                    updated = [p | {'name': name.strip(), 'tags': tags, 'notes': notes} if p['id'] == key else p for p in programmes]
                    save_doc('complimentary', doc | {'programmes': updated}, 'Programme updated: ' + name.strip())

    with issue:
        if not programmes:
            st.info('Add a programme first.')
        else:
            with st.form('comp_new_issuance', clear_on_submit=True):
                st.markdown('**Record slots given out**')
                programme_id = st.selectbox('Programme', list(names), format_func=names.get)
                issued_on = st.date_input('Date issued', value=date.today(), max_value=date.today())
                recipient = st.text_input('Recipient or batch', help='For example: "KOL batch 1" or a partner name.')
                quantities = quantity_editor('comp_new_quantities')
                notes = st.text_area('Notes')
                if st.form_submit_button('Save issuance'):
                    item = {'id': uuid.uuid4().hex, 'programme_id': programme_id, 'date': issued_on.isoformat(),
                        'recipient': recipient.strip(), 'quantities': quantities, 'notes': notes, 'cancelled': False, 'cancel_reason': ''}
                    save_doc('complimentary', doc | {'issuances': issuances + [item]}, f'Issuance recorded: {names[programme_id]}')
            if issuances:
                labels = {i['id']: f"{names.get(i['programme_id'], '?')} · {i['date']} · {i['recipient'] or 'no recipient'}" for i in issuances}
                key = st.selectbox('Edit or cancel an issuance', list(labels)[::-1], format_func=labels.get, key='comp_edit_issuance')
                item = next(i for i in issuances if i['id'] == key)
                with st.form('comp_issuance_' + key):
                    issued_on = st.date_input('Date issued', value=date.fromisoformat(item['date']), max_value=date.today())
                    recipient = st.text_input('Recipient or batch', item['recipient'])
                    quantities = quantity_editor('comp_quantities_' + key, item['quantities'])
                    notes = st.text_area('Notes', item.get('notes', ''))
                    cancelled = st.checkbox('Cancel this issuance (slots no longer count as utilized)', value=item.get('cancelled', False))
                    reason = st.text_input('Cancellation reason', item.get('cancel_reason', ''))
                    if st.form_submit_button('Save changes'):
                        updated = [i | {'date': issued_on.isoformat(), 'recipient': recipient.strip(), 'quantities': quantities,
                            'notes': notes, 'cancelled': cancelled, 'cancel_reason': reason.strip()} if i['id'] == key else i for i in issuances]
                        save_doc('complimentary', doc | {'issuances': updated}, 'Issuance updated: ' + labels[key])

    with activity:
        if issuances:
            log = pd.DataFrame([{'Date': i['date'], 'Programme': names.get(i['programme_id'], '?'), 'Recipient': i['recipient'],
                'Places': sum(i['quantities'].values()), 'Cancelled': i.get('cancelled', False), 'Notes': i.get('notes', ''),
                **{c: i['quantities'].get(c, 0) for c in PLANNING_CATEGORIES}} for i in issuances]).sort_values('Date', ascending=False)
            st.dataframe(log, hide_index=True, width='stretch')
            st.download_button('Download issuance log', log.to_csv(index=False), 'complimentary-issuances.csv', 'text/csv')
        else:
            st.info('No issuances recorded yet.')
