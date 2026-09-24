"""Time the full app on a synthetic registration CSV (no real data).

Usage: python scripts/benchmark.py [rows]   (default 60000)
Target: every page responds in about 2 seconds after the CSV has loaded.
"""
import pathlib
import random
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]

import doc_store  # noqa: E402
import sales_backend  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402
from test_pages import full_app_script  # noqa: E402

PAGES = ['Executive Summary', 'Plan Allocation', 'Corporate Sales', 'Complimentary', 'Campaigns',
    'Overview', 'Daily registration', 'Groups & complimentary', 'Audience & markets', 'Reports & data']


def synthetic_csv(rows):
    random.seed(1)
    categories = ['BYD Marathon (42.195KM)', 'adidas Half Marathon (21.1KM)', 'Standard Chartered 10km', '5km Fun Run',
        'Kids Dash Competitive 1.6KM', 'Kids Dash Non-Competitive 600m', 'BYD Marathon Crew Challenge']
    countries = ['Singapore'] * 6 + ['Malaysia', 'Indonesia', 'Japan', 'India', 'Australia', 'Philippines', 'China', 'UK']
    groups = [''] * 80 + [f'GROUP_REGISTRATION_Company {i} Pte Ltd Batch 1 - X' for i in range(15)] + [f'COMPLIMENTARY_Prog{i}' for i in range(5)]
    codes = [''] * 85 + ['EARLY10', 'KLHALF', 'MEDIC5', 'SCB20'] + [f'U{i:05d}' for i in range(11)]
    lines = ['Registration Date,Current Age,Gender,Country,Category Name,Group/Corporate Name,Promo Code - Code']
    for i in range(rows):
        day = 1 + i * 150 // rows
        lines.append(f'{day % 28 + 1:02d}/{4 + day // 28:02d}/2026 {random.randint(0, 23):02d}:{random.randint(0, 59):02d},'
            f'{random.randint(5, 70)},{random.choice(["Male", "Female"])},{random.choice(countries)},{random.choice(categories)},'
            f'{random.choice(groups)},{random.choice(codes)}')
    return '\n'.join(lines) + '\n'


def main():
    rows = int(sys.argv[1]) if len(sys.argv) > 1 else 60000
    doc_store.DATA_DIR = pathlib.Path(tempfile.mkdtemp())
    sales_backend.settings = lambda: {'backend': 'local'}
    csv = synthetic_csv(rows)
    print(f'{rows:,} rows · {len(csv) / 1e6:.1f} MB')
    for page in PAGES:
        app = AppTest.from_function(full_app_script, args=(page, csv), default_timeout=600)
        start = time.perf_counter(); app.run(); first = time.perf_counter() - start
        start = time.perf_counter(); app.run(); rerun = time.perf_counter() - start
        print(f'{page:24s} first {first:5.1f}s   rerun {rerun:5.1f}s' + ('   ERROR' if app.exception else ''))


if __name__ == '__main__':
    main()
