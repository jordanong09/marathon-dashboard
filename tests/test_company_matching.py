from planning.company_matching import link_registration_names, normalize_company

COMPANIES = [
    {'id': 'c1', 'name': 'Sunway MCL Ltd', 'aliases': []},
    {'id': 'c2', 'name': 'Far East Management', 'aliases': ['FEM Group']},
    {'id': 'c3', 'name': 'Acme Pte Ltd', 'aliases': []},
    {'id': 'c4', 'name': 'Acme Limited', 'aliases': []},
]


def test_normalize_drops_case_punctuation_and_suffixes():
    assert normalize_company('SUNWAY MCL LIMITED') == 'sunway mcl'
    assert normalize_company('Sunway M.C.L. Pte. Ltd.') == 'sunway m c l'
    assert normalize_company('Maybank Sdn Bhd') == 'maybank'
    assert normalize_company('Ltd') == ''
    assert normalize_company('Siemens Mobility Pte Ltd (Wayne)') == 'siemens mobility'
    assert normalize_company('Siemens Pte Ltd (Sharon)') == 'siemens'


def test_links_explicit_aliases_first_then_unique_name_matches():
    links = link_registration_names(COMPANIES, ['SUNWAY MCL LIMITED', 'fem group', 'Far East Management', 'Unknown Co'])
    assert links == {
        'SUNWAY MCL LIMITED': ('c1', 'auto'),
        'fem group': ('c2', 'linked'),
        'Far East Management': ('c2', 'auto'),
    }


def test_ambiguous_normalized_names_are_not_auto_linked():
    assert 'ACME' not in link_registration_names(COMPANIES, ['ACME'])
