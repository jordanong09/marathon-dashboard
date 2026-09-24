"""Shared loading, saving and target display for the planning pages."""
from __future__ import annotations

import copy

import pandas as pd
import streamlit as st

import doc_store
import sales_backend
from planning.attribution import attribute, clean_codes
from planning.campaign_detection import absorb_detected, detect_code_groups
from planning.categories import PLANNING_CATEGORIES
from planning.company_matching import link_registration_names
from planning.complimentary_tags import absorb_new_tags
from planning.metrics import capacity_series, plan_matrix, utilized_matrix

DOCUMENTS = ('plan', 'complimentary', 'campaigns', 'corporate')


def sales_path():
    return doc_store.DATA_DIR / 'corporate_sales.json'


def _read(name):
    return sales_backend.read_store(sales_path()) if name == 'corporate' else doc_store.read(name)


def get_doc(name):
    """Session snapshot of a saved document (deep copy, safe to edit)."""
    key = 'doc_snapshot_' + name
    if key not in st.session_state:
        st.session_state[key] = _read(name)
    return copy.deepcopy(st.session_state[key])


def save_doc(name, data, action):
    """Save and rerun on success; show the error and return on failure."""
    try:
        if name == 'corporate':
            saved = sales_backend.save_store(sales_path(), data, data['revision'], action)
        else:
            saved = doc_store.save(name, data, data['revision'], action)
    except (ValueError, OSError) as error:
        st.error(f'Not saved: {error}')
        return
    st.session_state['doc_snapshot_' + name] = saved
    st.session_state['saved_notice'] = f'{action} — saved to {sales_backend.storage_label()}.'
    st.rerun()


def show_saved_notice():
    if 'saved_notice' in st.session_state:
        st.success(st.session_state.pop('saved_notice'))


def reload_button(key):
    if st.button('Reload saved records', key=key, help='Fetch the latest records saved by other users.'):
        for name in DOCUMENTS:
            st.session_state.pop('doc_snapshot_' + name, None)
        st.rerun()


def storage_banner():
    if sales_backend.storage_label() == 'Supabase':
        st.caption('Storage: Supabase')
    else:
        st.warning('Local storage — not for real data. Records are saved on this computer only.')


def planning_context(data, promo_column):
    """Load every document and compute plan/utilized matrices, or show an error and return None."""
    try:
        docs = {name: get_doc(name) for name in DOCUMENTS}
    except (ValueError, OSError) as error:
        st.error(f'Cannot read saved planning records: {error}. Nothing has been changed.')
        return None
    sales, comp, campaigns = docs['corporate'], docs['complimentary'], docs['campaigns']
    company_names = {company['id']: company['name'] for company in sales['companies']}
    registration_names = [] if data is None else sorted(data['Corporate Group'].dropna().astype(str).loc[lambda s: s.str.strip().ne('')].unique())
    links = link_registration_names(sales['companies'], registration_names)
    aliases = {alias.casefold(): company['name'] for company in sales['companies'] for alias in company['aliases']}
    aliases |= {name.casefold(): company_names[company_id] for name, (company_id, _) in links.items()}
    if data is not None:
        comp = docs['complimentary'] = capture_complimentary_tags(comp, data)
        if promo_column:
            campaigns = docs['campaigns'] = capture_campaign_codes(campaigns, data, promo_column)
    tags = {tag.casefold(): programme['name'] for programme in comp['programmes'] for tag in programme['tags']}
    codes = {code: campaign['name'] for campaign in campaigns['campaigns'] for code in campaign['codes']}
    attributed = None if data is None else attribute(data, promo_column, aliases, tags, codes)
    return {'docs': docs, 'data': data, 'promo_column': promo_column, 'attributed': attributed, 'corporate_links': links,
        'plan': plan_matrix(docs['plan']), 'capacity': capacity_series(docs['plan']),
        'utilized': utilized_matrix(sales['orders'], comp['issuances'], attributed)}


