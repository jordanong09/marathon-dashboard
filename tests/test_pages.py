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


def test_app_without_upload_opens_executive_summary(local_store):
    app = AppTest.from_file('../app.py', default_timeout=60)
    app.run()
    assert not app.exception, app.exception
    assert any('Executive Summary' in s.value for s in app.subheader)
