"""Promo-code campaigns: detected or created, their registrations and when they ran."""
from __future__ import annotations

import uuid
from datetime import date

import pandas as pd
import streamlit as st

from planning.campaign_codes import read_code_file
from planning.campaign_detection import (AUTO_NOTE, MIN_AUTO_REGISTRATIONS, campaign_activity, detect_code_groups,
    merge_campaigns, suggest_merges)
from planning.metrics import registrations_by_subgroup
from planning.categories import PLANNING_CATEGORIES
from views.common import needs_upload, registration_dates, save_doc, target_strip


def _iso(value):
    return value.isoformat() if value else None


def _date(value):
    return date.fromisoformat(value) if value else None


def _day(value):
    return None if pd.isna(value) else pd.Timestamp(value).date()


def render_campaigns(ctx):
    st.subheader('Campaigns')
    target_strip(ctx, 'Campaign')
    doc = ctx['docs']['campaigns']
    campaigns = doc['campaigns']
    names = {c['id']: c['name'] for c in campaigns}
    attributed = ctx['attributed']
    dates = registration_dates(ctx['data'])
    overview, manage, codes_tab, detected_tab = st.tabs(['Overview', 'Campaigns', 'Codes', 'Detected codes'])

    with overview:
        if not campaigns:
            st.info(f'No campaigns yet. Upload the registration CSV: promo codes used {MIN_AUTO_REGISTRATIONS}+ times are saved as campaigns automatically, or create one under Campaigns.')
        else:
            for suggestion in suggest_merges(campaigns):
                with st.container(border=True):
                    st.markdown(f"**Possible merge — {suggestion['prefix']} family:** {', '.join(suggestion['campaigns'])} share the same code family.")
                    merged_name = st.text_input('Merged campaign name', suggestion['prefix'], key='merge_name_' + suggestion['prefix'])
                    if st.button(f"Merge {len(suggestion['ids'])} campaigns", key='merge_' + suggestion['prefix']):
                        save_doc('campaigns', doc | {'campaigns': merge_campaigns(campaigns, suggestion['ids'], merged_name.strip())},
                            f"Merged {', '.join(suggestion['campaigns'])} into {merged_name.strip()}")
            activity = None
            if attributed is not None:
                matrix = registrations_by_subgroup(attributed, dates, 'Campaign')
                if not matrix.empty:
                    ranked = matrix.drop(index='Total')
                    a, b, c = st.columns(3)
                    a.metric('Campaign registrations', f"{int(matrix.loc['Total', 'Total']):,}")
                    b.metric('Campaigns with sign-ups', f'{len(ranked):,}')
                    c.metric('Most sign-ups', ranked.index[0], f"{int(ranked['Total'].iloc[0]):,} registrations", delta_color='off')
                    st.markdown('#### Registrations by campaign and category')
                    st.dataframe(matrix, width='stretch')
                    st.download_button('Download campaign × category table', matrix.to_csv(), 'campaign-registrations.csv', 'text/csv')
                activity = campaign_activity(attributed['Campaign'], dates).set_index('Campaign')
            table = []
            for c in campaigns:
                active = activity.loc[c['name']] if activity is not None and c['name'] in activity.index else None
                uses = None if activity is None else int(active['Code uses']) if active is not None else 0
                table.append({'Campaign': c['name'], 'Source': 'Auto' if c.get('auto') else 'Manual', 'Codes': len(c['codes']),
                    'Start (first use)': None if active is None else _day(active['First registered']),
                    'End (last use)': None if active is None else _day(active['Last registered']),
                    'Code uses': uses, 'Last 7 days': None if activity is None else int(active['Last 7 days']) if active is not None else 0,
                    'Cap': c.get('cap'), 'Uses left': c['cap'] - uses if c.get('cap') is not None and uses is not None else None,
                    'Planned start': c.get('start'), 'Planned end': c.get('end')})
            st.markdown('#### Campaign details')
            st.dataframe(pd.DataFrame(table).sort_values('Code uses', ascending=False, na_position='last'), hide_index=True, width='stretch')
            st.caption('Start/End are the first and last registrations using the campaign codes, so they show when a campaign actually ran. '
                'Code uses counts every use; the category table counts each participant once (people also tagged corporate or complimentary stay in that group).')
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

    with detected_tab:
        if not needs_upload(ctx):
            claimed = {code for c in campaigns for code in c['codes']}
            groups = detect_code_groups(attributed['Promo Code'], dates, claimed)
            st.caption(f'Promo codes in this upload that no campaign claims. Codes sharing their leading letters form a family '
                f'(RGSIM1, RG-SIM-2 → RGSIM); a lone code keeps its own name. Groups with {MIN_AUTO_REGISTRATIONS}+ registrations '
                'become campaigns automatically; add smaller ones here.')
            if groups.empty:
                st.success('Every promo code in this upload belongs to a campaign.')
            else:
                shown = groups.assign(**{'Codes': groups['Codes'].map(', '.join),
                    'First registered': groups['First registered'].map(_day), 'Last registered': groups['Last registered'].map(_day)})
                st.dataframe(shown, hide_index=True, width='stretch')
                st.download_button('Download detected codes', shown.to_csv(index=False), 'detected-codes.csv', 'text/csv')
                chosen = st.multiselect('Groups to act on', groups['Prefix'].tolist(), key='detected_chosen')
                picked = groups[groups['Prefix'].isin(chosen)]
                left, right = st.columns(2)
                if left.button('Create one campaign per group', disabled=picked.empty, key='detected_create'):
                    existing = {c['name'].casefold() for c in campaigns}
                    new = [{'id': uuid.uuid4().hex, 'name': name if name.casefold() not in existing else f'{name} (auto)', 'type': 'shared',
                        'codes': codes, 'cap': None, 'start': None, 'end': None, 'notes': AUTO_NOTE, 'auto': True, 'prefix': prefix}
                        for prefix, name, codes in zip(picked['Prefix'], picked['Suggested name'], picked['Codes'])]
                    save_doc('campaigns', doc | {'campaigns': campaigns + new}, 'Campaigns created from detected codes: ' + ', '.join(chosen))
                if campaigns:
                    target = right.selectbox('…or add their codes to', list(names), format_func=names.get, key='detected_target')
                    if right.button('Add codes to this campaign', disabled=picked.empty, key='detected_add'):
                        codes = [code for group_codes in picked['Codes'] for code in group_codes]
                        updated = [c | {'codes': list(dict.fromkeys(c['codes'] + codes))} if c['id'] == target else c for c in campaigns]
                        save_doc('campaigns', doc | {'campaigns': updated}, f'{len(codes)} detected codes added to {names[target]}')
