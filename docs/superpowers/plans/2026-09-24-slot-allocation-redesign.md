# Slot Allocation Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the executive plan allocation (5 groups × 6 categories + capacity) the single source of truth, add persisted Complimentary and Campaigns stakeholder tabs, and an Executive Summary of plan / utilized / remaining.

**Architecture:** Pure-pandas core in `planning/` (categories, attribution, metrics, code-list parsing), a named-document store `doc_store.py` (local JSON for dev, Supabase RPC for deployment) and thin Streamlit screens in `views/`. `app.py` keeps the registration CSV preparation and analytics pages and routes planning pages to `views/router.py`. Corporate Sales keeps its existing store and workflow.

**Tech Stack:** Python 3.13, Streamlit 1.59.2, pandas 3.0.3, Supabase (PostgREST RPC), pytest.

Spec: `docs/superpowers/specs/2026-09-24-slot-allocation-redesign-design.md`

Run tests with the project venv: `.venv/Scripts/python -m pytest -q` (Windows Git Bash).

## File map

| File | Status | Responsibility |
|---|---|---|
| `planning/__init__.py` | create | package marker |
| `planning/categories.py` | create | planning categories, groups, category conversion |
| `planning/attribution.py` | create | one group per registration + conflicts |
| `planning/metrics.py` | create | plan/utilized/remaining matrices, gaps |
| `planning/campaign_codes.py` | create | parse uploaded unique-code lists |
| `doc_store.py` | create | plan/complimentary/campaigns documents, validation, local + Supabase |
| `sales_backend.py` | modify | shared `call()`, `require_supabase` rule |
| `supabase_setup.sql` | modify | documents tables + RPCs |
| `views/__init__.py` | create | package marker |
| `views/common.py` | create | snapshots, save, target strip, formatting |
| `views/executive_summary.py` | create | Executive Summary |
| `views/plan_allocation.py` | create | Plan Allocation |
| `views/complimentary.py` | create | Complimentary tab |
| `views/campaigns.py` | create | Campaigns tab |
| `views/router.py` | create | planning page dispatch |
| `corporate_sales.py` | modify | ctx-based, planning categories, plan target |
| `admin_dashboard.py` | modify | grouped navigation; remove allocation admin |
| `app.py` | modify | routing, no-upload planning pages, plan capacity → targets, remove Slots & campaigns |
| `slot_planning.py` | delete | retired |
| `tests/*` | create | unit + AppTest smoke tests |
| `requirements-dev.txt`, `.gitignore`, `secrets.example.toml`, `README.md`, `CLOUD_TRIAL_GUIDE.md` | modify/create | tooling + deployment docs |

---

### Task 1: Test tooling

**Files:** Create `requirements-dev.txt`, `tests/conftest.py`; modify `.gitignore`

- [ ] **Step 1: Create files**

`requirements-dev.txt`:
```text
-r requirements.txt
pytest==8.4.2
```

`tests/conftest.py`:
```python
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def local_store(tmp_path, monkeypatch):
    """Force local storage in a temporary folder."""
    import doc_store
    import sales_backend
    monkeypatch.setattr(sales_backend, 'settings', lambda: {'backend': 'local'})
    monkeypatch.setattr(doc_store, 'DATA_DIR', tmp_path)
    return tmp_path
```

Append to `.gitignore`:
```text
.venv/
.pytest_cache/
```

- [ ] **Step 2: Commit**
```bash
git add requirements-dev.txt tests/conftest.py .gitignore
git commit -m "chore: add pytest tooling"
```

### Task 2: Planning categories

**Files:** Create `planning/__init__.py` (empty), `planning/categories.py`; Test `tests/test_categories.py`

- [ ] **Step 1: Write the failing test** — `tests/test_categories.py`:
```python
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
```

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/test_categories.py -q` → FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement** — `planning/categories.py`:
```python
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
```

- [ ] **Step 4: Run** tests → PASS
- [ ] **Step 5: Commit** `git add planning tests/test_categories.py && git commit -m "feat: planning categories"`

### Task 3: Attribution engine

**Files:** Create `planning/attribution.py`; Test `tests/test_attribution.py`

- [ ] **Step 1: Write the failing test** — `tests/test_attribution.py`:
```python
import pandas as pd

from planning.attribution import attribute, clean_codes


def frame(**columns):
    size = len(next(iter(columns.values())))
    base = {'Grouped Category': ['BYD Marathon'] * size, 'Corporate Group': [None] * size,
        'Complimentary Programme': [None] * size, 'Market': ['Singapore'] * size, 'Promo': [''] * size}
    base.update(columns)
    return pd.DataFrame(base)


ALIASES = {'acme': 'Acme Pte Ltd'}
TAGS = {'kol': 'KOL Programme'}
CODES = {'EARLY': 'Early Bird'}


def run(data):
    return attribute(data, 'Promo', ALIASES, TAGS, CODES)


def test_priority_order():
    data = frame(**{'Corporate Group': ['ACME', None, None, None, None],
        'Complimentary Programme': [None, 'KOL', None, None, None],
        'Promo': ['', '', 'EARLY', '', ''],
        'Market': ['Singapore', 'Singapore', 'Singapore', 'Singapore', 'International']})
    result = run(data)
    assert result.Group.tolist() == ['Corporate', 'Complimentary', 'Campaign', 'Local Retail', 'International Retail']
    assert result.Subgroup.tolist() == ['Acme Pte Ltd', 'KOL Programme', 'Early Bird', '', '']


def test_conflicts_stay_in_higher_priority_group():
    data = frame(**{'Corporate Group': ['Acme', None], 'Complimentary Programme': ['KOL', 'KOL'], 'Promo': ['EARLY', 'EARLY']})
    result = run(data)
    assert result.Group.tolist() == ['Corporate', 'Complimentary']
    assert result.Conflict.tolist() == [True, True]
    assert result['Other Matches'].tolist() == ['Complimentary: KOL; Campaign: Early Bird', 'Campaign: Early Bird']


def test_unlinked_and_unconfigured():
    data = frame(**{'Corporate Group': ['Globex', None], 'Complimentary Programme': [None, 'Media']})
    assert run(data).Subgroup.tolist() == ['Unlinked', 'Unconfigured']


def test_unknown_market_is_international_and_categories_mapped():
    data = frame(**{'Market': ['Unknown'], 'Grouped Category': ['BYD Marathon Crew Challenge']})
    result = run(data)
    assert result.Group.tolist() == ['International Retail']
    assert result['Planning Category'].tolist() == ['Full Marathon']


def test_codes_are_exact_and_cleaned():
    assert clean_codes(pd.Series([' EARLY ', 'n/a', None])).tolist() == ['EARLY', '', '']
    result = run(frame(Promo=['early', ' EARLY ']))
    assert result.Group.tolist() == ['Local Retail', 'Campaign']


def test_no_promo_column_and_empty_data():
    data = frame(Promo=['EARLY'])
    assert attribute(data, None, ALIASES, TAGS, CODES).Group.tolist() == ['Local Retail']
    assert attribute(None, 'Promo', ALIASES, TAGS, CODES).empty
```

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** — `planning/attribution.py`:
```python
"""Assign every registration to exactly one planning group."""
from __future__ import annotations

import numpy as np
import pandas as pd

from planning.categories import to_planning_category

COLUMNS = ['Group', 'Subgroup', 'Planning Category', 'Promo Code', 'Campaign', 'Conflict', 'Other Matches']


def clean_codes(series):
    values = series.fillna('').astype(str).str.strip()
    return values.mask(values.str.lower().isin(['', 'n/a', 'na', 'nan', 'none', '<na>']), '')


def _text(data, column):
    if column not in data:
        return pd.Series('', index=data.index, dtype=object)
    return data[column].fillna('').astype(str).str.strip().astype(object)


def attribute(data, promo_column, corporate_aliases, comp_tags, campaign_codes):
    """Priority: corporate tag > complimentary tag > campaign code > retail by market.

    corporate_aliases: {registration name casefolded: company}
    comp_tags: {complimentary tag casefolded: programme}
    campaign_codes: {exact code: campaign}
    """
    if data is None or data.empty:
        return pd.DataFrame(columns=COLUMNS)
    corporate = _text(data, 'Corporate Group')
    complimentary = _text(data, 'Complimentary Programme')
    codes = clean_codes(data[promo_column]).astype(object) if promo_column else pd.Series('', index=data.index, dtype=object)
    campaign = codes.map(campaign_codes).fillna('').astype(object)
    is_corporate, is_comp, is_campaign = corporate.ne(''), complimentary.ne(''), campaign.ne('')
    local = _text(data, 'Market').eq('Singapore')
    group = np.select([is_corporate, is_comp, is_campaign, local],
        ['Corporate', 'Complimentary', 'Campaign', 'Local Retail'], 'International Retail')
    subgroup = np.select([is_corporate, is_comp, is_campaign], [
        corporate.str.casefold().map(corporate_aliases).fillna('Unlinked'),
        complimentary.str.casefold().map(comp_tags).fillna('Unconfigured'),
        campaign], '')
    comp_other = pd.Series(np.where(is_comp & is_corporate, 'Complimentary: ' + complimentary, ''), index=data.index)
    campaign_other = pd.Series(np.where(is_campaign & (is_corporate | is_comp), 'Campaign: ' + campaign, ''), index=data.index)
    other = (comp_other + '; ' + campaign_other).str.strip('; ')
    return pd.DataFrame({
        'Group': group, 'Subgroup': subgroup,
        'Planning Category': data['Grouped Category'].map(to_planning_category),
        'Promo Code': codes, 'Campaign': campaign,
        'Conflict': other.ne(''), 'Other Matches': other}, index=data.index)
