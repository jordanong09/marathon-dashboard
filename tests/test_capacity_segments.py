import random

import numpy as np
import pandas as pd

from planning.capacity_segments import classify_capacity_segments


def legacy_classify(row):
    """Row-by-row classifier previously in app.py, kept as the reference behaviour."""
    group_corporate_raw = row.get("_group_corporate_raw") or ""
    category_raw = row.get("_category_raw") or ""
    if "UNSFUL_MEDIC" in str(group_corporate_raw).upper():
        return "Unsuccessful Medic Entry"
    if "Transfer Entry" in str(category_raw):
        return "Transfer Entry"
    if row["Registration Type"] == "Group Registration":
        if "Standard_Chartered_Staff" in str(group_corporate_raw):
            return "Standard Chartered Staff Entry"
        return "Corporate Registration"
    if row["Registration Type"] == "Complimentary":
        return "Complimentary Entry"
    if row["Market"] == "Singapore":
        return "Local"
    return "International"


def test_matches_legacy_row_classifier_on_every_branch():
    random.seed(7)
    raws = [None, np.nan, '', 'GROUP_REGISTRATION_Acme', 'group_unsful_medic_x', 'GROUP_REGISTRATION_Standard_Chartered_Staff',
        'COMPLIMENTARY_KOL', 'standard_chartered_staff']
    categories = [None, np.nan, '5km Fun Run', 'Transfer Entry - Marathon', 'transfer entry 10km']
    types = ['Public', 'Group Registration', 'Complimentary', 'Other']
    markets = ['Singapore', 'International', 'Unknown', None]
    frame = pd.DataFrame([{'_group_corporate_raw': random.choice(raws), '_category_raw': random.choice(categories),
        'Registration Type': random.choice(types), 'Market': random.choice(markets)} for _ in range(3000)])
    expected = frame.apply(legacy_classify, axis=1)
    pd.testing.assert_series_equal(classify_capacity_segments(frame), expected, check_names=False, check_dtype=False)


def test_empty_frame():
    empty = pd.DataFrame(columns=['_group_corporate_raw', '_category_raw', 'Registration Type', 'Market'])
    assert classify_capacity_segments(empty).empty
