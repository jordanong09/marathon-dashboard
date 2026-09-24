"""Six planning categories and conversion from registration categories."""
from __future__ import annotations

PLANNING_CATEGORIES = ['Full Marathon', 'Half Marathon', '10 km', '5 km', 'Kids 1.6 km', 'Kids 600 m']
GROUPS = ['Corporate', 'Complimentary', 'Campaign', 'Local Retail', 'International Retail']
UNMAPPED = 'Unmapped'
DEFAULT_CAPACITY = {'Full Marathon': 13000, 'Half Marathon': 19000, '10 km': 9000, '5 km': 7000,
    'Kids 1.6 km': 1500, 'Kids 600 m': 2500}
SOURCE_TO_PLANNING = {
    'BYD Marathon': 'Full Marathon',
    'BYD Marathon Crew Challenge': 'Full Marathon',
    'adidas Half Marathon': 'Half Marathon',
    'Standard Chartered 10km': '10 km',
    '5km': '5 km',
    'Kids Dash Competitive 1.6KM': 'Kids 1.6 km',
    'Kids Dash Non-Competitive 1.6KM': 'Kids 1.6 km',
    'Kids Dash Non-Competitive 600m': 'Kids 600 m',
}


def to_planning_category(name):
    """Map a grouped registration category (or a planning category) to a planning category."""
    if name in PLANNING_CATEGORIES:
        return name
    return SOURCE_TO_PLANNING.get(name, UNMAPPED)


def convert_quantities(quantities):
    """Sum per-category quantities into planning categories; unknown keys are kept, never dropped."""
    result = {category: 0 for category in PLANNING_CATEGORIES}
    for name, value in quantities.items():
        target = to_planning_category(name)
        key = name if target == UNMAPPED else target
        result[key] = result.get(key, 0) + value
    return result
