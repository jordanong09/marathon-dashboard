import pandas as pd

from planning.attribution import attribute, clean_codes


def frame(**columns):
    size = len(next(iter(columns.values())))
    base = {'Grouped Category': ['BYD Marathon'] * size, 'Corporate Group': [None] * size,
        'Complimentary Programme': [None] * size, 'Market': ['Singapore'] * size, 'Promo': [''] * size}
    base.update(columns)
    return pd.DataFrame(base)


ALIASES = {'acme': 'Acme Pte Ltd'}
TAGS = {'kol': 'KOL Programme'}
CODES = {'EARLY': 'Early Bird'}


def run(data):
    return attribute(data, 'Promo', ALIASES, TAGS, CODES)


def test_priority_order():
    data = frame(**{'Corporate Group': ['ACME', None, None, None, None],
        'Complimentary Programme': [None, 'KOL', None, None, None],
        'Promo': ['', '', 'EARLY', '', ''],
        'Market': ['Singapore', 'Singapore', 'Singapore', 'Singapore', 'International']})
    result = run(data)
    assert result.Group.tolist() == ['Corporate', 'Complimentary', 'Campaign', 'Local Retail', 'International Retail']
    assert result.Subgroup.tolist() == ['Acme Pte Ltd', 'KOL Programme', 'Early Bird', '', '']


def test_conflicts_stay_in_higher_priority_group():
    data = frame(**{'Corporate Group': ['Acme', None], 'Complimentary Programme': ['KOL', 'KOL'], 'Promo': ['EARLY', 'EARLY']})
    result = run(data)
    assert result.Group.tolist() == ['Corporate', 'Complimentary']
    assert result.Conflict.tolist() == [True, True]
    assert result['Other Matches'].tolist() == ['Complimentary: KOL; Campaign: Early Bird', 'Campaign: Early Bird']


def test_unlinked_and_unconfigured():
    data = frame(**{'Corporate Group': ['Globex', None], 'Complimentary Programme': [None, 'Media']})
    assert run(data).Subgroup.tolist() == ['Unlinked', 'Unconfigured']


def test_unknown_market_is_international_and_categories_mapped():
    data = frame(**{'Market': ['Unknown'], 'Grouped Category': ['BYD Marathon Crew Challenge']})
    result = run(data)
    assert result.Group.tolist() == ['International Retail']
    assert result['Planning Category'].tolist() == ['Full Marathon']


def test_codes_are_exact_and_cleaned():
    assert clean_codes(pd.Series([' EARLY ', 'n/a', None])).tolist() == ['EARLY', '', '']
    result = run(frame(Promo=['early', ' EARLY ']))
    assert result.Group.tolist() == ['Local Retail', 'Campaign']


def test_no_promo_column_and_empty_data():
    data = frame(Promo=['EARLY'])
    assert attribute(data, None, ALIASES, TAGS, CODES).Group.tolist() == ['Local Retail']
    assert attribute(None, 'Promo', ALIASES, TAGS, CODES).empty