def capture_complimentary_tags(comp, data):
    """Save complimentary tags seen in the upload as programmes; keep the saved ones untouched."""
    found = data['Complimentary Programme'].dropna().astype(str).tolist() if 'Complimentary Programme' in data else []
    programmes, added, attached = absorb_new_tags(comp['programmes'], found)
    if not added and not attached:
        return comp
    changed = comp | {'programmes': programmes}
    action = 'Captured complimentary tags from upload: ' + ', '.join(added + attached)
    try:
        saved = doc_store.save('complimentary', changed, comp['revision'], action)
    except (ValueError, OSError) as error:
        st.warning(f'New complimentary tags found ({", ".join(added + attached)}) but not saved: {error} They are counted for this session only.')
        return changed
    st.session_state['doc_snapshot_complimentary'] = saved
    parts = [f'{len(added)} new complimentary programme(s) added: {", ".join(added)}'] if added else []
    parts += [f'{len(attached)} tag(s) linked to existing programmes: {", ".join(attached)}'] if attached else []
    st.success(' · '.join(parts) + '. Saved from this registration upload.')
    return saved


def registration_dates(data):
    if data is None or 'Registration Date Only' not in data:
        return pd.Series(pd.NaT, index=None if data is None else data.index)
    return data['Registration Date Only']


def capture_campaign_codes(campaigns, data, promo_column):
    """Save promo-code groups with enough registrations as automatic campaigns; extend existing ones."""
    claimed = {code for campaign in campaigns['campaigns'] for code in campaign['codes']}
    groups = detect_code_groups(clean_codes(data[promo_column]), registration_dates(data), claimed)
    updated, created, extended = absorb_detected(campaigns['campaigns'], groups)
    if not created and not extended:
        return campaigns
    changed = campaigns | {'campaigns': updated}
    action = 'Detected campaigns from upload: ' + ', '.join(created + extended)
    try:
        saved = doc_store.save('campaigns', changed, campaigns['revision'], action)
    except (ValueError, OSError) as error:
        st.warning(f'Campaign codes detected ({", ".join(created + extended)}) but not saved: {error} They are counted for this session only.')
        return changed
    st.session_state['doc_snapshot_campaigns'] = saved
    parts = [f'{len(created)} new campaign(s) detected: {", ".join(created)}'] if created else []
    parts += [f'new codes added to: {", ".join(dict.fromkeys(extended))}'] if extended else []
    st.success(' · '.join(parts) + '. Saved from this registration upload.')
    return saved


def fmt(value):
    return '—' if pd.isna(value) else f'{value:,.0f}'


def _negative(value):
    return 'color:#B42318;background-color:#FFF0ED' if isinstance(value, (int, float)) and pd.notna(value) and value < 0 else ''


def style_numbers(frame, formatters=None):
    """Display text (st.dataframe shows missing values as 'None' otherwise) with negatives in red."""
    formatters = formatters or {}
    text = frame.apply(lambda column: column.map(formatters.get(column.name, fmt)))
    return text.style.apply(lambda _: frame.map(_negative), axis=None)


def pct(value):
    return '—' if pd.isna(value) else f'{value:.0f}%'


def target_strip(ctx, group):
    """Plan / utilized / remaining for one group, per planning category."""
    plan, utilized = ctx['plan'].loc[group], ctx['utilized'].loc[group]
    frame = pd.DataFrame({'Plan': plan, 'Utilized': utilized, 'Remaining': plan - utilized}).T
    frame['Total'] = frame.sum(axis=1, min_count=1)
    a, b, c = st.columns(3)
    a.metric(f'{group} plan', fmt(frame.loc['Plan', 'Total']))
    b.metric('Utilized', fmt(frame.loc['Utilized', 'Total']))
    c.metric('Remaining', fmt(frame.loc['Remaining', 'Total']))
    st.dataframe(style_numbers(frame), width='stretch')
    if not frame.loc['Plan', 'Total']:
        st.caption('No plan allocation for this group yet. The executive sets it in Plan Allocation.')


def quantity_editor(key, quantities=None):
    """Editable Places per planning category; returns {category: int}."""
    quantities = quantities or {}
    frame = pd.DataFrame({'Category': PLANNING_CATEGORIES, 'Places': [int(quantities.get(c, 0)) for c in PLANNING_CATEGORIES]})
    edited = st.data_editor(frame, key=key, disabled=['Category'], hide_index=True, width='stretch',
        column_config={'Places': st.column_config.NumberColumn(min_value=0, step=1, required=True)})
    return {category: int(value) for category, value in zip(edited.Category, edited.Places.fillna(0))}


def needs_upload(ctx):
    if ctx['data'] is None:
        st.info('Upload the registration CSV in the sidebar to see registrations here.')
        return True
    return False
