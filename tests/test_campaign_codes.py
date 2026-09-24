import pandas as pd
import pytest

from planning.campaign_codes import parse_code_list, read_code_file


def test_parse_dedupes_and_sums_usage():
    frame = pd.DataFrame({' Promo Code ': ['A1', 'A1', '', 'B2'], 'Usage': ['0/1', '0/1', '0/1', '2/3'],
        'End date': ['2026-09-30T15:59:00Z', None, None, '2026-10-01T00:00:00Z']})
    result = parse_code_list(frame)
    assert result == {'codes': ['A1', 'B2'], 'cap': 4, 'end': '2026-09-30', 'skipped': 2}


def test_missing_column_rejected():
    with pytest.raises(ValueError, match='Promo Code'):
        parse_code_list(pd.DataFrame({'Code': ['A']}))


def test_read_csv_bytes():
    assert read_code_file('codes.csv', b'Promo Code\nX1\nX2\n')['codes'] == ['X1', 'X2']
    with pytest.raises(ValueError):
        read_code_file('codes.txt', b'')
