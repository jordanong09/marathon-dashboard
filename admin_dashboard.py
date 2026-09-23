"""Registration administration, allocation scenarios and campaign discovery."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


def style_dashboard():
    st.markdown('''<style>
    .stApp {background:#F5F6F8;color:#20252B}
    .block-container {max-width:1480px;padding-top:2rem}
    [data-testid="stMetric"] {background:white;border:1px solid #DDE1E6;
      border-top:3px solid #E8402D;border-radius:8px;padding:16px;min-height:120px}
    [data-testid="stMetricLabel"] {color:#515B66}
    h1,h2,h3 {letter-spacing:-.025em}
    [data-testid="stSidebar"] {background:#FFFFFF}
    .event-header {display:flex;align-items:center;gap:32px;background:#fff;
      border:1px solid #E0E3E8;border-radius:18px;padding:18px 24px;
      border-left:5px solid #E8402D;margin-bottom:18px;box-shadow:0 8px 24px #20252B06}
    .event-header img {width:120px;height:auto;object-fit:contain;flex-shrink:0}
    .event-header-copy {border-left:1px solid #E4E7EC;padding-left:32px}
    .event-eyebrow {font-size:11px;letter-spacing:.14em;font-weight:700;color:#B62E22;margin-bottom:8px}
    .event-heading {font-size:28px;line-height:1.2;font-weight:750;color:#20252B}
    .event-subtitle {font-size:14px;color:#59636E;margin-top:8px}
    .event-dates {display:flex;flex-wrap:wrap;gap:8px 24px;font-size:12px;color:#59636E;margin-top:10px}
    .st-key-workspace_navigation {padding:8px 4px 20px}
    .st-key-workspace_navigation button {width:100%;min-height:44px;border-radius:14px;
      border:1px solid #E0E4EA;background:linear-gradient(145deg,#FAFBFC,#EDF0F4);
      color:#35404B;box-shadow:5px 5px 12px #D8DDE4,-5px -5px 12px #FFFFFF;
      justify-content:flex-start;padding:10px 14px;transition:box-shadow .16s,transform .16s,border-color .16s}
    .st-key-workspace_navigation button p {font-size:14px;font-weight:650;text-align:left}
    .st-key-workspace_navigation button:hover {border-color:#C83224;color:#A82C20;transform:translateY(-2px)}
    .st-key-workspace_navigation button[kind="primary"] {background:#FFF3EF;color:#A82C20;
      border:2px solid #C83224;box-shadow:inset 3px 3px 7px #EAD5CF,inset -3px -3px 7px #FFFFFF}
    .st-key-workspace_navigation button:focus-visible {outline:3px solid #263C59;outline-offset:4px}
    @media(max-width:700px) {.event-header {gap:18px;padding:20px;flex-wrap:wrap}
      .event-header img {width:145px}.event-header-copy {border-left:0;padding-left:0}
      .st-key-workspace_navigation button {min-height:64px;padding:12px}}
    @media(prefers-reduced-motion:reduce) {.st-key-workspace_navigation button {transition:none}}
    html,body,[data-testid="stAppViewContainer"],button,input {font-family:Inter,"Segoe UI",Arial,sans-serif}
    [data-testid="stMetricValue"] {font-variant-numeric:tabular-nums;font-size:32px}
    [data-testid="stSidebarContent"] {overflow-y:auto}
    .st-key-workspace_navigation {position:sticky;top:0;z-index:20;background:#fff;padding:8px 4px 16px}
    .st-key-workspace_navigation [data-testid="stVerticalBlock"] {gap:8px}
    [data-testid="stPlotlyChart"] {background:#fff;border-radius:12px;padding:0;margin:8px 0 24px;
      min-width:0;max-width:100%;box-sizing:border-box;box-shadow:0 0 0 1px #E2E6EB}
    [data-testid="stColumn"] {min-width:0}
    [data-testid="stMainBlockContainer"] {container-type:inline-size}
    @container (max-width:1000px) {
      [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stPlotlyChart"]) {flex-direction:column;align-items:stretch}
      [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stPlotlyChart"]) > [data-testid="stColumn"] {width:100%!important;flex:1 1 auto!important}
    }
    h3 {font-size:20px!important;margin-top:16px!important}
    @media(max-height:740px) {.st-key-workspace_navigation {position:static}}
    </style>''', unsafe_allow_html=True)


def clean_codes(series):
    values = series.fillna('').astype(str).str.strip()
    return values.mask(values.str.lower().isin(['', 'n/a', 'na', 'nan', 'none']), '')


@st.cache_data(show_spinner=False, max_entries=4)
def campaign_files(signature):
    records = []
    for filename, _mtime in signature:
        frame = pd.read_excel(filename, dtype=str)
        frame.columns = frame.columns.str.strip()
        if 'Promo Code' not in frame:
            raise ValueError(f'Missing Promo Code column: {Path(filename).name}')
        frame['Code'] = clean_codes(frame['Promo Code'])
        frame = frame[frame.Code.ne('')].drop_duplicates('Code')
        frame['Campaign'] = Path(filename).stem
        frame['Allowed uses'] = pd.to_numeric(frame['Usage'].str.split('/').str[-1].str.strip(), errors='coerce')
        frame['Closes'] = pd.to_datetime(frame['End date'], utc=True, errors='coerce').dt.tz_convert('Asia/Singapore').dt.tz_localize(None).dt.normalize()
        records.append(frame[['Code', 'Campaign', 'Allowed uses', 'Closes']])
    return pd.concat(records, ignore_index=True) if records else pd.DataFrame(columns=['Code','Campaign','Allowed uses','Closes'])


def allocation_summary(data, plans, groups):
    rows = []
    for _, plan in plans.iterrows():
        count = int(data['Grouped Category'].isin(groups[plan['Category']]).sum())
        capacity = int(plan['Capacity'])
        rows.append({'Category': plan['Category'], 'Registered': count, 'Capacity': capacity,
                     'Remaining': capacity-count, 'Utilization %': count/capacity*100 if capacity else None,
                     'Target': int(plan['Target']), 'Status': 'Over capacity' if capacity and count>capacity else ('Not configured' if not capacity else 'Within capacity')})
    return pd.DataFrame(rows)


def render_admin(data, promo_column, groups, defaults, close_date):
    st.subheader('Slots & campaign administration')
    st.caption('Allocation totals use the full uploaded file. Sidebar audience and date filters do not reduce capacity usage.')
    initial = pd.DataFrame([{'Category': name, 'Capacity': 0, 'Target': defaults.get(name) or 0} for name in groups])
    if 'allocation_plan' not in st.session_state:
        st.session_state.allocation_plan = initial
    with st.expander('Import saved allocation settings'):
        saved = st.file_uploader('Allocation settings JSON', type=['json'], key='allocation_import')
        if saved and st.button('Apply imported settings'):
            try:
                candidate = pd.DataFrame(json.loads(saved.getvalue()))
                if set(candidate.columns) != set(initial.columns) or candidate.Category.duplicated().any() or set(candidate.Category) != set(groups):
                    raise ValueError('Category names must match the current allocation table.')
                for col in ['Capacity','Target']:
                    values = pd.to_numeric(candidate[col], errors='raise')
                    if values.isna().any() or (values<0).any() or (values%1 != 0).any():
                        raise ValueError('Capacity and target must be non-negative whole numbers.')
                    candidate[col] = values.astype(int)
                st.session_state.allocation_plan = candidate
                st.session_state.pop('allocation_editor', None)
                st.success('Settings imported.')
            except (ValueError, TypeError, KeyError) as error:
                st.error(f'Cannot import settings: {error}')
    plan = st.data_editor(st.session_state.allocation_plan, hide_index=True, disabled=['Category'],
        column_config={c:st.column_config.NumberColumn(c,min_value=0,step=1,required=True) for c in ['Capacity','Target']}, key='allocation_editor')
    if st.button('Apply category settings for this session'):
        st.session_state.allocation_plan = plan.copy()
        st.session_state.pop('allocation_editor', None)
        st.rerun()
    st.caption('Capacity 0 means not configured. Targets are planning goals, separate from capacity. Crew Challenge uses Marathon capacity; the 1.6 km Kids Dash categories share a planning group.')
    st.download_button('Save allocation settings', plan.to_json(orient='records'), 'allocation-settings.json', 'application/json')
    summary = allocation_summary(data, plan, groups)
    dates = pd.to_datetime(data['Registration Date Only'])
    latest = dates.max()
    days = max(0, (close_date-latest).days) if pd.notna(latest) else 0
    forecasts = []
    for _, row in summary.iterrows():
        recent = data['Grouped Category'].isin(groups[row.Category]) & dates.ge(latest-pd.Timedelta(days=7)) & dates.lt(latest)
        forecasts.append(round(row.Registered + int(recent.sum())/7*days))
    summary['Projected at close'] = forecasts
    summary['Projected utilization %'] = summary['Projected at close']/summary.Capacity.replace(0,float('nan'))*100
    summary['Required per day'] = ((summary.Target-summary.Registered).clip(lower=0)/days).round(1) if days else None
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Registered in capacity groups',f'{summary.Registered.sum():,}')
    c2.metric('Configured capacity',f'{summary.Capacity.sum():,}')
    complete = summary.Capacity.gt(0).all()
    c3.metric('Overall utilization',f'{summary.Registered.sum()/summary.Capacity.sum()*100:.1f}%' if complete else 'Not configured')
    c4.metric('Projected at close',f'{sum(forecasts):,}')
    st.dataframe(summary, hide_index=True, use_container_width=True)
    st.caption('Slot forecast: seven complete calendar days before the latest export date, projected to registration close. This simple planning scenario is separate from the weekday-adjusted forecast in Overview. Allocation changes do not change demand. Missing capacity is never treated as zero availability.')
    render_chart(px.bar(summary, x='Registered', y='Category', orientation='h', color_discrete_sequence=['#E8402D']),use_container_width=True)
    st.download_button('Download slot analysis',summary.to_csv(index=False),'slot-analysis.csv','text/csv')

    st.markdown('### Complimentary & group allocations')
    parts = []
    for column in ['Complimentary Programme', 'Corporate Group']:
        if column in data:
            counts = data[column].dropna().value_counts()
            parts.extend({'Type':column,'Programme':name,'Registered':int(count),'Allocated':0} for name,count in counts.items() if str(name).strip())
    if parts:
        channel = st.data_editor(pd.DataFrame(parts),hide_index=True,disabled=['Type','Programme','Registered'],
            column_config={'Allocated':st.column_config.NumberColumn(min_value=0,step=1,required=True)},key='programme_allocations')
        channel['Remaining'] = (channel.Allocated-channel.Registered).where(channel.Allocated.gt(0))
        channel['Utilization %'] = (channel.Registered/channel.Allocated.replace(0,float('nan'))*100)
        st.dataframe(channel,hide_index=True,use_container_width=True)
        st.download_button('Download programme allocations',channel.to_csv(index=False),'programme-allocations.csv','text/csv')
        st.caption('Programme edits last for this session. Download the table for your records. Programme allocations are subsets of category capacity, not additional places.')

    st.markdown('### Promo codes & campaigns')
    if promo_column is None:
        st.info('Select a promo-code column to see campaign usage.')
        return
    codes = clean_codes(data[promo_column])
    folder = Path(__file__).parent/'promo_lists'
    signature = tuple((str(p),p.stat().st_mtime_ns) for p in sorted(folder.glob('*.xlsx')))
    try:
        issued = campaign_files(signature)
    except (ValueError,KeyError,OSError) as error:
        st.error(f'Campaign list could not be loaded: {error}')
        return
    a,b,c = st.columns(3)
    a.metric('Registrations with a code',f'{codes.ne("").sum():,}')
    b.metric('Unique codes used',f'{codes[codes.ne("")].nunique():,}')
    c.metric('Bundled campaigns',issued.Campaign.nunique())
    counts = codes[codes.ne('')].value_counts().rename_axis('Code').reset_index(name='Registered')
    if issued.Code.duplicated().any():
        st.warning('Some codes appear in multiple campaign lists. Campaign totals overlap; do not add them together.')
    mapped = issued.merge(counts,on='Code',how='left')
    mapped['Registered'] = mapped.Registered.fillna(0).astype(int)
    report=[]
    dates = pd.to_datetime(data['Registration Date Only'])
    latest = dates.max()
    for name, group in mapped.groupby('Campaign'):
        used = int(group.Registered.sum())
        slots = group['Allowed uses'].sum(min_count=len(group))
        deadline = group.Closes.min()
        matched = codes.isin(group.Code)
        recent = int((matched & dates.ge(latest-pd.Timedelta(days=7)) & dates.lt(latest)).sum()) if pd.notna(latest) else 0
        days = max(0,(deadline-latest).days) if pd.notna(deadline) and pd.notna(latest) else None
        projected = used+recent/7*days if days is not None else None
        report.append({'Campaign':name,'Issued codes':len(group),'Unique codes redeemed':int(group.Registered.gt(0).sum()),
          'Registered':used,'Allocated uses':slots,'Utilization %':used/slots*100 if slots else None,
          'Remaining uses':slots-used,'Projected registrations':round(projected) if projected is not None else None,
          'Projected utilization %':projected/slots*100 if projected is not None and slots else None,
          'Closes':deadline,'Overused codes':int(group.Registered.gt(group['Allowed uses']).sum())})
    st.dataframe(pd.DataFrame(report),hide_index=True,use_container_width=True)
    st.caption('Exact, case-sensitive code matching; add-on prices do not affect attribution. Forecasts use the seven calendar days before the latest export date and each campaign’s closing date. They assume the export covers those days and do not cap excess demand. Workbook Usage is an earlier snapshot, not added to registration counts.')
    unknown = counts[~counts.Code.isin(issued.Code)].copy()
    unknown['Allocated uses'] = 0
    with st.expander('Other codes — automatic discovery and allocation'):
        unknown = st.data_editor(unknown,hide_index=True,disabled=['Code','Registered'],column_config={'Allocated uses':st.column_config.NumberColumn(min_value=0,step=1,required=True)},key='other_code_allocations')
        unknown['Utilization %'] = unknown.Registered/unknown['Allocated uses'].replace(0,float('nan'))*100
        remaining_days = max(0,(close_date-latest).days) if pd.notna(latest) else 0
        recent_counts = codes[dates.ge(latest-pd.Timedelta(days=7)) & dates.lt(latest)].value_counts()
        unknown['Projected registrations'] = (unknown.Registered+unknown.Code.map(recent_counts).fillna(0)/7*remaining_days).round().astype(int)
        unknown['Projected utilization %'] = unknown['Projected registrations']/unknown['Allocated uses'].replace(0,float('nan'))*100
        st.caption('Other-code forecasts use the event registration deadline. For shorter promotions, use an issued-code workbook with its own closing date. Allocations remain in this page session; download before leaving.')
        st.dataframe(unknown,hide_index=True,use_container_width=True)
        st.download_button('Download discovered codes',unknown.to_csv(index=False),'discovered-codes.csv','text/csv')
    st.download_button('Download KL campaign analysis',pd.DataFrame(report).to_csv(index=False),'kl-campaign-analysis.csv','text/csv')


def workspace_navigation():
    """Render accessible icon tiles with an explicit selected state."""
    sections = [
        ("Corporate Sales", "business_center", "Saved companies, orders, top-ups, payment milestones and released allocations"),
        ("Management Slot Planning", "table_chart", "Draft allocation, actual registrations and remaining places by programme and category"),
        ("Overview", "dashboard", "Registration totals, momentum and category performance"),
        ("Daily registration", "monitoring", "Daily trends, cumulative growth and registration timing"),
        ("Slots & campaigns", "confirmation_number", "Capacity planning, promo codes and utilization"),
        ("Groups & complimentary", "groups", "Group registrations, complimentary programmes and add-ons"),
        ("Audience & markets", "public", "Participant demographics, countries and market mix"),
        ("Reports & data", "description", "Management exports, registration tracker and data quality"),
    ]
    if "workspace_page" not in st.session_state:
        st.session_state.workspace_page = "Corporate Sales" if st.query_params.get('sales_view') else "Overview"

    def select_page(name):
        st.session_state.workspace_page = name
        if name != 'Corporate Sales':
            for key in ['sales_view','sales_order']:
                if key in st.query_params:
                    del st.query_params[key]

    with st.sidebar.container(key="workspace_navigation"):
        st.caption("WORKSPACE")
        for name, icon, description in sections:
            active = st.session_state.workspace_page == name
            st.button(name, icon=f":material/{icon}:", help=description,
                type="primary" if active else "secondary", use_container_width=True,
                key="workspace_"+icon, on_click=select_page, args=(name,))
    return st.session_state.workspace_page


def render_chart(figure, **kwargs):
    """Render all charts against the available content width without CSS padding."""
    figure.update_layout(autosize=True, width=None)
    margin = figure.layout.margin
    figure.update_layout(margin=dict(l=max(margin.l or 0, 24),r=max(margin.r or 0, 40),
        t=max(margin.t or 0, 48),b=max(margin.b or 0, 48)))
    figure.update_xaxes(automargin=True)
    figure.update_yaxes(automargin=True)
    kwargs.pop('use_container_width',None)
    config = dict(kwargs.pop('config',{}) or {})
    config.update(responsive=True, displaylogo=False)
    return st.plotly_chart(figure, width='stretch', config=config, **kwargs)
