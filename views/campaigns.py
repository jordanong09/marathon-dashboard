"""Promo-code campaigns: shared or unique codes, registrations and unmatched codes."""
from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from planning.campaign_codes import read_code_file
from planning.categories import PLANNING_CATEGORIES
from planning.metrics import unmatched_codes
from views.common import needs_upload, save_doc, target_strip

PROMO_FOLDER = Path(__file__).resolve().parent.parent / 'promo_lists'


def _iso(value):
    return value.isoformat() if value else None


def _date(value):
    return date.fromisoformat(value) if value else None


def seed_campaigns():
    """Build unique-code campaigns from the legacy promo_lists folder (one-time import)."""
    campaigns = []
    for file in sorted(PROMO_FOLDER.glob('*.xlsx')):
        parsed = read_code_file(file.name, file.read_bytes())
        campaigns.append({'id': uuid.uuid4().hex, 'name': file.stem, 'type': 'unique', 'codes': parsed['codes'],
            'cap': parsed['cap'], 'start': None, 'end': parsed['end'], 'notes': 'Imported from promo_lists'})
    return campaigns


def render_campaigns(ctx):
    st.subheader('Campaigns')
    target_strip(ctx, 'Campaign')
    doc = ctx['docs']['campaigns']
    campaigns = doc['campaigns']
    names = {c['id']: c['name'] for c in campaigns}
    attributed = ctx['attributed']
    overview, manage, codes_tab, unmatched_tab = st.tabs(['Overview', 'Campaigns', 'Codes', 'Unmatched codes'])

    with overview:
        if not campaigns:
            st.info('No campaigns yet. Create one under Campaigns.')
            if PROMO_FOLDER.exists() and any(PROMO_FOLDER.glob('*.xlsx')) and st.button('Import existing KL Half code lists (one-time)'):
                try:
                    seeded = seed_campaigns()
                except (ValueError, OSError, KeyError) as error:
                    st.error(f'Import failed: {error}')
                else:
                    save_doc('campaigns', doc | {'campaigns': seeded}, 'Imported promo_lists campaigns')
        else:
            registered = None
            if attributed is not None:
                rows = attributed[attributed['Group'].eq('Campaign')]
                registered = pd.crosstab(rows['Subgroup'], rows['Planning Category']).reindex(columns=PLANNING_CATEGORIES, fill_value=0)
            table = []
            for c in campaigns:
                counts = registered.loc[c['name']] if registered is not None and c['name'] in registered.index else None
                total = None if registered is None else int(counts.sum()) if counts is not None else 0
                table.append({'Campaign': c['name'], 'Type': c['type'], 'Codes': len(c['codes']), 'Cap': c.get('cap'),
                    'Registrations': total, 'Uses left': c['cap'] - total if c.get('cap') is not None and total is not None else None,
                    'Starts': c.get('start'), 'Closes': c.get('end'),
                    **{cat: (None if registered is None else int(counts[cat]) if counts is not None else 0) for cat in PLANNING_CATEGORIES}})
            st.dataframe(pd.DataFrame(table), hide_index=True, width='stretch')
            st.caption('Registrations count once per participant. Participants also tagged corporate or complimentary stay in that group and are listed as conflicts in the Executive Summary.')
            needs_upload(ctx)

    with manage:
        with st.form('campaign_new', clear_on_submit=True):
            st.markdown('**Create campaign**')
            name = st.text_input('Campaign name', placeholder='Early Bird')
            kind = st.radio('Code type', ['shared', 'unique'], horizontal=True,
                format_func={'shared': 'Shared code(s) — e.g. EARLYBIRD', 'unique': 'Unique codes — upload a list'}.get)
            start = st.date_input('Start date (optional)', value=None)
            end = st.date_input('End date (optional)', value=None)
            cap = st.number_input('Cap on registrations (0 = no cap)', min_value=0, step=1)
            notes = st.text_area('Notes')
            if st.form_submit_button('Create campaign'):
                item = {'id': uuid.uuid4().hex, 'name': name.strip(), 'type': kind, 'codes': [], 'cap': int(cap) or None,
                    'start': _iso(start), 'end': _iso(end), 'notes': notes}
                save_doc('campaigns', doc | {'campaigns': campaigns + [item]}, 'Campaign created: ' + name.strip())
        if campaigns:
            key = st.selectbox('Edit campaign', list(names), format_func=names.get, key='campaign_edit')
            c = next(c for c in campaigns if c['id'] == key)
            with st.form('campaign_' + key):
                name = st.text_input('Campaign name', c['name'])
                start = st.date_input('Start date (optional)', value=_date(c.get('start')))
                end = st.date_input('End date (optional)', value=_date(c.get('end')))
                cap = st.number_input('Cap on registrations (0 = no cap)', min_value=0, step=1, value=c.get('cap') or 0)
                notes = st.text_area('Notes', c.get('notes', ''))
                delete = st.checkbox('Delete this campaign and its codes')
                if st.form_submit_button('Save campaign'):
                    if delete:
                        save_doc('campaigns', doc | {'campaigns': [x for x in campaigns if x['id'] != key]}, 'Campaign deleted: ' + c['name'])
                    else:
                        updated = [x | {'name': name.strip(), 'start': _iso(start), 'end': _iso(end), 'cap': int(cap) or None, 'notes': notes}
                            if x['id'] == key else x for x in campaigns]
                        save_doc('campaigns', doc | {'campaigns': updated}, 'Campaign updated: ' + name.strip())

    with codes_tab:
        if not campaigns:
            st.info('Create a campaign first.')
        else:
            key = st.selectbox('Campaign', list(names), format_func=names.get, key='campaign_codes')
            c = next(c for c in campaigns if c['id'] == key)
            st.caption(f"{len(c['codes']):,} codes · matching is exact and case-sensitive after trimming spaces.")
            if c['codes']:
                st.dataframe(pd.DataFrame({'Code': c['codes'][:500]}), hide_index=True, height=200)

            def replace_codes(new_codes, action, cap=None):
                updated = [x | {'codes': new_codes} | ({'cap': cap} if cap is not None and x.get('cap') is None else {})
                    if x['id'] == key else x for x in campaigns]
                save_doc('campaigns', doc | {'campaigns': updated}, action)

            if c['type'] == 'shared':
                with st.form('codes_add_' + key, clear_on_submit=True):
                    text = st.text_area('Add codes, one per line')
                    if st.form_submit_button('Add codes'):
                        new = [line.strip() for line in text.splitlines() if line.strip()]
                        replace_codes(list(dict.fromkeys(c['codes'] + new)), f"Codes added to {c['name']}")
            else:
                upload = st.file_uploader('Upload unique codes (.csv or .xlsx with a "Promo Code" column)', type=['csv', 'xlsx'], key='codes_file_' + key)
                if upload is not None:
                    try:
                        parsed = read_code_file(upload.name, upload.getvalue())
                    except (ValueError, KeyError) as error:
                        st.error(f'Cannot read this file: {error}')
                    else:
                        existing = set(c['codes'])
                        fresh = [code for code in parsed['codes'] if code not in existing]
                        st.write(f"{len(parsed['codes']):,} codes read · {len(fresh):,} new · {parsed['skipped']:,} blank or duplicate rows skipped"
                            + (f" · allowed uses in file: {parsed['cap']:,}" if parsed['cap'] is not None else ''))
                        if fresh and st.button(f'Add {len(fresh):,} codes', key='codes_upload_' + key):
                            replace_codes(c['codes'] + fresh, f"{len(fresh)} codes uploaded to {c['name']}", parsed['cap'])
            with st.form('codes_remove_' + key, clear_on_submit=True):
                text = st.text_area('Remove codes, one per line')
                remove_all = st.checkbox('Remove all codes from this campaign')
                if st.form_submit_button('Remove codes'):
                    drop = set(c['codes']) if remove_all else {line.strip() for line in text.splitlines()}
                    replace_codes([code for code in c['codes'] if code not in drop], f"Codes removed from {c['name']}")

    with unmatched_tab:
        if not needs_upload(ctx):
            table = unmatched_codes(attributed).rename_axis('Promo code').reset_index(name='Registrations')
            st.caption('Promo codes used in registrations that no campaign claims yet (e.g. Medic codes). Add them to a campaign to track them.')
            st.dataframe(table, hide_index=True, width='stretch')
            st.download_button('Download unmatched codes', table.to_csv(index=False), 'unmatched-codes.csv', 'text/csv')