```
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `git add planning/attribution.py tests/test_attribution.py && git commit -m "feat: registration attribution engine"`

### Task 4: Metrics

**Files:** Create `planning/metrics.py`; Test `tests/test_metrics.py`

- [ ] **Step 1: Write the failing test** — `tests/test_metrics.py`:
```python
import math

import pandas as pd

from planning.categories import DEFAULT_CAPACITY, GROUPS, PLANNING_CATEGORIES
from planning.metrics import (capacity_series, gaps, group_summary, plan_matrix, unmatched_codes,
    utilized_matrix)


def plan_doc(**cells):
    allocation = {g: {c: 0 for c in PLANNING_CATEGORIES} for g in GROUPS}
    for (group, category), value in cells.items():
        allocation[group][category] = value
    return {'capacity': dict(DEFAULT_CAPACITY), 'allocation': allocation}


def attributed(rows):
    return pd.DataFrame(rows, columns=['Group', 'Subgroup', 'Planning Category', 'Promo Code', 'Campaign', 'Conflict', 'Other Matches'])


def test_plan_matrix_and_capacity():
    doc = plan_doc(**{('Corporate', 'Full Marathon'): 200})
    assert plan_matrix(doc).loc['Corporate', 'Full Marathon'] == 200
    assert capacity_series(doc)['Full Marathon'] == 13000


def test_utilized_uses_reservations_issuances_and_registrations():
    orders = [{'quantities': {'BYD Marathon': 50, 'BYD Marathon Crew Challenge': 10}, 'cancelled': False},
        {'quantities': {'Full Marathon': 99}, 'cancelled': True}]
    issuances = [{'quantities': {'5 km': 7}, 'cancelled': False}]
    registrations = attributed([
        ['Campaign', 'Early', 'Half Marathon', 'EARLY', 'Early', False, ''],
        ['Local Retail', '', '10 km', '', '', False, ''],
        ['Local Retail', '', 'Unmapped', '', '', False, ''],
        ['Corporate', 'Acme', 'Full Marathon', '', '', False, '']])
    result = utilized_matrix(orders, issuances, registrations)
    assert result.loc['Corporate', 'Full Marathon'] == 60
    assert result.loc['Complimentary', '5 km'] == 7
    assert result.loc['Campaign', 'Half Marathon'] == 1
    assert result.loc['Local Retail'].sum() == 1


def test_utilized_without_upload_is_nan_for_registration_groups():
    result = utilized_matrix([], [], None)
    assert result.loc['Corporate'].sum() == 0
    assert result.loc['Campaign'].isna().all()


def test_group_summary_totals():
    plan = plan_matrix(plan_doc(**{('Corporate', '5 km'): 100}))
    utilized = utilized_matrix([{'quantities': {'5 km': 120}, 'cancelled': False}], [], None)
    summary = group_summary(plan, utilized)
    assert summary.loc['Corporate', 'Remaining'] == -20
    assert summary.loc['Total', 'Plan'] == 100
    assert math.isnan(summary.loc['Campaign', 'Utilized'])


def test_gaps_report_over_allocation_oversold_and_low_utilization():
    doc = plan_doc(**{('Corporate', '5 km'): 100, ('Complimentary', 'Kids 600 m'): 3000})
    plan = plan_matrix(doc)
    utilized = utilized_matrix([{'quantities': {'5 km': 120}, 'cancelled': False}], [], None)
    messages = gaps(plan, utilized, capacity_series(doc), None)
    levels = [level for level, _ in messages]
    text = ' | '.join(message for _, message in messages)
    assert 'Corporate · 5 km: 20 over plan' in text
    assert 'Kids 600 m: plan exceeds capacity by 500' in text
    assert 'Complimentary: 0% of plan utilized' in text
    assert levels == sorted(levels, key=['error', 'warning', 'info'].index)


def test_unmatched_codes():
    registrations = attributed([
        ['Local Retail', '', '5 km', 'MEDIC', '', False, ''],
        ['Local Retail', '', '5 km', 'MEDIC', '', False, ''],
        ['Campaign', 'Early', '5 km', 'EARLY', 'Early', False, '']])
    assert unmatched_codes(registrations).to_dict() == {'MEDIC': 2}
```

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** — `planning/metrics.py`:
```python
"""Plan, utilized and remaining matrices (groups x planning categories)."""
from __future__ import annotations

import pandas as pd

from planning.categories import GROUPS, PLANNING_CATEGORIES, UNMAPPED, convert_quantities

REGISTRATION_GROUPS = ['Campaign', 'Local Retail', 'International Retail']
LEVELS = ['error', 'warning', 'info']


def empty_matrix(fill=0.0):
    return pd.DataFrame(fill, index=GROUPS, columns=PLANNING_CATEGORIES, dtype=float)


def capacity_series(plan_doc):
    return pd.Series({c: plan_doc['capacity'].get(c, 0) for c in PLANNING_CATEGORIES}, dtype=float)


def plan_matrix(plan_doc):
    matrix = empty_matrix()
    for group, row in plan_doc['allocation'].items():
        for category, value in row.items():
            if group in matrix.index and category in matrix.columns:
                matrix.loc[group, category] = value
    return matrix


def sum_quantities(records):
    """Total non-cancelled quantities by planning category."""
    total = pd.Series(0.0, index=PLANNING_CATEGORIES)
    for record in records:
        if record.get('cancelled'):
            continue
        for category, value in convert_quantities(record['quantities']).items():
            if category in total.index:
                total[category] += value
    return total


def registered_matrix(attributed):
    mapped = attributed[attributed['Planning Category'].ne(UNMAPPED)]
    counts = pd.crosstab(mapped['Group'], mapped['Planning Category'])
    return counts.reindex(index=GROUPS, columns=PLANNING_CATEGORIES, fill_value=0).astype(float)


def utilized_matrix(corporate_orders, issuances, attributed):
    """Corporate = reserved, Complimentary = issued, others = registrations (NaN without an upload)."""
    matrix = empty_matrix(float('nan'))
    matrix.loc['Corporate'] = sum_quantities(corporate_orders)
    matrix.loc['Complimentary'] = sum_quantities(issuances)
    if attributed is not None:
        matrix.loc[REGISTRATION_GROUPS] = registered_matrix(attributed).loc[REGISTRATION_GROUPS]
    return matrix


def group_summary(plan, utilized):
    used = utilized.sum(axis=1, min_count=1)
    summary = pd.DataFrame({'Plan': plan.sum(axis=1), 'Utilized': used})
    summary.loc['Total'] = [plan.to_numpy().sum(), used.sum(min_count=1)]
    summary['Remaining'] = summary.Plan - summary.Utilized
    summary['% utilized'] = summary.Utilized / summary.Plan.replace(0, float('nan')) * 100
    return summary


def unmatched_codes(attributed):
    codes = attributed.loc[attributed['Promo Code'].ne('') & attributed['Campaign'].eq(''), 'Promo Code']
    return codes.value_counts()


def gaps(plan, utilized, capacity, attributed, low_share=0.5):
    """Return (level, message) pairs ordered error → warning → info."""
    items = []
    remaining = plan - utilized
    for group in GROUPS:
        for category in PLANNING_CATEGORIES:
            value = remaining.loc[group, category]
            if pd.notna(value) and value < 0:
                items.append(('error', f'{group} · {category}: {-value:,.0f} over plan'))
    unallocated = capacity - plan.sum()
    for category, value in unallocated.items():
        if value < 0:
            items.append(('error', f'{category}: plan exceeds capacity by {-value:,.0f}'))
        elif value > 0:
            items.append(('info', f'{category}: {value:,.0f} places not yet allocated to a group'))
    for group in GROUPS:
        planned, used = plan.loc[group].sum(), utilized.loc[group].sum(min_count=1)
        if planned > 0 and pd.notna(used) and used < planned * low_share:
            items.append(('warning', f'{group}: {used / planned:.0%} of plan utilized ({used:,.0f} of {planned:,.0f})'))
    if attributed is not None and not attributed.empty:
        for label, group in [('Unlinked', 'Corporate'), ('Unconfigured', 'Complimentary')]:
            count = int((attributed['Group'].eq(group) & attributed['Subgroup'].eq(label)).sum())
            if count:
                items.append(('warning', f'{count:,} {group.lower()} registrations are {label.lower()}: link their registration names in the {group} tab'))
        unmatched = unmatched_codes(attributed)
        if len(unmatched):
            items.append(('info', f'{len(unmatched):,} promo codes ({int(unmatched.sum()):,} registrations) are not in any campaign'))
    return sorted(items, key=lambda item: LEVELS.index(item[0]))
