import pytest
from streamlit.testing.v1 import AppTest

PAGES = ['Executive Summary', 'Plan Allocation', 'Corporate Sales', 'Complimentary', 'Campaigns']


def page_script(page, with_data):
    import pandas as pd
    from views.router import render_planning_page
    data = None
    if with_data:
        data = pd.DataFrame({
            'Grouped Category': ['BYD Marathon', '5km', 'adidas Half Marathon', 'Kids Dash Non-Competitive 600m'],
            'Corporate Group': ['Acme', None, None, None],
            'Complimentary Programme': [None, 'KOL', None, None],
            'Market': ['Singapore', 'Singapore', 'International', 'Singapore'],
            'Promo': ['', '', 'EARLY', ''],
            'Registration Date Only': pd.to_datetime(['2026-09-01'] * 4),
        })
    render_planning_page(page, data, 'Promo' if with_data else None)


@pytest.mark.parametrize('page', PAGES)
@pytest.mark.parametrize('with_data', [False, True])
def test_page_renders(page, with_data, local_store):
    app = AppTest.from_function(page_script, args=(page, with_data), default_timeout=30)
    app.run()
    assert not app.exception, app.exception


def test_plan_save_persists_and_feeds_summary(local_store):
    import doc_store
    app = AppTest.from_function(page_script, args=('Plan Allocation', False), default_timeout=30)
    app.run()
    next(b for b in app.button if b.label == 'Save plan').click().run()
    assert not app.exception, app.exception
    assert doc_store.read('plan')['revision'] == 1
    assert any('Plan saved' in s.value for s in app.success)


def test_create_campaign_and_add_shared_code(local_store):
    import doc_store
    app = AppTest.from_function(page_script, args=('Campaigns', True), default_timeout=30)
    app.run()
    next(t for t in app.text_input if t.label == 'Campaign name').input('Early Bird')
    next(b for b in app.button if b.label == 'Create campaign').click().run()
    assert not app.exception, app.exception
    next(t for t in app.text_area if t.label == 'Add codes, one per line').input('EARLY\nEARLY2')
    next(b for b in app.button if b.label == 'Add codes').click().run()
    assert not app.exception, app.exception
    campaigns = doc_store.read('campaigns')['campaigns']
    assert campaigns[0]['name'] == 'Early Bird' and campaigns[0]['codes'] == ['EARLY', 'EARLY2']


def corporate_script():
    import pandas as pd
    from views.router import render_planning_page
    data = pd.DataFrame({
        'Grouped Category': ['BYD Marathon', '5km', '5km'],
        'Corporate Group': ['ACME', 'ACME', 'Globex'],
        'Complimentary Programme': [None, None, None],
        'Market': ['Singapore'] * 3,
        'Promo': [''] * 3,
    })
    render_planning_page('Corporate Sales', data, 'Promo')


def test_corporate_utilization_auto_matches_and_lists_every_company(local_store):
    import json
    import sales_store
    store = sales_store.new_store()
    store['companies'] = [{'id': 'c1', 'name': 'Acme Pte Ltd', 'aliases': []}]
    store['orders'] = [{'id': 'o1', 'company_id': 'c1', 'label': 'Initial order', 'workflow_version': 2, 'quantities': {'5 km': 4},
        'milestones': {'Links disseminated': '2026-09-01'}, 'completed_steps': {}, 'invoice': '', 'invoice_amount': 0.0, 'cancelled': False, 'notes': ''}]
    (local_store / 'corporate_sales.json').write_text(json.dumps(store), encoding='utf-8')
    app = AppTest.from_function(corporate_script, default_timeout=30)
    app.run()
    assert not app.exception, app.exception
    overview = next(d.value for d in app.dataframe if 'Matching' in d.value.columns).set_index('Company')
    assert overview.loc['Acme Pte Ltd', 'Matching'] == 'Auto-matched'
    assert overview.loc['Acme Pte Ltd', 'Registered'] == 2
    assert overview.loc['Acme Pte Ltd', 'Released'] == 4
    assert overview.loc['Globex', 'Matching'] == 'No sales record'
    grid = next(d.value for d in app.dataframe if d.value.index.name == 'Company')
    assert grid.loc['Acme Pte Ltd', '5 km'] == '1 / 4'
    assert grid.loc['Acme Pte Ltd', 'Full Marathon'] == '1 / 0'
    unused = next(d.value for d in app.dataframe if 'Unused' in d.value.columns)
    assert unused[['Company', 'Category', 'Unused']].values.tolist() == [['Acme Pte Ltd', '5 km', 3]]
    next(b for b in app.button if b.label.startswith('Confirm 1 suggested')).click().run()
    assert not app.exception, app.exception
    saved = json.loads((local_store / 'corporate_sales.json').read_text(encoding='utf-8'))
    assert saved['companies'][0]['aliases'] == ['ACME']


def corporate_no_upload_script():
    from views.router import render_planning_page
    render_planning_page('Corporate Sales', None, None)


