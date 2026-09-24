from planning.complimentary_tags import AUTO_NOTE, absorb_new_tags

EXISTING = [
    {'id': 'p1', 'name': 'KOL Programme', 'tags': ['KOL'], 'notes': ''},
    {'id': 'p2', 'name': 'Media', 'tags': [], 'notes': ''},
]


def test_new_tags_become_programmes_and_existing_are_kept():
    ids = iter(['n1', 'n2'])
    programmes, added, attached = absorb_new_tags(EXISTING, ['kol', 'MEDIA', 'Elite', ' Elite ', 'NatChamps', None, ''], lambda: next(ids))
    assert added == ['Elite', 'NatChamps'] and attached == ['MEDIA']
    assert programmes[:2] == [EXISTING[0], {'id': 'p2', 'name': 'Media', 'tags': ['MEDIA'], 'notes': ''}]
    assert programmes[2] == {'id': 'n1', 'name': 'Elite', 'tags': ['Elite'], 'notes': AUTO_NOTE}
    assert EXISTING[1]['tags'] == []  # input not mutated


def test_nothing_new_returns_same_programmes():
    programmes, added, attached = absorb_new_tags(EXISTING, ['KOL'])
    assert programmes == EXISTING and not added and not attached