```
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `git add planning/metrics.py tests/test_metrics.py && git commit -m "feat: plan, utilized and gap metrics"`

### Task 5: Code-list parsing

**Files:** Create `planning/campaign_codes.py`; Test `tests/test_campaign_codes.py`

- [ ] **Step 1: Write the failing test**:
```python
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
```
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** — `planning/campaign_codes.py`:
```python
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
```
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `git add planning/campaign_codes.py tests/test_campaign_codes.py && git commit -m "feat: parse unique promo code lists"`

### Task 6: sales_backend shared call + require_supabase

**Files:** Modify `sales_backend.py`; Test `tests/test_sales_backend.py`

- [ ] **Step 1: Write the failing test**:
```python
import pytest

import sales_backend


def test_require_supabase_blocks_local(monkeypatch):
    monkeypatch.setattr(sales_backend.st, 'secrets', {'sales_storage': {'backend': 'local', 'require_supabase': True}})
    with pytest.raises(ValueError, match='must store records in Supabase'):
        sales_backend.settings()


def test_local_default(monkeypatch):
    monkeypatch.setattr(sales_backend.st, 'secrets', {})
    assert sales_backend.settings()['backend'] == 'local'
```
- [ ] **Step 2: Run** → FAIL on first test
- [ ] **Step 3: Implement** — replace `settings` and `rpc` in `sales_backend.py`:
```python
def settings():
    try:
        config = dict(st.secrets.get("sales_storage", {}))
    except FileNotFoundError:
        config = {}
    mode = config.get("backend", "local")
    if mode not in ("local", "supabase"):
        raise ValueError("Unknown sales storage backend.")
    if config.get("require_supabase") and mode != "supabase":
        raise ValueError("This deployment must store records in Supabase. Configure sales_storage in Streamlit Secrets.")
    if mode == "supabase":
        url = config.get("url", "").rstrip("/")
        key = config.get("secret_key", "")
        if not re.fullmatch(r"https://[a-z0-9-]+\.supabase\.co", url) or not key.startswith("sb_secret_"):
            raise ValueError("Configure the Supabase project URL and server secret key in Streamlit Secrets.")
        config["url"] = url
    config["backend"] = mode
    return config