def test_corporate_without_upload_says_so_and_allows_typed_links(local_store):
    import json
    import sales_store
    store = sales_store.new_store()
    store['companies'] = [{'id': 'c1', 'name': 'SUNWAY MCL LIMITED', 'aliases': []}]
    (local_store / 'corporate_sales.json').write_text(json.dumps(store), encoding='utf-8')
    app = AppTest.from_function(corporate_no_upload_script, default_timeout=30)
    app.run()
    assert not app.exception, app.exception
    assert any('No registration data in this session' in w.value for w in app.warning)
    overview = next(d.value for d in app.dataframe if 'Matching' in d.value.columns)
    assert overview['Matching'].tolist() == ['Upload registrations']
    app.text_area(key='sales_aliases_typed_c1').input('SUNWAY MCL LTD\nSUNWAY MCL')
    next(b for b in app.button if b.label == 'Save registration matching').click().run()
    assert not app.exception, app.exception
    saved = json.loads((local_store / 'corporate_sales.json').read_text(encoding='utf-8'))
    assert saved['companies'][0]['aliases'] == ['SUNWAY MCL LTD', 'SUNWAY MCL']


def complimentary_script():
    import pandas as pd
    from views.router import render_planning_page
    data = pd.DataFrame({
        'Grouped Category': ['5km', '5km', 'BYD Marathon'],
        'Corporate Group': [None, None, None],
        'Complimentary Programme': ['KOL', 'Elite', 'Elite'],
        'Market': ['Singapore'] * 3,
        'Promo': [''] * 3,
    })
    render_planning_page('Complimentary', data, 'Promo')


def test_complimentary_tags_are_captured_saved_and_tracked(local_store):
    import doc_store
    comp = doc_store.read('complimentary')
    comp['programmes'] = [{'id': 'p1', 'name': 'KOL Programme', 'tags': ['KOL'], 'notes': ''}]
    comp['issuances'] = [{'id': 'i1', 'programme_id': 'p1', 'date': '2026-09-01', 'recipient': 'KOLs',
        'quantities': {'5 km': 2}, 'notes': '', 'cancelled': False, 'cancel_reason': ''}]
    doc_store.save('complimentary', comp, 0, 'seed')
    app = AppTest.from_function(complimentary_script, default_timeout=30)
    app.run()
    assert not app.exception, app.exception
    assert any('1 new complimentary programme(s) added: Elite' in s.value for s in app.success)
    saved = doc_store.read('complimentary')
    assert [p['name'] for p in saved['programmes']] == ['KOL Programme', 'Elite']
    assert len(saved['issuances']) == 1
    overview = next(d.value for d in app.dataframe if 'Programme' in d.value.columns and 'Tags' in d.value.columns).set_index('Programme')
    assert overview.loc['KOL Programme', ['Issued', 'Registered', 'Status']].tolist() == [2, 1, 'Awaiting registrations']
    assert overview.loc['Elite', ['Issued', 'Registered', 'Status']].tolist() == [0, 2, 'No issuance recorded']
    rerun = AppTest.from_function(complimentary_script, default_timeout=30)
    rerun.run()
    assert not rerun.exception and not rerun.success
    assert doc_store.read('complimentary')['revision'] == saved['revision']


def campaign_detection_script():
    import pandas as pd
    from views.router import render_planning_page
    codes = ['EARLY10'] * 3 + ['EARLY20'] * 3 + ['MEDIC1'] * 2 + ['']
    data = pd.DataFrame({
        'Grouped Category': ['5km'] * len(codes),
        'Corporate Group': [None] * len(codes),
        'Complimentary Programme': [None] * len(codes),
        'Market': ['Singapore'] * len(codes),
        'Promo': codes,
        'Registration Date Only': pd.to_datetime(['2026-05-01', '2026-05-02', '2026-09-20', '2026-09-21', '2026-09-22', '2026-09-23',
            '2026-06-01', '2026-06-02', '2026-09-23']),
    })
    render_planning_page('Campaigns', data, 'Promo')


def test_campaigns_are_detected_dated_and_small_groups_can_be_added(local_store):
    import doc_store
    app = AppTest.from_function(campaign_detection_script, default_timeout=30)
    app.run()
    assert not app.exception, app.exception
    assert any('1 new campaign(s) detected: EARLY' in s.value for s in app.success)
    saved = doc_store.read('campaigns')['campaigns']
    assert [(c['name'], sorted(c['codes']), c['auto']) for c in saved] == [('EARLY', ['EARLY10', 'EARLY20'], True)]
    overview = next(d.value for d in app.dataframe if 'Source' in d.value.columns).set_index('Campaign')
    assert overview.loc['EARLY', ['Registrations', 'Last 7 days']].tolist() == [6, 4]
    assert str(overview.loc['EARLY', 'First registered']) == '2026-05-01'
    assert str(overview.loc['EARLY', 'Last registered']) == '2026-09-23'
    detected = next(d.value for d in app.dataframe if 'Prefix' in d.value.columns)
    assert detected['Prefix'].tolist() == ['MEDIC'] and detected['Registrations'].tolist() == [2]
    app.multiselect(key='detected_chosen').select('MEDIC')
    app.button(key='detected_create').click().run()
    assert not app.exception, app.exception
    assert [c['name'] for c in doc_store.read('campaigns')['campaigns']] == ['EARLY', 'MEDIC']


