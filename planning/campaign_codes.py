"""Read unique promo-code lists (CSV/XLSX with a Promo Code column)."""
from __future__ import annotations

from io import BytesIO

import pandas as pd

from planning.attribution import clean_codes


def parse_code_list(frame):
    """Return codes, total allowed uses (None if not given) and earliest end date."""
    frame = frame.rename(columns=lambda column: str(column).strip())
    if 'Promo Code' not in frame:
        raise ValueError('The file needs a "Promo Code" column.')
    codes = clean_codes(frame['Promo Code'])
    kept = frame[codes.ne('')].assign(Code=codes[codes.ne('')]).drop_duplicates('Code')
    cap = None
    if 'Usage' in kept and len(kept):
        limits = pd.to_numeric(kept['Usage'].astype(str).str.split('/').str[-1].str.strip(), errors='coerce')
        cap = int(limits.sum()) if limits.notna().all() else None
    end = None
    if 'End date' in kept:
        dates = pd.to_datetime(kept['End date'], utc=True, errors='coerce').dropna()
        if len(dates):
            end = dates.min().tz_convert('Asia/Singapore').date().isoformat()
    return {'codes': kept['Code'].tolist(), 'cap': cap, 'end': end, 'skipped': int(len(frame) - len(kept))}


def read_code_file(name, content):
    """Parse the bytes of an uploaded .csv or .xlsx code list."""
    lowered = name.lower()
    if lowered.endswith('.csv'):
        frame = pd.read_csv(BytesIO(content), dtype=str, encoding='utf-8-sig')
    elif lowered.endswith('.xlsx'):
        frame = pd.read_excel(BytesIO(content), dtype=str)
    else:
        raise ValueError('Upload a .csv or .xlsx file.')
    return parse_code_list(frame)
