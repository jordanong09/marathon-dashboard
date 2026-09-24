"""Complimentary programmes: tag links and registrations, with an optional log of slots given out."""
from __future__ import annotations

import uuid
from datetime import date

import pandas as pd
import streamlit as st

from planning.categories import PLANNING_CATEGORIES
from planning.metrics import registrations_by_subgroup, sum_quantities
from views.common import needs_upload, quantity_editor, registration_dates, save_doc, target_strip


def _status(issued, registered):
    if registered > issued:
        return 'Registered above issued'
    return 'Fully registered' if registered == issued else 'Awaiting registrations'


def _merge_tags(selected, typed):
    return list(dict.fromkeys([*selected, *(line.strip() for line in typed.splitlines() if line.strip())]))


def _without_tags(programmes, tags, keep=None):
    """Remove these tags from every other programme so a tag is moved, never linked twice."""
    moving = {tag.casefold() for tag in tags}
    return [p if p['id'] == keep else p | {'tags': [t for t in p['tags'] if t.casefold() not in moving]} for p in programmes]


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
    all_tags = sorted({*found, *(tag for p in programmes for tag in p['tags'])}, key=str.casefold)
    overview, manage, issue, activity = st.tabs(['Overview', 'Programmes', 'Slots given out (optional)', 'Activity'])

    with overview:
        if not programmes:
            st.info('No programmes yet. Upload the registration CSV: every COMPLIMENTARY_ tag in it is saved as a programme automatically.')
        if unlinked:
            st.warning(f'{len(unlinked)} complimentary tags in the registration data are not linked to a programme: {", ".join(unlinked)}')
        if not needs_upload(ctx):
            table = registrations_by_subgroup(ctx['attributed'], registration_dates(data), 'Complimentary')
            if table.empty:
                st.info('No registrations in this upload carry a COMPLIMENTARY_ tag.')
            else:
                ranked = table.drop(index='Total')
                a, b, c = st.columns(3)
                a.metric('Complimentary registrations', f"{int(table.loc['Total', 'Total']):,}")
                b.metric('Programmes with sign-ups', f'{len(ranked):,}')
                c.metric('Most sign-ups', ranked.index[0], f"{int(ranked['Total'].iloc[0]):,} registrations", delta_color='off')
                st.markdown('#### Registrations by programme and category')
                st.dataframe(table, width='stretch')
                st.caption('Complimentary utilization = registrations carrying the programme tag. Programmes are sorted by total sign-ups; '
                    'Last 7 days ends on the latest registration date.')
                st.download_button('Download programme × category table', table.to_csv(), 'complimentary-registrations.csv', 'text/csv')
                if issuances:
                    rows = []
                    for p in programmes:
                        issued = int(sum_quantities([i for i in issuances if i['programme_id'] == p['id']]).sum())
                        if issued:
                            registered = int(table.loc[p['name'], 'Total']) if p['name'] in table.index else 0
                            rows.append({'Programme': p['name'], 'Slots given out': issued, 'Registered': registered,
                                'Registered %': registered / issued * 100, 'Status': _status(issued, registered)})
                    if rows:
                        with st.expander('Slots given out vs registered (optional log)'):
                            st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch',
                                column_config={'Registered %': st.column_config.NumberColumn(format='%.0f%%')})

    with manage:
        with st.form('comp_new_programme', clear_on_submit=True):
            st.markdown('**Add programme**')
            name = st.text_input('Programme name')
            tags = st.multiselect('Registration tags (COMPLIMENTARY_…)', unlinked, help='Tags found in the uploaded registration data.')
            typed = st.text_area('Or type tags, one per line', help='The text after COMPLIMENTARY_, e.g. KOL for COMPLIMENTARY_KOL.', key='comp_new_typed')
            notes = st.text_area('Notes')
            if st.form_submit_button('Add programme'):
                tags = _merge_tags(tags, typed)
                changed = doc | {'programmes': _without_tags(programmes, tags) + [{'id': uuid.uuid4().hex, 'name': name.strip(), 'tags': tags, 'notes': notes}]}
                save_doc('complimentary', changed, 'Programme added: ' + name.strip())
        if programmes:
            key = st.selectbox('Edit programme', list(names), format_func=names.get, key='comp_edit_programme')
            programme = next(p for p in programmes if p['id'] == key)
            has_issuances = any(i['programme_id'] == key for i in issuances)
            with st.form('comp_programme_' + key):
                name = st.text_input('Programme name', programme['name'])
                tags = st.multiselect('Registration tags', all_tags, default=programme['tags'],
                    help='Choosing a tag that belongs to another programme moves it here.')
                typed = st.text_area('Add tags by typing, one per line', key='comp_edit_typed_' + key)
                notes = st.text_area('Notes', programme.get('notes', ''))
                delete = st.checkbox('Delete this programme', disabled=has_issuances,
                    help='Only programmes without recorded issuances can be deleted. Its tags are captured again on the next upload unless you move them to another programme first.')
                if st.form_submit_button('Save programme'):
                    if delete:
                        save_doc('complimentary', doc | {'programmes': [p for p in programmes if p['id'] != key]}, 'Programme deleted: ' + programme['name'])
                    else:
                        tags = _merge_tags(tags, typed)
                        updated = [p | {'name': name.strip(), 'tags': tags, 'notes': notes} if p['id'] == key else p for p in _without_tags(programmes, tags, keep=key)]
                        save_doc('complimentary', doc | {'programmes': updated}, 'Programme updated: ' + name.strip())

    with issue:
        if not programmes:
            st.info('Add a programme first.')
        else:
            with st.form('comp_new_issuance', clear_on_submit=True):
                st.markdown('**Record slots given out** (optional — utilization counts registrations)')
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
