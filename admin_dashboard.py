"""Dashboard styling, workspace navigation and chart rendering."""
from __future__ import annotations

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


SECTIONS = [
    ('PLANNING', [
        ('Executive Summary', 'space_dashboard', 'Plan, utilized and remaining by group and category'),
        ('Plan Allocation', 'tune', 'Category capacity and group allocations'),
    ]),
    ('STAKEHOLDERS', [
        ('Corporate Sales', 'business_center', 'Companies, orders, top-ups, payment milestones and utilization'),
        ('Complimentary', 'redeem', 'Complimentary programmes, slots issued and registrations'),
        ('Campaigns', 'campaign', 'Promo-code campaigns, codes and registrations'),
    ]),
    ('ANALYTICS', [
        ('Overview', 'dashboard', 'Registration totals, momentum and category performance'),
        ('Daily registration', 'monitoring', 'Daily trends, cumulative growth and registration timing'),
        ('Groups & complimentary', 'groups', 'Group registrations, complimentary programmes and add-ons'),
        ('Audience & markets', 'public', 'Participant demographics, countries and market mix'),
        ('Reports & data', 'description', 'Management exports, registration tracker and data quality'),
    ]),
]


def workspace_navigation():
    """Render grouped navigation tiles with an explicit selected state."""
    if 'workspace_page' not in st.session_state:
        st.session_state.workspace_page = 'Corporate Sales' if st.query_params.get('sales_view') else 'Executive Summary'

    def select_page(name):
        st.session_state.workspace_page = name
        if name != 'Corporate Sales':
            for key in ['sales_view', 'sales_order']:
                if key in st.query_params:
                    del st.query_params[key]

    with st.sidebar.container(key='workspace_navigation'):
        for heading, pages in SECTIONS:
            st.caption(heading)
            for name, icon, description in pages:
                st.button(name, icon=f':material/{icon}:', help=description,
                    type='primary' if st.session_state.workspace_page == name else 'secondary',
                    use_container_width=True, key='workspace_' + icon, on_click=select_page, args=(name,))
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
