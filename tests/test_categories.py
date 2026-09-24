from planning.categories import PLANNING_CATEGORIES, UNMAPPED, convert_quantities, to_planning_category


def test_maps_detailed_categories():
    assert to_planning_category('BYD Marathon Crew Challenge') == 'Full Marathon'
    assert to_planning_category('Kids Dash Competitive 1.6KM') == 'Kids 1.6 km'
    assert to_planning_category('Kids Dash Non-Competitive 1.6KM') == 'Kids 1.6 km'
    assert to_planning_category('Half Marathon') == 'Half Marathon'
    assert to_planning_category('Unmapped') == UNMAPPED
    assert to_planning_category(None) == UNMAPPED


def test_convert_quantities_sums_legacy_keys():
    result = convert_quantities({'BYD Marathon': 10, 'BYD Marathon Crew Challenge': 5,
        'Kids Dash Competitive 1.6KM': 2, 'Kids Dash Non-Competitive 1.6KM': 3})
    assert result['Full Marathon'] == 15
    assert result['Kids 1.6 km'] == 5
    assert list(result)[:6] == PLANNING_CATEGORIES


def test_convert_quantities_keeps_unknown_keys():
    assert convert_quantities({'Mystery': 4})['Mystery'] == 4


def test_kids_variants_and_annotated_names_map_to_planning_categories():
    assert to_planning_category('Kids 1.6 km — subtype unconfirmed') == 'Kids 1.6 km'
    assert to_planning_category('Kids Dash 1.6KM (subtype unconfirmed)') == 'Kids 1.6 km'
    assert to_planning_category('Half Marathon — legacy') == 'Half Marathon'
    assert to_planning_category('Something else') == UNMAPPED


def test_convert_quantities_folds_unconfirmed_kids_subtype():
    result = convert_quantities({'Kids 1.6 km': 10, 'Kids 1.6 km — subtype unconfirmed': 114})
    assert result['Kids 1.6 km'] == 124 and 'Kids 1.6 km — subtype unconfirmed' not in result