def summary_pace_script():
    import pandas as pd
    from views.router import render_planning_page
    days = [d for d in pd.date_range('2026-09-10', '2026-09-23') for _ in range(3)]
    data = pd.DataFrame({
        'Grouped Category': ['BYD Marathon'] * len(days),
        'Corporate Group': [None] * len(days),
        'Complimentary Programme': [None] * len(days),
        'Market': ['Singapore'] * len(days),
        'Promo': [''] * len(days),
        'Registration Date Only': pd.to_datetime(days + [pd.Timestamp('2026-09-24')])[:len(days)],
    })
    data = pd.concat([data, data.head(1).assign(**{'Registration Date Only': pd.Timestamp('2026-09-24')})], ignore_index=True)
    render_planning_page('Executive Summary', data, 'Promo')


def test_executive_summary_shows_recommendations_and_pace(local_store):
    import doc_store
    plan = doc_store.read('plan')
    plan['allocation']['Local Retail']['Full Marathon'] = 40
    plan['allocation']['Corporate']['Full Marathon'] = 100
    doc_store.save('plan', plan, 0, 'seed')
    app = AppTest.from_function(summary_pace_script, default_timeout=30)
    app.run()
    assert not app.exception, app.exception
    messages = [m.value for m in [*app.success, *app.warning, *app.info]]
    assert any(m.startswith('**Momentum: Local Retail**') for m in messages)
    assert any(m.startswith('**Behind plan: Corporate**') for m in messages)
    assert any(m.startswith('**Allocate Full Marathon**') for m in messages)
    pace = next(d.value for d in app.dataframe if 'Projected at close' in d.value.columns)
    assert pace.loc['Local Retail', 'Last 7 days'] == '21' and pace.loc['Local Retail', 'Status'] == 'Ahead of plan'


SAMPLE_CSV = '''Registration Date,Current Age,Gender,Country,Category Name,Group/Corporate Name,Promo Code - Code
01/09/2026 10:00,34,Male,Singapore,BYD Marathon (42.195KM),GROUP_REGISTRATION_Acme Batch 1 - Tan,
02/09/2026 11:00,28,Female,Malaysia,adidas Half Marathon (21.1KM),,EARLY
03/09/2026 12:00,41,Female,Singapore,5km Fun Run,COMPLIMENTARY_KOL,
04/09/2026 13:00,9,Male,Singapore,Kids Dash Non-Competitive 600m,,
05/09/2026 14:00,30,Male,Japan,Standard Chartered 10km,,MEDIC1
06/09/2026 09:00,45,Female,Australia,BYD Marathon Crew Challenge,,
07/09/2026 09:30,37,Male,India,5km Fun Run,,
08/09/2026 10:30,52,Female,Indonesia,adidas Half Marathon (21.1KM),,
09/09/2026 11:30,26,Male,Philippines,Standard Chartered 10km,,
10/09/2026 12:30,12,Female,Singapore,Kids Dash Competitive 1.6KM,,
'''


def full_app_script(page, csv_text):
    import runpy
    from pathlib import Path
    import streamlit as st
    from streamlit.proto.Common_pb2 import FileURLs
    from streamlit.runtime.uploaded_file_manager import UploadedFile, UploadedFileRec

    upload = UploadedFile(UploadedFileRec('sample', 'registrations.csv', 'text/csv', csv_text.encode()), FileURLs())
    st.session_state.setdefault('workspace_page', page)
    st.sidebar.file_uploader = lambda *args, **kwargs: upload
    runpy.run_path(str(Path('app.py').resolve()), run_name='__main__')


@pytest.mark.parametrize('page', PAGES + ['Overview', 'Daily registration', 'Groups & complimentary', 'Audience & markets', 'Reports & data'])
def test_full_app_with_upload(page, local_store, monkeypatch):
    from pathlib import Path
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    app = AppTest.from_function(full_app_script, args=(page, SAMPLE_CSV), default_timeout=120)
    app.run()
    assert not app.exception, app.exception
    assert not app.error, [e.value for e in app.error]
    assert app.subheader, 'page content did not render'
    if page in PAGES:
        assert app.subheader[0].value == page


def test_app_without_upload_opens_executive_summary(local_store):
    app = AppTest.from_file('../app.py', default_timeout=60)
    app.run()
    assert not app.exception, app.exception
    assert any('Executive Summary' in s.value for s in app.subheader)


FEW_COUNTRIES_CSV = '''Registration Date,Current Age,Gender,Country,Category Name,Group/Corporate Name,Promo Code - Code
01/09/2026 10:00,34,Male,Singapore,BYD Marathon (42.195KM),,
02/09/2026 11:00,28,Female,Malaysia,adidas Half Marathon (21.1KM),,
03/09/2026 12:00,41,Female,Japan,5km Fun Run,,
'''


def test_audience_page_with_five_or_fewer_countries(local_store, monkeypatch):
    from pathlib import Path
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    app = AppTest.from_function(full_app_script, args=('Audience & markets', FEW_COUNTRIES_CSV), default_timeout=120)
    app.run()
    assert not app.exception, app.exception