def call(config, function, payload):
    """POST a server-only RPC; map failures to user-facing errors."""
    request = Request(config["url"] + "/rest/v1/rpc/" + function,
        data=json.dumps(payload).encode(), method="POST",
        headers={"apikey": config["secret_key"], "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 409:
            raise ValueError("Records changed in another session. Reload before saving.") from None
        raise OSError("Supabase rejected the request. Ask the administrator to check the connection and database setup.") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise OSError("Supabase could not confirm the request. Reload saved records before retrying; a save may have completed.") from None


def rpc(config, function, payload):
    result = call(config, function, payload)
    if not isinstance(result, dict) or result.get("schema_version") != 1 or not all(k in result for k in ("revision", "companies", "orders", "targets", "history")):
        raise ValueError("Supabase returned an unexpected record format. Saving has been stopped.")
    return result
```
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `git add sales_backend.py tests/test_sales_backend.py && git commit -m "feat: shared Supabase call and require_supabase rule"`

### Task 7: Document store

**Files:** Create `doc_store.py`; Test `tests/test_doc_store.py`

- [ ] **Step 1: Write the failing test**:
```python
import pytest

import doc_store
import sales_backend


def test_read_returns_seed(local_store):
    plan = doc_store.read('plan')
    assert plan['revision'] == 0 and plan['capacity']['Full Marathon'] == 13000
    assert doc_store.read('campaigns')['campaigns'] == []


def test_save_bumps_revision_and_rejects_stale(local_store):
    plan = doc_store.read('plan')
    plan['allocation']['Corporate']['5 km'] = 10
    saved = doc_store.save('plan', plan, 0, 'Plan saved')
    assert saved['revision'] == 1 and saved['history'][-1]['action'] == 'Plan saved'
    assert doc_store.read('plan')['allocation']['Corporate']['5 km'] == 10
    with pytest.raises(ValueError, match='changed in another session'):
        doc_store.save('plan', plan, 0, 'stale')


def test_plan_validation(local_store):
    plan = doc_store.read('plan')
    plan['capacity']['5 km'] = -1
    with pytest.raises(ValueError, match='Capacity for 5 km'):
        doc_store.save('plan', plan, 0, 'x')


def campaign(name, codes, **extra):
    return {'id': name, 'name': name, 'type': 'shared', 'codes': codes, 'cap': None, 'start': None, 'end': None, 'notes': ''} | extra


def test_campaign_code_clash_rejected(local_store):
    doc = doc_store.read('campaigns')
    doc['campaigns'] = [campaign('A', ['X1', 'X2']), campaign('B', ['X2'])]
    with pytest.raises(ValueError, match='1 code\\(s\\) already belong to another campaign: X2'):
        doc_store.save('campaigns', doc, 0, 'x')


def test_campaign_names_unique_and_dates_ordered(local_store):
    doc = doc_store.read('campaigns')
    doc['campaigns'] = [campaign('A', []), campaign('a', [])]
    with pytest.raises(ValueError, match='unique'):
        doc_store.save('campaigns', doc, 0, 'x')
    doc['campaigns'] = [campaign('A', [], start='2026-10-02', end='2026-10-01')]
    with pytest.raises(ValueError, match='end date'):
        doc_store.save('campaigns', doc, 0, 'x')


def test_complimentary_validation(local_store):
    doc = doc_store.read('complimentary')
    doc['programmes'] = [{'id': 'p1', 'name': 'KOL', 'tags': ['KOL'], 'notes': ''},
        {'id': 'p2', 'name': 'Media', 'tags': ['kol'], 'notes': ''}]
    with pytest.raises(ValueError, match='only one programme'):
        doc_store.save('complimentary', doc, 0, 'x')
    doc['programmes'] = doc['programmes'][:1]
    doc['issuances'] = [{'id': 'i1', 'programme_id': 'p1', 'date': '2026-09-01', 'recipient': 'KOLs',
        'quantities': {'5 km': 0}, 'notes': '', 'cancelled': False, 'cancel_reason': ''}]
    with pytest.raises(ValueError, match='at least one'):
        doc_store.save('complimentary', doc, 0, 'x')
    doc['issuances'][0]['quantities'] = {'5 km': 5}
    assert doc_store.save('complimentary', doc, 0, 'ok')['revision'] == 1


def test_supabase_read_and_save(monkeypatch):
    calls = []
    monkeypatch.setattr(sales_backend, 'settings', lambda: {'backend': 'supabase', 'url': 'u', 'secret_key': 'k'})

    def fake_call(config, function, payload):
        calls.append((function, payload))
        if function == 'marathon_doc_read':
            return {'schema_version': 1, 'revision': 3, 'history': []}
        return payload['p_data'] | {'revision': 4}

    monkeypatch.setattr(sales_backend, 'call', fake_call)
    doc = doc_store.read('plan')
    assert doc['revision'] == 3 and 'capacity' in doc
    assert doc_store.save('plan', doc, 3, 'x')['revision'] == 4
    assert calls[1][0] == 'marathon_doc_save' and calls[1][1]['p_expected_revision'] == 3


def test_supabase_bad_response(monkeypatch):
    monkeypatch.setattr(sales_backend, 'settings', lambda: {'backend': 'supabase'})
    monkeypatch.setattr(sales_backend, 'call', lambda *a: ['nope'])
    with pytest.raises(ValueError, match='unexpected record format'):
        doc_store.read('plan')
```
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** — `doc_store.py`:
```python
"""Named planning documents (plan, complimentary, campaigns) with revision checks.

Local JSON is for development; deployments use Supabase RPCs (see supabase_setup.sql).
"""
from __future__ import annotations

import copy
import json
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import sales_backend
from planning.categories import DEFAULT_CAPACITY, GROUPS, PLANNING_CATEGORIES

DATA_DIR = Path(os.environ.get('MARATHON_DATA_DIR', Path(__file__).parent / 'planning_data'))
NAMES = ('plan', 'complimentary', 'campaigns')


def seed(name):
    base = {'schema_version': 1, 'revision': 0, 'history': []}
    if name == 'plan':
        return base | {'capacity': dict(DEFAULT_CAPACITY),
            'allocation': {group: {category: 0 for category in PLANNING_CATEGORIES} for group in GROUPS}}
    if name == 'complimentary':
        return base | {'programmes': [], 'issuances': []}
    if name == 'campaigns':
        return base | {'campaigns': []}
    raise ValueError(f'Unknown planning document: {name}')


def _merge(name, stored):
    if stored is None:
        return seed(name)
    if not isinstance(stored, dict) or stored.get('schema_version') != 1:
        raise ValueError('Supabase returned an unexpected record format. Saving has been stopped.')
    return seed(name) | stored


def _whole(value, label):
    if type(value) is not int or value < 0:
        raise ValueError(f'{label} must be a whole number of 0 or more.')


def _past_date(value, label):
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f'{label} must be a valid date.') from None
    if parsed > date.today():
        raise ValueError(f'{label} cannot be in the future.')


def _unique_names(items, label):
    names = [str(item.get('name', '')).strip().casefold() for item in items]
    if not all(names):
        raise ValueError(f'Every {label} needs a name.')
    if len(names) != len(set(names)):
        raise ValueError(f'{label.capitalize()} names must be unique.')


def validate(name, data):
    if data.get('schema_version') != 1 or not isinstance(data.get('history'), list):
        raise ValueError('Unsupported planning document format.')
    if name == 'plan':
        for category in PLANNING_CATEGORIES:
            _whole(data['capacity'].get(category), f'Capacity for {category}')
        for group in GROUPS:
            for category in PLANNING_CATEGORIES:
                _whole(data['allocation'].get(group, {}).get(category), f'{group} · {category}')
    elif name == 'complimentary':
        _unique_names(data['programmes'], 'programme')
        tags = [tag.casefold() for programme in data['programmes'] for tag in programme['tags']]
        if len(tags) != len(set(tags)):
            raise ValueError('A registration tag can be linked to only one programme.')
        ids = {programme['id'] for programme in data['programmes']}
        for item in data['issuances']:
            if item['programme_id'] not in ids:
                raise ValueError('An issuance refers to a programme that no longer exists.')
            _past_date(item['date'], 'Issue date')
            for category, value in item['quantities'].items():
                _whole(value, f'Issued places for {category}')
            if sum(item['quantities'].values()) <= 0:
                raise ValueError('Enter at least one issued place.')
            if item.get('cancelled') and not str(item.get('cancel_reason', '')).strip():
                raise ValueError('Enter a reason when cancelling an issuance.')
    elif name == 'campaigns':
        _unique_names(data['campaigns'], 'campaign')
        owner, clashes = {}, set()
        for campaign in data['campaigns']:
            if campaign['type'] not in ('shared', 'unique'):
                raise ValueError('Campaign type must be shared or unique.')
            if campaign.get('cap') is not None:
                _whole(campaign['cap'], 'Campaign cap')
            if campaign.get('start') and campaign.get('end') and campaign['start'] > campaign['end']:
                raise ValueError(f"{campaign['name']}: the end date must be on or after the start date.")
            for code in campaign['codes']:
                if not isinstance(code, str) or not code.strip():
                    raise ValueError('Promo codes cannot be blank.')
                if owner.get(code, campaign['name']) != campaign['name']:
                    clashes.add(code)
                owner[code] = campaign['name']
        if clashes:
            shown = ', '.join(sorted(clashes)[:10])
            raise ValueError(f'{len(clashes)} code(s) already belong to another campaign: {shown}')
    else:
        raise ValueError(f'Unknown planning document: {name}')


def _path(name, folder):
    return Path(folder) / f'{name}.json'


def _read_local(name, path):
    return _merge(name, json.loads(path.read_text(encoding='utf-8')) if path.exists() else None)


def read(name, folder=None):
    if name not in NAMES:
        raise ValueError(f'Unknown planning document: {name}')
    config = sales_backend.settings()
    if config.get('backend') == 'supabase':
        return _merge(name, sales_backend.call(config, 'marathon_doc_read', {'p_name': name}))
    return _read_local(name, _path(name, folder or DATA_DIR))


def save(name, data, expected_revision, action, folder=None):
    validate(name, data)
    config = sales_backend.settings()
    if config.get('backend') == 'supabase':
        result = sales_backend.call(config, 'marathon_doc_save', {'p_name': name, 'p_data': data,
            'p_expected_revision': expected_revision, 'p_action': action})
        return _merge(name, result)
    return _save_local(name, _path(name, folder or DATA_DIR), data, expected_revision, action)


def _save_local(name, path, data, expected_revision, action):
    """Reject stale edits; keep a backup and atomically replace the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix('.lock')
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError('Another save is in progress. Retry shortly; if it persists, ask an administrator to inspect the save lock.') from None
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        os.close(descriptor)
        current = _read_local(name, path)
        if current['revision'] != expected_revision:
            raise ValueError('These records changed in another session. Reload before saving your changes.')
        result = copy.deepcopy(data)
        result['revision'] = current['revision'] + 1
        now = datetime.now(timezone.utc).isoformat()
        result['saved_at'] = now
        result['history'] = current['history'] + [{'at': now, 'action': action, 'revision': result['revision']}]
        if path.exists():
            backups = path.parent / 'backups'
            backups.mkdir(exist_ok=True)
            (backups / f"{name}-{current['revision']}-{uuid.uuid4().hex[:8]}.json").write_bytes(path.read_bytes())
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        return result
    finally:
        temporary.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)
```
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `git add doc_store.py tests/test_doc_store.py && git commit -m "feat: planning document store"`

### Task 8: Supabase SQL

**Files:** Modify `supabase_setup.sql` — insert before the final `commit;`:
```sql
-- Planning documents: plan, complimentary, campaigns (added 2026-09-24).
create table if not exists marathon_private.documents (
 name text primary key check (name in ('plan','complimentary','campaigns')),
 document jsonb not null
);
create table if not exists marathon_private.document_revision (
 name text not null,
 revision bigint not null,
 document jsonb not null,
 archived_at timestamptz not null default now(),
 primary key (name, revision)
);
alter table marathon_private.documents enable row level security;
alter table marathon_private.document_revision enable row level security;
revoke all on marathon_private.documents, marathon_private.document_revision from public, anon, authenticated;
insert into marathon_private.documents values
 ('plan','{"schema_version":1,"revision":0,"history":[]}'),
 ('complimentary','{"schema_version":1,"revision":0,"history":[]}'),
 ('campaigns','{"schema_version":1,"revision":0,"history":[]}')
on conflict do nothing;
create or replace function public.marathon_doc_read(p_name text) returns jsonb
language sql security definer set search_path = '' as $$
 select document from marathon_private.documents where name = p_name;
$$;
create or replace function public.marathon_doc_save(p_name text, p_data jsonb, p_expected_revision bigint, p_action text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare current_doc jsonb; next_doc jsonb; next_revision bigint; saved_time timestamptz := clock_timestamp();
begin
 select document into strict current_doc from marathon_private.documents where name = p_name for update;
 if (current_doc->>'revision')::bigint <> p_expected_revision then
  raise sqlstate 'PT409' using message = 'Stale revision';
 end if;
 if p_data->>'schema_version' is distinct from '1' then
  raise exception 'Invalid planning document';
 end if;
 next_revision := p_expected_revision + 1;
 next_doc := p_data || jsonb_build_object('revision', next_revision, 'saved_at', saved_time,
  'history', (current_doc->'history') || jsonb_build_array(jsonb_build_object('at', saved_time, 'action', p_action, 'revision', next_revision)));
 insert into marathon_private.document_revision(name, revision, document) values (p_name, p_expected_revision, current_doc);
 update marathon_private.documents set document = next_doc where name = p_name;
 return next_doc;
end;
$$;
revoke all on function public.marathon_doc_read(text) from public, anon, authenticated;
revoke all on function public.marathon_doc_save(text, jsonb, bigint, text) from public, anon, authenticated;
grant execute on function public.marathon_doc_read(text) to service_role;
grant execute on function public.marathon_doc_save(text, jsonb, bigint, text) to service_role;
```
- [ ] Commit `git add supabase_setup.sql && git commit -m "feat: Supabase planning documents"`

### Task 9: Shared view helpers + router

**Files:** Create `views/__init__.py` (empty), `views/common.py`, `views/router.py`

`views/common.py`:
```python
"""Shared loading, saving and target display for the planning pages."""
from __future__ import annotations

import copy

import pandas as pd
import streamlit as st

import doc_store
import sales_backend
from planning.attribution import attribute
from planning.categories import PLANNING_CATEGORIES
from planning.metrics import capacity_series, plan_matrix, utilized_matrix

DOCUMENTS = ('plan', 'complimentary', 'campaigns', 'corporate')


def sales_path():
    return doc_store.DATA_DIR / 'corporate_sales.json'


def _read(name):
    return sales_backend.read_store(sales_path()) if name == 'corporate' else doc_store.read(name)


def get_doc(name):
    """Session snapshot of a saved document (deep copy, safe to edit)."""
    key = 'doc_snapshot_' + name
    if key not in st.session_state:
        st.session_state[key] = _read(name)
    return copy.deepcopy(st.session_state[key])


def save_doc(name, data, action):
    """Save and rerun on success; show the error and return on failure."""
    try:
        if name == 'corporate':
            saved = sales_backend.save_store(sales_path(), data, data['revision'], action)
        else:
            saved = doc_store.save(name, data, data['revision'], action)
    except (ValueError, OSError) as error:
        st.error(f'Not saved: {error}')
        return
    st.session_state['doc_snapshot_' + name] = saved
    st.session_state['saved_notice'] = f'{action} — saved to {sales_backend.storage_label()}.'
    st.rerun()


def show_saved_notice():
    if 'saved_notice' in st.session_state:
        st.success(st.session_state.pop('saved_notice'))


def reload_button(key):
    if st.button('Reload saved records', key=key, help='Fetch the latest records saved by other users.'):
        for name in DOCUMENTS:
            st.session_state.pop('doc_snapshot_' + name, None)
        st.rerun()


def storage_banner():
    if sales_backend.storage_label() == 'Supabase':
        st.caption('Storage: Supabase')
    else:
        st.warning('Local storage — not for real data. Records are saved on this computer only.')


def planning_context(data, promo_column):
    """Load every document and compute plan/utilized matrices, or show an error and return None."""
    try:
        docs = {name: get_doc(name) for name in DOCUMENTS}
    except (ValueError, OSError) as error:
        st.error(f'Cannot read saved planning records: {error}. Nothing has been changed.')
        return None
    sales, comp, campaigns = docs['corporate'], docs['complimentary'], docs['campaigns']
    aliases = {alias.casefold(): company['name'] for company in sales['companies'] for alias in company['aliases']}
    tags = {tag.casefold(): programme['name'] for programme in comp['programmes'] for tag in programme['tags']}
    codes = {code: campaign['name'] for campaign in campaigns['campaigns'] for code in campaign['codes']}
    attributed = None if data is None else attribute(data, promo_column, aliases, tags, codes)
    return {'docs': docs, 'data': data, 'promo_column': promo_column, 'attributed': attributed,
        'plan': plan_matrix(docs['plan']), 'capacity': capacity_series(docs['plan']),
        'utilized': utilized_matrix(sales['orders'], comp['issuances'], attributed)}


def fmt(value):
    return '—' if pd.isna(value) else f'{value:,.0f}'


def _negative(value):
    return 'color:#B42318;background-color:#FFF0ED' if isinstance(value, (int, float)) and pd.notna(value) and value < 0 else ''


def style_numbers(frame):
    return frame.style.format('{:,.0f}', na_rep='—').map(_negative)


def target_strip(ctx, group):
    """Plan / utilized / remaining for one group, per planning category."""
    plan, utilized = ctx['plan'].loc[group], ctx['utilized'].loc[group]
    frame = pd.DataFrame({'Plan': plan, 'Utilized': utilized, 'Remaining': plan - utilized}).T
    frame['Total'] = frame.sum(axis=1, min_count=1)
    a, b, c = st.columns(3)
    a.metric(f'{group} plan', fmt(frame.loc['Plan', 'Total']))
    b.metric('Utilized', fmt(frame.loc['Utilized', 'Total']))
    c.metric('Remaining', fmt(frame.loc['Remaining', 'Total']))
    st.dataframe(style_numbers(frame), width='stretch')
    if not frame.loc['Plan', 'Total']:
        st.caption('No plan allocation for this group yet. The executive sets it in Plan Allocation.')


def quantity_editor(key, quantities=None):
    """Editable Places per planning category; returns {category: int}."""
    quantities = quantities or {}
    frame = pd.DataFrame({'Category': PLANNING_CATEGORIES, 'Places': [int(quantities.get(c, 0)) for c in PLANNING_CATEGORIES]})
    edited = st.data_editor(frame, key=key, disabled=['Category'], hide_index=True, width='stretch',
        column_config={'Places': st.column_config.NumberColumn(min_value=0, step=1, required=True)})
    return {category: int(value) for category, value in zip(edited.Category, edited.Places.fillna(0))}


def needs_upload(ctx):
    if ctx['data'] is None:
        st.info('Upload the registration CSV in the sidebar to see registrations here.')
        return True
    return False
```

`views/router.py`:
```python
"""Dispatch the planning and stakeholder pages."""
from __future__ import annotations

from corporate_sales import render_corporate_sales
from views.campaigns import render_campaigns
from views.common import planning_context, reload_button, show_saved_notice, storage_banner
from views.complimentary import render_complimentary
from views.executive_summary import render_executive_summary
from views.plan_allocation import render_plan_allocation

PAGES = {
    'Executive Summary': render_executive_summary,
    'Plan Allocation': render_plan_allocation,
    'Corporate Sales': render_corporate_sales,
    'Complimentary': render_complimentary,
    'Campaigns': render_campaigns,
}
PLANNING_PAGES = tuple(PAGES)


def render_planning_page(page, data, promo_column):
    storage_banner()
    show_saved_notice()
    ctx = planning_context(data, promo_column)
    if ctx is None:
        return
    reload_button('reload_' + page)
    PAGES[page](ctx)
```
- [ ] Commit together with Tasks 10–13 (the router imports them).

### Task 10: Executive Summary view — `views/executive_summary.py`
```python
"""Executive view: plan, utilized and remaining for every group and category."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from planning.metrics import gaps, group_summary
from views.common import fmt, style_numbers


def render_executive_summary(ctx):
    st.subheader('Executive Summary')
    plan, utilized, capacity = ctx['plan'], ctx['utilized'], ctx['capacity']
    summary = group_summary(plan, utilized)
    unallocated = capacity - plan.sum()
    tiles = [('Capacity', capacity.sum()), ('Planned', summary.loc['Total', 'Plan']),
        ('Utilized', summary.loc['Total', 'Utilized']), ('Remaining', summary.loc['Total', 'Remaining']),
        ('Unallocated', unallocated.sum())]
    for column, (label, value) in zip(st.columns(5), tiles):
        column.metric(label, fmt(value))
    if not plan.to_numpy().any():
        st.info('No group allocations saved yet. Open Plan Allocation to set the plan.')
    if ctx['data'] is None:
        st.caption('Campaign and retail utilization come from registrations. Upload the registration CSV in the sidebar; until then they show — and are left out of totals.')

    st.markdown('### By group')
    st.dataframe(summary.style.format({'Plan': '{:,.0f}', 'Utilized': '{:,.0f}', 'Remaining': '{:,.0f}', '% utilized': '{:.0f}%'},
        na_rep='—').map(lambda v: 'color:#B42318' if isinstance(v, float) and v < 0 else '', subset=['Remaining']), width='stretch')
    st.caption('Utilized: Corporate = places reserved on active orders · Complimentary = slots issued · Campaign and Retail = registrations.')

    st.markdown('### By group and category')
    view = st.segmented_control('Show', ['Plan', 'Utilized', 'Remaining'], default='Remaining', key='summary_view') or 'Remaining'
    matrix = {'Plan': plan, 'Utilized': utilized, 'Remaining': plan - utilized}[view].copy()
    matrix.loc['Total'] = matrix.sum(min_count=1)
    matrix['Total'] = matrix.sum(axis=1, min_count=1)
    st.dataframe(style_numbers(matrix), width='stretch')
    capacity_rows = pd.DataFrame([capacity, plan.sum(), unallocated], index=['Capacity', 'Planned for groups', 'Unallocated'])
    capacity_rows['Total'] = capacity_rows.sum(axis=1)
    st.dataframe(style_numbers(capacity_rows), width='stretch')
    st.download_button('Download ' + view.lower() + ' table', matrix.to_csv(), f'executive-{view.lower()}.csv', 'text/csv')

    st.markdown('### Gaps')
    items = gaps(plan, utilized, capacity, ctx['attributed'])
    if not items:
        st.success('No gaps found.')
    for level, message in items:
        getattr(st, level)(message)

    attributed = ctx['attributed']
    if attributed is not None:
        with st.expander('Conflicts & data quality'):
            unmapped = int(attributed['Planning Category'].eq('Unmapped').sum())
            conflicts = attributed[attributed['Conflict']]
            st.write(f'{len(attributed):,} registrations · {unmapped:,} with an unrecognised category (not counted in any group) · '
                f'{len(conflicts):,} matched more than one group (each counted once, in the higher-priority group).')
            if len(conflicts):
                table = conflicts.groupby(['Group', 'Subgroup', 'Other Matches']).size().rename('Registrations').reset_index()
                st.dataframe(table, hide_index=True, width='stretch')
```

### Task 11: Plan Allocation view — `views/plan_allocation.py`
```python
"""Executive-owned plan: category capacity and group allocations."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from planning.categories import GROUPS, PLANNING_CATEGORIES
from views.common import save_doc, style_numbers


def plan_frame(plan_doc):
    rows = [{'Row': 'Capacity', **plan_doc['capacity']}]
    rows += [{'Row': group, **plan_doc['allocation'].get(group, {})} for group in GROUPS]
    return pd.DataFrame(rows, columns=['Row'] + PLANNING_CATEGORIES).fillna(0)


def frame_to_plan(frame):
    values = frame.set_index('Row')[PLANNING_CATEGORIES]
    if values.isna().any().any():
        raise ValueError('Every cell needs a number (use 0 for none).')
    row = lambda name: {category: int(values.loc[name, category]) for category in PLANNING_CATEGORIES}
    return {'capacity': row('Capacity'), 'allocation': {group: row(group) for group in GROUPS}}


def render_plan_allocation(ctx):
    st.subheader('Plan Allocation')
    plan_doc = ctx['docs']['plan']
    st.caption(f"Saved revision {plan_doc['revision']} · {plan_doc.get('saved_at', 'not saved yet')}")
    st.caption('Set total capacity per category, then allocate places to each group. Stakeholders split their allocation inside their own tab.')
    edited = st.data_editor(plan_frame(plan_doc), hide_index=True, disabled=['Row'], width='stretch',
        key=f"plan_editor_{plan_doc['revision']}",
        column_config={c: st.column_config.NumberColumn(min_value=0, step=1, required=True) for c in PLANNING_CATEGORIES})
    try:
        changed = frame_to_plan(edited)
    except ValueError as error:
        st.error(str(error))
        return
    capacity = pd.Series(changed['capacity'])
    allocated = pd.DataFrame(changed['allocation']).T.sum()
    check = pd.DataFrame([allocated, capacity - allocated], index=['Allocated to groups', 'Unallocated'])[PLANNING_CATEGORIES]
    check['Total'] = check.sum(axis=1)
    st.dataframe(style_numbers(check), width='stretch')
    if (capacity - allocated).lt(0).any():
        st.error('Group allocations exceed capacity in at least one category. You can still save, but the plan is oversold.')
    note = st.text_input('Note for this save (optional)', key='plan_note')
    if st.button('Save plan', type='primary'):
        save_doc('plan', plan_doc | changed, 'Plan saved' + (': ' + note.strip() if note.strip() else ''))
    st.download_button('Download plan (CSV)', edited.to_csv(index=False), 'plan-allocation.csv', 'text/csv')
    if plan_doc['history']:
        with st.expander('Save history'):
            st.dataframe(pd.DataFrame(plan_doc['history'][::-1]), hide_index=True, width='stretch')
```

### Task 12: Complimentary view — `views/complimentary.py`
```python
"""Complimentary programmes: tag links, issued slots and registrations."""
from __future__ import annotations

import uuid
from datetime import date

import pandas as pd
import streamlit as st

from planning.categories import PLANNING_CATEGORIES
from planning.metrics import sum_quantities
from views.common import needs_upload, quantity_editor, save_doc, target_strip


def _registered(attributed, programme):
    if attributed is None:
        return None
    rows = attributed[attributed['Group'].eq('Complimentary') & attributed['Subgroup'].eq(programme)]
    return rows['Planning Category'].value_counts()


def render_complimentary(ctx):
    st.subheader('Complimentary')
    target_strip(ctx, 'Complimentary')
    doc = ctx['docs']['complimentary']
    programmes, issuances = doc['programmes'], doc['issuances']
    names = {p['id']: p['name'] for p in programmes}
    data = ctx['data']
    found = [] if data is None else sorted(data['Complimentary Programme'].dropna().astype(str).str.strip().loc[lambda s: s.ne('')].unique())
    linked = {tag.casefold() for p in programmes for tag in p['tags']}
    unlinked = [tag for tag in found if tag.casefold() not in linked]
    overview, manage, issue, activity = st.tabs(['Overview', 'Programmes', 'Record issuance', 'Activity'])

    with overview:
        if not programmes:
            st.info('No programmes yet. Add one under Programmes.')
        rows, detail = [], []
        for p in programmes:
            issued = sum_quantities([i for i in issuances if i['programme_id'] == p['id']])
            registered = _registered(ctx['attributed'], p['name'])
            reg_total = None if registered is None else int(registered.sum())
            rows.append({'Programme': p['name'], 'Issued': int(issued.sum()), 'Registered': reg_total,
                'Conversion %': reg_total / issued.sum() * 100 if reg_total is not None and issued.sum() else None})
            for category in PLANNING_CATEGORIES:
                reg = None if registered is None else int(registered.get(category, 0))
                if issued[category] or reg:
                    detail.append({'Programme': p['name'], 'Category': category, 'Issued': int(issued[category]), 'Registered': reg})
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch',
                column_config={'Conversion %': st.column_config.NumberColumn(format='%.0f%%')})
            with st.expander('By category'):
                st.dataframe(pd.DataFrame(detail), hide_index=True, width='stretch')
        if unlinked:
            st.warning(f'{len(unlinked)} complimentary tags in the registration data are not linked to a programme: {", ".join(unlinked)}')
        needs_upload(ctx)

    with manage:
        with st.form('comp_new_programme', clear_on_submit=True):
            st.markdown('**Add programme**')
            name = st.text_input('Programme name')
            tags = st.multiselect('Registration tags (COMPLIMENTARY_…)', unlinked, help='Tags found in the uploaded registration data.')
            notes = st.text_area('Notes')
            if st.form_submit_button('Add programme'):
                changed = doc | {'programmes': programmes + [{'id': uuid.uuid4().hex, 'name': name.strip(), 'tags': tags, 'notes': notes}]}
                save_doc('complimentary', changed, 'Programme added: ' + name.strip())
        if programmes:
            key = st.selectbox('Edit programme', list(names), format_func=names.get, key='comp_edit_programme')
            programme = next(p for p in programmes if p['id'] == key)
            with st.form('comp_programme_' + key):
                name = st.text_input('Programme name', programme['name'])
                tags = st.multiselect('Registration tags', sorted(set(unlinked + programme['tags'])), default=programme['tags'])
                notes = st.text_area('Notes', programme.get('notes', ''))
                if st.form_submit_button('Save programme'):
                    updated = [p | {'name': name.strip(), 'tags': tags, 'notes': notes} if p['id'] == key else p for p in programmes]
                    save_doc('complimentary', doc | {'programmes': updated}, 'Programme updated: ' + name.strip())

    with issue:
        if not programmes:
            st.info('Add a programme first.')
        else:
            with st.form('comp_new_issuance', clear_on_submit=True):
                st.markdown('**Record slots given out**')
                programme_id = st.selectbox('Programme', list(names), format_func=names.get)
                issued_on = st.date_input('Date issued', value=date.today(), max_value=date.today())
                recipient = st.text_input('Recipient or batch', help='For example: "KOL batch 1" or a partner name.')
                quantities = quantity_editor('comp_new_quantities')
                notes = st.text_area('Notes')
                if st.form_submit_button('Save issuance'):
                    item = {'id': uuid.uuid4().hex, 'programme_id': programme_id, 'date': issued_on.isoformat(),
                        'recipient': recipient.strip(), 'quantities': quantities, 'notes': notes, 'cancelled': False, 'cancel_reason': ''}
                    save_doc('complimentary', doc | {'issuances': issuances + [item]}, f'Issuance recorded: {names[programme_id]}')
            if issuances:
                labels = {i['id']: f"{names.get(i['programme_id'], '?')} · {i['date']} · {i['recipient'] or 'no recipient'}" for i in issuances}
                key = st.selectbox('Edit or cancel an issuance', list(labels)[::-1], format_func=labels.get, key='comp_edit_issuance')
                item = next(i for i in issuances if i['id'] == key)
                with st.form('comp_issuance_' + key):
                    issued_on = st.date_input('Date issued', value=date.fromisoformat(item['date']), max_value=date.today())
                    recipient = st.text_input('Recipient or batch', item['recipient'])
                    quantities = quantity_editor('comp_quantities_' + key, item['quantities'])
                    notes = st.text_area('Notes', item.get('notes', ''))
                    cancelled = st.checkbox('Cancel this issuance (slots no longer count as utilized)', value=item.get('cancelled', False))
                    reason = st.text_input('Cancellation reason', item.get('cancel_reason', ''))
                    if st.form_submit_button('Save changes'):
                        updated = [i | {'date': issued_on.isoformat(), 'recipient': recipient.strip(), 'quantities': quantities,
                            'notes': notes, 'cancelled': cancelled, 'cancel_reason': reason.strip()} if i['id'] == key else i for i in issuances]
                        save_doc('complimentary', doc | {'issuances': updated}, 'Issuance updated: ' + labels[key])

    with activity:
        if issuances:
            log = pd.DataFrame([{'Date': i['date'], 'Programme': names.get(i['programme_id'], '?'), 'Recipient': i['recipient'],
                'Places': sum(i['quantities'].values()), 'Cancelled': i.get('cancelled', False), 'Notes': i.get('notes', ''),
                **{c: i['quantities'].get(c, 0) for c in PLANNING_CATEGORIES}} for i in issuances]).sort_values('Date', ascending=False)
            st.dataframe(log, hide_index=True, width='stretch')
            st.download_button('Download issuance log', log.to_csv(index=False), 'complimentary-issuances.csv', 'text/csv')
        else:
            st.info('No issuances recorded yet.')
```

### Task 13: Campaigns view — `views/campaigns.py`
```python
"""Promo-code campaigns: shared or unique codes, registrations and unmatched codes."""
from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from planning.campaign_codes import read_code_file
from planning.categories import PLANNING_CATEGORIES
from planning.metrics import unmatched_codes
from views.common import needs_upload, save_doc, target_strip

PROMO_FOLDER = Path(__file__).resolve().parent.parent / 'promo_lists'


def _iso(value):
    return value.isoformat() if value else None


def _date(value):
    return date.fromisoformat(value) if value else None


def seed_campaigns():
    """Build unique-code campaigns from the legacy promo_lists folder (one-time import)."""
    campaigns = []
    for file in sorted(PROMO_FOLDER.glob('*.xlsx')):
        parsed = read_code_file(file.name, file.read_bytes())
        campaigns.append({'id': uuid.uuid4().hex, 'name': file.stem, 'type': 'unique', 'codes': parsed['codes'],
            'cap': parsed['cap'], 'start': None, 'end': parsed['end'], 'notes': 'Imported from promo_lists'})
    return campaigns


def render_campaigns(ctx):
    st.subheader('Campaigns')
    target_strip(ctx, 'Campaign')
    doc = ctx['docs']['campaigns']
    campaigns = doc['campaigns']
    names = {c['id']: c['name'] for c in campaigns}
    attributed = ctx['attributed']
    overview, manage, codes_tab, unmatched_tab = st.tabs(['Overview', 'Campaigns', 'Codes', 'Unmatched codes'])

    with overview:
        if not campaigns:
            st.info('No campaigns yet. Create one under Campaigns.')
            if PROMO_FOLDER.exists() and any(PROMO_FOLDER.glob('*.xlsx')) and st.button('Import existing KL Half code lists (one-time)'):
                try:
                    seeded = seed_campaigns()
                except (ValueError, OSError, KeyError) as error:
                    st.error(f'Import failed: {error}')
                else:
                    save_doc('campaigns', doc | {'campaigns': seeded}, 'Imported promo_lists campaigns')
        else:
            registered = None
            if attributed is not None:
                rows = attributed[attributed['Group'].eq('Campaign')]
                registered = pd.crosstab(rows['Subgroup'], rows['Planning Category']).reindex(columns=PLANNING_CATEGORIES, fill_value=0)
            table = []
            for c in campaigns:
                counts = registered.loc[c['name']] if registered is not None and c['name'] in registered.index else None
                total = None if registered is None else int(counts.sum()) if counts is not None else 0
                table.append({'Campaign': c['name'], 'Type': c['type'], 'Codes': len(c['codes']), 'Cap': c.get('cap'),
                    'Registrations': total, 'Uses left': c['cap'] - total if c.get('cap') is not None and total is not None else None,
                    'Starts': c.get('start'), 'Closes': c.get('end'),
                    **{cat: (None if registered is None else int(counts[cat]) if counts is not None else 0) for cat in PLANNING_CATEGORIES}})
            st.dataframe(pd.DataFrame(table), hide_index=True, width='stretch')
            st.caption('Registrations count once per participant. Participants also tagged corporate or complimentary stay in that group and are listed as conflicts in the Executive Summary.')
            needs_upload(ctx)

    with manage:
        with st.form('campaign_new', clear_on_submit=True):
            st.markdown('**Create campaign**')
            name = st.text_input('Campaign name', placeholder='Early Bird')
            kind = st.radio('Code type', ['shared', 'unique'], horizontal=True,
                format_func={'shared': 'Shared code(s) — e.g. EARLYBIRD', 'unique': 'Unique codes — upload a list'}.get)
            start = st.date_input('Start date (optional)', value=None)
            end = st.date_input('End date (optional)', value=None)
            cap = st.number_input('Cap on registrations (0 = no cap)', min_value=0, step=1)
            notes = st.text_area('Notes')
            if st.form_submit_button('Create campaign'):
                item = {'id': uuid.uuid4().hex, 'name': name.strip(), 'type': kind, 'codes': [], 'cap': int(cap) or None,
                    'start': _iso(start), 'end': _iso(end), 'notes': notes}
                save_doc('campaigns', doc | {'campaigns': campaigns + [item]}, 'Campaign created: ' + name.strip())
        if campaigns:
            key = st.selectbox('Edit campaign', list(names), format_func=names.get, key='campaign_edit')
            c = next(c for c in campaigns if c['id'] == key)
            with st.form('campaign_' + key):
                name = st.text_input('Campaign name', c['name'])
                start = st.date_input('Start date (optional)', value=_date(c.get('start')))
                end = st.date_input('End date (optional)', value=_date(c.get('end')))
                cap = st.number_input('Cap on registrations (0 = no cap)', min_value=0, step=1, value=c.get('cap') or 0)
                notes = st.text_area('Notes', c.get('notes', ''))
                delete = st.checkbox('Delete this campaign and its codes')
                if st.form_submit_button('Save campaign'):
                    if delete:
                        save_doc('campaigns', doc | {'campaigns': [x for x in campaigns if x['id'] != key]}, 'Campaign deleted: ' + c['name'])
                    else:
                        updated = [x | {'name': name.strip(), 'start': _iso(start), 'end': _iso(end), 'cap': int(cap) or None, 'notes': notes}
                            if x['id'] == key else x for x in campaigns]
                        save_doc('campaigns', doc | {'campaigns': updated}, 'Campaign updated: ' + name.strip())

    with codes_tab:
        if not campaigns:
            st.info('Create a campaign first.')
        else:
            key = st.selectbox('Campaign', list(names), format_func=names.get, key='campaign_codes')
            c = next(c for c in campaigns if c['id'] == key)
            st.caption(f"{len(c['codes']):,} codes · matching is exact and case-sensitive after trimming spaces.")
            if c['codes']:
                st.dataframe(pd.DataFrame({'Code': c['codes'][:500]}), hide_index=True, height=200)

            def replace_codes(new_codes, action, cap=None):
                updated = [x | {'codes': new_codes} | ({'cap': cap} if cap is not None and x.get('cap') is None else {})
                    if x['id'] == key else x for x in campaigns]
                save_doc('campaigns', doc | {'campaigns': updated}, action)

            if c['type'] == 'shared':
                with st.form('codes_add_' + key, clear_on_submit=True):
                    text = st.text_area('Add codes, one per line')
                    if st.form_submit_button('Add codes'):
                        new = [line.strip() for line in text.splitlines() if line.strip()]
                        replace_codes(list(dict.fromkeys(c['codes'] + new)), f"Codes added to {c['name']}")
            else:
                upload = st.file_uploader('Upload unique codes (.csv or .xlsx with a "Promo Code" column)', type=['csv', 'xlsx'], key='codes_file_' + key)
                if upload is not None:
                    try:
                        parsed = read_code_file(upload.name, upload.getvalue())
                    except (ValueError, KeyError) as error:
                        st.error(f'Cannot read this file: {error}')
                    else:
                        existing = set(c['codes'])
                        fresh = [code for code in parsed['codes'] if code not in existing]
                        st.write(f"{len(parsed['codes']):,} codes read · {len(fresh):,} new · {parsed['skipped']:,} blank or duplicate rows skipped"
                            + (f" · allowed uses in file: {parsed['cap']:,}" if parsed['cap'] is not None else ''))
                        if fresh and st.button(f'Add {len(fresh):,} codes', key='codes_upload_' + key):
                            replace_codes(c['codes'] + fresh, f"{len(fresh)} codes uploaded to {c['name']}", parsed['cap'])
            with st.form('codes_remove_' + key, clear_on_submit=True):
                text = st.text_area('Remove codes, one per line')
                remove_all = st.checkbox('Remove all codes from this campaign')
                if st.form_submit_button('Remove codes'):
                    drop = set(c['codes']) if remove_all else {line.strip() for line in text.splitlines()}
                    replace_codes([code for code in c['codes'] if code not in drop], f"Codes removed from {c['name']}")

    with unmatched_tab:
        if not needs_upload(ctx):
            table = unmatched_codes(attributed).rename_axis('Promo code').reset_index(name='Registrations')
            st.caption('Promo codes used in registrations that no campaign claims yet (e.g. Medic codes). Add them to a campaign to track them.')
            st.dataframe(table, hide_index=True, width='stretch')
            st.download_button('Download unmatched codes', table.to_csv(index=False), 'unmatched-codes.csv', 'text/csv')
```

### Task 14: Corporate Sales on the new context

**Files:** Modify `corporate_sales.py`

- Imports: replace `from sales_backend import ...` with
```python
from planning.categories import PLANNING_CATEGORIES, convert_quantities, to_planning_category
from views.common import save_doc, target_strip
```
- Delete `SALES_PATH`. New function head (replaces everything up to `companies=records['companies']...`):
```python
def render_corporate_sales(ctx):
    data = ctx['data'] if ctx['data'] is not None else pd.DataFrame(columns=['Corporate Group', 'Grouped Category'])
    st.subheader('Corporate Sales')
    st.caption('Reservations → verified payments → registration links → utilization. Reserved places count as utilized in the Executive Summary.')
    target_strip(ctx, 'Corporate')
    records = ctx['docs']['corporate']
    for order in records['orders']:
        order['quantities'] = convert_quantities(order['quantities'])

    def commit(changed, action):
        save_doc('corporate', changed, action)
    st.caption(f"Saved revision {records['revision']} · {records.get('saved_at','No records saved yet')}")
    st.download_button('Download sales backup', json.dumps(records, indent=2), 'corporate-sales-backup.json', 'application/json')
```
- `categories=list(dict.fromkeys(PLANNING_CATEGORIES+[c for o in orders for c in o['quantities']]))`
- `summary['Group target']=summary.Category.map(ctx['plan'].loc['Corporate']).fillna(0).astype(int)`; remove the "Set group sales targets" expander; overview warning text: 'Reserved places exceed the Corporate plan in one or more categories. Ask the executive to review the plan before taking further orders.'
- Company utilization: `actual['Grouped Category'].map(to_planning_category).value_counts()`; delete the `subtype unconfirmed` line.

### Task 15: Navigation + app routing + retire slot planning

**Files:** Modify `admin_dashboard.py`, `app.py`; delete `slot_planning.py`

`admin_dashboard.py`: delete `clean_codes`, `campaign_files`, `allocation_summary`, `render_admin` and unused imports (`json`, `Path`, `px`); replace `workspace_navigation` with:
```python
SECTIONS = [
    ('PLANNING', [
        ('Executive Summary', 'space_dashboard', 'Plan, utilized and remaining by group and category'),
        ('Plan Allocation', 'tune', 'Category capacity and group allocations'),
    ]),
    ('STAKEHOLDERS', [
        ('Corporate Sales', 'business_center', 'Companies, orders, top-ups, payment milestones and utilization'),
        ('Complimentary', 'redeem', 'Complimentary programmes, slots issued and registrations'),
        ('Campaigns', 'campaign', 'Promo-code campaigns, codes and registrations'),
    ]),
    ('ANALYTICS', [
        ('Overview', 'dashboard', 'Registration totals, momentum and category performance'),
        ('Daily registration', 'monitoring', 'Daily trends, cumulative growth and registration timing'),
        ('Groups & complimentary', 'groups', 'Group registrations, complimentary programmes and add-ons'),
        ('Audience & markets', 'public', 'Participant demographics, countries and market mix'),
        ('Reports & data', 'description', 'Management exports, registration tracker and data quality'),
    ]),
]


def workspace_navigation():
    """Render grouped navigation tiles with an explicit selected state."""
    if 'workspace_page' not in st.session_state:
        st.session_state.workspace_page = 'Corporate Sales' if st.query_params.get('sales_view') else 'Executive Summary'

    def select_page(name):
        st.session_state.workspace_page = name
        if name != 'Corporate Sales':
            for key in ['sales_view', 'sales_order']:
                if key in st.query_params:
                    del st.query_params[key]

    with st.sidebar.container(key='workspace_navigation'):
        for heading, pages in SECTIONS:
            st.caption(heading)
            for name, icon, description in pages:
                st.button(name, icon=f':material/{icon}:', help=description,
                    type='primary' if st.session_state.workspace_page == name else 'secondary',
                    use_container_width=True, key='workspace_' + icon, on_click=select_page, args=(name,))
    return st.session_state.workspace_page
```

`app.py`:
1. Imports: remove the `corporate_sales` and `slot_planning` imports; `from admin_dashboard import style_dashboard, workspace_navigation, render_chart`; add `from planning.categories import PLANNING_CATEGORIES` and `from views.router import PLANNING_PAGES, render_planning_page`.
2. Replace the session `allocation_plan` override (lines 307–310) with:
```python
# Overview pacing targets follow the saved plan capacity (same order as TARGET_GROUPS).
try:
    from views.common import get_doc
    _plan_capacity = get_doc("plan")["capacity"]
    for _planning_category, _target_group in zip(PLANNING_CATEGORIES, TARGET_GROUPS):
        CATEGORY_TARGETS[_target_group] = int(_plan_capacity.get(_planning_category, CATEGORY_TARGETS[_target_group]))
except (OSError, ValueError, KeyError):
    pass  # Keep built-in targets; planning pages show the storage error.
```
3. In the `uploaded_file is None` block replace the Corporate Sales special case with:
```python
    if page in PLANNING_PAGES:
        render_planning_page(page, None, None)
        st.stop()
```
4. Line ~4808 caption: remove the `Slots & campaigns` suffix expression.
5. Delete `bundled_promo_campaigns = load_bundled_promo_lists()`, the `Slots & campaigns` `render_admin` block, and the whole "TAB 6.5: PROMO CAMPAIGN AUDIT" section (up to "TAB 7: REGISTRATION TIMING"). Replace the Corporate Sales / Slot Planning routing with:
```python
if page in PLANNING_PAGES:
    render_planning_page(page, prepared_df, promo_code_column)
```
6. `git rm slot_planning.py`.

- [ ] Run `.venv/Scripts/python -m pytest -q` → PASS
- [ ] Commit `git add -A && git commit -m "feat: planning pages, grouped navigation, retire slot planning"`

### Task 16: AppTest smoke tests — `tests/test_pages.py`
```python
import pytest
from streamlit.testing.v1 import AppTest

PAGES = ['Executive Summary', 'Plan Allocation', 'Corporate Sales', 'Complimentary', 'Campaigns']


def page_script(page, with_data):
    import pandas as pd
    from views.router import render_planning_page
    data = None
    if with_data:
        data = pd.DataFrame({
            'Grouped Category': ['BYD Marathon', '5km', 'adidas Half Marathon', 'Kids Dash Non-Competitive 600m'],
            'Corporate Group': ['Acme', None, None, None],
            'Complimentary Programme': [None, 'KOL', None, None],
            'Market': ['Singapore', 'Singapore', 'International', 'Singapore'],
            'Promo': ['', '', 'EARLY', ''],
            'Registration Date Only': pd.to_datetime(['2026-09-01'] * 4),
        })
    render_planning_page(page, data, 'Promo' if with_data else None)


@pytest.mark.parametrize('page', PAGES)
@pytest.mark.parametrize('with_data', [False, True])
def test_page_renders(page, with_data, local_store):
    app = AppTest.from_function(page_script, args=(page, with_data), default_timeout=30)
    app.run()
    assert not app.exception, app.exception


def test_app_without_upload_opens_executive_summary(local_store):
    app = AppTest.from_file('../app.py', default_timeout=60)
    app.run()
    assert not app.exception, app.exception
    assert any('Executive Summary' in s.value for s in app.subheader)
```
- [ ] Run → PASS; commit `git add tests/test_pages.py && git commit -m "test: planning page smoke tests"`

### Task 17: Deployment docs

- `secrets.example.toml`: add `require_supabase = true` under `[sales_storage]`.
- `README.md`: update the file list (planning/, views/, doc_store.py; remove slot_planning.py) and add test instructions.
- `CLOUD_TRIAL_GUIDE.md`: rerun `supabase_setup.sql` (adds planning documents); `require_supabase`; persistence list (plan, complimentary, campaigns now persistent); one-time KL Half import, then delete `promo_lists/` from the repo.
- Commit `docs: deployment notes for planning redesign`.

### Task 18: Deploy (needs the user)

1. User runs the updated `supabase_setup.sql` in the Supabase SQL Editor.
2. User adds `require_supabase = true` in Streamlit Secrets.
3. Push the branch and merge to `main` (Streamlit Cloud redeploys from `main`).
4. Acceptance: Executive Summary shows "Storage: Supabase"; save plan; add comp programme + issuance; import KL Half campaigns; reload in a fresh session and confirm persistence; upload CSV and check totals.
5. After the import is confirmed: `git rm -r promo_lists` and push.
