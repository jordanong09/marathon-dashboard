import pandas as pd

from planning.campaign_detection import (AUTO_NOTE, absorb_detected, campaign_activity, code_prefix,
    detect_code_groups, merge_campaigns, suggest_merges)


def test_code_prefix_strips_trailing_numbers():
    assert code_prefix('EARLY10') == 'EARLY'
    assert code_prefix('medic-05') == 'MEDIC'
    assert code_prefix('KLHALF') == 'KLHALF'
    assert code_prefix('A1') == 'A1'  # too short once stripped: keep the whole code
    assert code_prefix('RG-SIM-1') == code_prefix('RGSIM2') == 'RGSIM'
    assert code_prefix('x7k2pq') == 'X7K2PQ'


def test_detect_groups_unclaimed_codes_with_dates():
    codes = pd.Series(['EARLY10', 'EARLY20', '', 'EARLY10', 'KL5', 'CLAIMED'])
    dates = pd.Series(pd.to_datetime(['2026-05-01', '2026-05-03', '2026-05-02', '2026-06-10', '2026-07-01', '2026-07-02']))
    groups = detect_code_groups(codes, dates, claimed={'CLAIMED'})
    assert groups['Prefix'].tolist() == ['EARLY', 'KL5']
    assert groups['Kind'].tolist() == ['Family', 'Single code']
    assert groups['Suggested name'].tolist() == ['EARLY', 'KL5']
    early = groups.iloc[0]
    assert early['Codes'] == ['EARLY10', 'EARLY20'] and early['Registrations'] == 3
    assert early['First registered'] == pd.Timestamp('2026-05-01') and early['Last registered'] == pd.Timestamp('2026-06-10')


def test_absorb_creates_big_groups_and_extends_auto_campaigns_only():
    campaigns = [
        {'id': 'a', 'name': 'MEDIC', 'type': 'shared', 'codes': ['MEDIC1'], 'cap': None, 'start': None, 'end': None, 'notes': '', 'auto': True, 'prefix': 'MEDIC'},
        {'id': 'm', 'name': 'EARLY', 'type': 'shared', 'codes': ['EB'], 'cap': None, 'start': None, 'end': None, 'notes': ''},
    ]
    groups = pd.DataFrame({'Prefix': ['EARLY', 'MEDIC', 'TINY'], 'Codes': [['EARLY10'], ['MEDIC2'], ['TINY1']],
        'Registrations': [9, 1, 2], 'First registered': [None] * 3, 'Last registered': [None] * 3})
    ids = iter(['n1'])
    result, created, extended = absorb_detected(campaigns, groups, min_registrations=5, make_id=lambda: next(ids))
    assert created == ['EARLY10'] and extended == ['MEDIC']
    assert result[0]['codes'] == ['MEDIC1', 'MEDIC2']
    assert result[1]['codes'] == ['EB']  # manual campaign untouched
    assert result[2] == {'id': 'n1', 'name': 'EARLY10', 'type': 'shared', 'codes': ['EARLY10'], 'cap': None,
        'start': None, 'end': None, 'notes': AUTO_NOTE, 'auto': True, 'prefix': 'EARLY'}
    assert campaigns[0]['codes'] == ['MEDIC1']  # input not mutated


def test_campaign_activity_first_last_and_last_seven_days():
    names = pd.Series(['Early', 'Early', '', 'Early', 'Medic'])
    dates = pd.Series(pd.to_datetime(['2026-05-01', '2026-09-20', '2026-09-24', '2026-09-18', '2026-06-01']))
    activity = campaign_activity(names, dates).set_index('Campaign')
    assert activity.loc['Early', 'First registered'] == pd.Timestamp('2026-05-01')
    assert activity.loc['Early', 'Last registered'] == pd.Timestamp('2026-09-20')
    assert activity.loc['Early', 'Code uses'] == 3 and activity.loc['Early', 'Last 7 days'] == 2
    assert activity.loc['Medic', 'Last 7 days'] == 0


def auto(name, codes, prefix, **extra):
    return {'id': name, 'name': name, 'type': 'shared', 'codes': codes, 'cap': None, 'start': None, 'end': None,
        'notes': AUTO_NOTE, 'auto': True, 'prefix': prefix} | extra


def test_single_code_campaign_is_renamed_to_family_when_siblings_arrive():
    groups = pd.DataFrame({'Prefix': ['RGSIM'], 'Codes': [['RGSIM2', 'RGSIM3']], 'Registrations': [4],
        'First registered': [None], 'Last registered': [None]})
    result, created, extended = absorb_detected([auto('RGSIM1', ['RGSIM1'], 'RGSIM')], groups)
    assert result[0]['name'] == 'RGSIM' and result[0]['codes'] == ['RGSIM1', 'RGSIM2', 'RGSIM3'] and extended == ['RGSIM']


def test_suggest_and_merge_campaigns_of_the_same_family():
    campaigns = [auto('RGSIM1', ['RGSIM1'], 'RGSIM1', cap=10, start='2026-05-01'), auto('RGSIM2', ['RGSIM2'], 'RGSIM2', cap=5, end='2026-08-01'),
        auto('EARLY10', ['EARLY10'], 'EARLY'), {'id': 'u', 'name': 'KL list', 'type': 'unique', 'codes': ['K1X', 'Z9Q'], 'cap': None,
        'start': None, 'end': None, 'notes': ''}]
    suggestions = suggest_merges(campaigns)
    assert suggestions == [{'prefix': 'RGSIM', 'ids': ['RGSIM1', 'RGSIM2'], 'campaigns': ['RGSIM1', 'RGSIM2']}]
    merged = merge_campaigns(campaigns, ['RGSIM1', 'RGSIM2'], 'RGSIM')
    assert [c['name'] for c in merged] == ['RGSIM', 'EARLY10', 'KL list']
    assert merged[0] | {'notes': ''} == auto('RGSIM1', ['RGSIM1', 'RGSIM2'], 'RGSIM', cap=15, start='2026-05-01', end='2026-08-01', notes='') | {'name': 'RGSIM'}
