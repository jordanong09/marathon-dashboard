"""Capacity-table segment for every registration, computed column-wise."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _text(frame, column):
    # Matches the former row-wise `value or ""` then str(): None -> "", NaN -> "nan".
    values = frame[column] if column in frame else pd.Series('', index=frame.index)
    return values.map(lambda v: str(v) if v is not None and v != '' else '', na_action=None).astype(str)


def classify_capacity_segments(frame):
    """Segment per row. Order matters: medic and transfer before corporate/complimentary, then market."""
    if frame.empty:
        return pd.Series(index=frame.index, dtype=object)
    raw = _text(frame, '_group_corporate_raw')
    category_raw = _text(frame, '_category_raw')
    registration_type = frame['Registration Type']
    group = registration_type.eq('Group Registration')
    conditions = [
        raw.str.upper().str.contains('UNSFUL_MEDIC', regex=False),
        category_raw.str.contains('Transfer Entry', regex=False),
        group & raw.str.contains('Standard_Chartered_Staff', regex=False),
        group,
        registration_type.eq('Complimentary'),
        frame['Market'].eq('Singapore'),
    ]
    choices = ['Unsuccessful Medic Entry', 'Transfer Entry', 'Standard Chartered Staff Entry',
        'Corporate Registration', 'Complimentary Entry', 'Local']
    return pd.Series(np.select(conditions, choices, 'International'), index=frame.index, dtype=object)
