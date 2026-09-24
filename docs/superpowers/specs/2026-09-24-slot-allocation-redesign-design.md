# Slot Allocation Redesign — Design

Date: 2026-09-24 · Status: approved in brainstorming · Target: trial live by 30 Sep 2026, foundation for next edition.

## Goal

Make the executive's **plan allocation** the single source of truth. Each stakeholder tab (Corporate, Complimentary, Campaigns) records what it has committed and sees its target from the plan. The **Executive Summary** shows plan, utilized and remaining for every group and category, and highlights gaps.

All user-entered data persists in Supabase. Only registration data is uploaded (CSV today; export/API later).

## 1. Planning model

### Categories (6)

| Planning category | Source categories (`assign_grouped_category` output) |
|---|---|
| Full Marathon | BYD Marathon, BYD Marathon Crew Challenge |
| Half Marathon | adidas Half Marathon |
| 10 km | Standard Chartered 10km |
| 5 km | 5km |
| Kids 1.6 km | Kids Dash Competitive 1.6KM, Kids Dash Non-Competitive 1.6KM |
| Kids 600 m | Kids Dash Non-Competitive 600m |

Anything else is `Unmapped`. It is counted and flagged in data quality, but not in any group.

### Groups (5)

Corporate, Complimentary, Campaign, Local Retail, International Retail.

### Plan (executive-owned)

- `capacity[category]`: total places per category. Seeded from the current `CATEGORY_TARGETS` (13000 / 19000 / 9000 / 7000 / 1500 / 2500).
- `allocation[group][category]`: planned places, whole numbers ≥ 0.
- `Unallocated[category] = capacity − Σ allocation`. A negative value (oversold) gives a red warning; saving is still allowed.

Stakeholders split their group into subgroups (companies, programmes, campaigns) inside their own tab. The executive plan is **group level only**.

### Utilized (Executive Summary definition)

| Group | Utilized |
|---|---|
| Corporate | Places reserved on non-cancelled orders (payment not required) |
| Complimentary | Slots recorded as issued (non-cancelled issuances) |
| Campaign | Registrations attributed to the campaign |
| Local / International Retail | Registrations attributed to retail, by `Market` (country of residence) |

`Remaining = plan − utilized`, per group × category. Negative values mean over-allocation and are shown in red.

### Attribution (each registration counted exactly once)

Priority order:

1. **Corporate:** the `Corporate Group` value is non-empty (a `GROUP_REGISTRATION_` row). Subgroup = the linked company if one of its aliases matches (case-insensitive), otherwise `Unlinked`.
2. **Complimentary:** the `Complimentary Programme` value is non-empty. Subgroup = the programme linked to that tag, otherwise `Unconfigured`.
3. **Campaign:** the cleaned promo code exactly matches a code in a campaign. Subgroup = that campaign.
4. **Retail:** Local if `Market == "Singapore"`, otherwise International (including Unknown).

A registration that matches more than one rule (for example, a corporate tag plus a campaign code) is **flagged as a conflict**. It stays in the higher-priority group and appears in an informational Conflicts list. Group totals + Unmapped always equal the number of registrations.

Unlinked corporate and unconfigured comp registrations count as registered in their group. They are not "utilized" (utilized comes from orders or issuances for those groups). They appear in the Gaps panel.

### Legacy data

Existing corporate orders store quantities under the 8 detailed category names. They are converted to planning categories **when read** by summing. The converted form is written back on the next Corporate Sales save; nothing is rewritten before then.

## 2. Screens

The sidebar navigation has three sections:

- **Planning:** Executive Summary (default landing page), Plan Allocation.
- **Stakeholders:** Corporate Sales, Complimentary, Campaigns.
- **Analytics** (existing, unchanged): Overview, Daily registration, Groups & complimentary, Audience & markets, Reports & data.

**Retired:**
- Management Slot Planning (`slot_planning.py` deleted).
- "Slots & campaigns": its capacity/allocation table and promo audit are replaced by Plan Allocation and Campaigns. The page is removed from navigation.

The registration CSV upload stays in the sidebar and is shared by all pages. Planning and stakeholder pages open **without** an upload. Registration-derived figures then show "Upload registrations".

### Executive Summary (read-only)

- **Tiles:** Capacity · Planned · Utilized · Remaining · Unallocated.
- **Group table:** Plan, Utilized, Remaining, % utilized per group, plus a total row.
- **Detail table:** groups × 6 categories, with a view switch between Plan / Utilized / Remaining. Negative values are red.
- **Gaps panel:**
  - over-allocated cells (remaining < 0)
  - groups with utilization below 50% of plan
  - categories with unallocated capacity > 0
  - oversold categories (unallocated < 0)
  - unlinked corporate names
  - unconfigured comp tags
  - unmatched promo codes
- **Collapsible "Conflicts & data quality" section:** the conflict list (group assigned, other matches), and the Unmapped count.
- Download buttons for each table.

### Plan Allocation (executive edits)

- One editor: a Capacity row plus 5 group rows × 6 categories. A calculated Unallocated row and a Total column are shown underneath.
- Save with an optional note. Shows the revision, last-saved time and save history.
- Download as CSV.

### Stakeholder target strip

A shared component at the top of each stakeholder tab showing Plan / Utilized / Remaining per category for that group.

### Corporate Sales

- The existing workflow is unchanged. Order quantities use the 6 planning categories.
- The target strip replaces the "Set group sales targets" editor. The Overview's "Group target" and "Available to sell" columns come from the plan.
- Company utilization compares registrations by planning category.

### Complimentary (sub-tabs)

- **Overview:** per programme, issued, registered and conversion % by category, plus the target strip.
- **Programmes:** add or edit a programme (unique name, linked `COMPLIMENTARY_` tags chosen from the tags in the upload or kept from before, notes). A tag can be linked to only one programme.
- **Record issuance:** programme, date issued (not in the future), recipient/batch description, quantity per category (at least one > 0), notes. Existing issuances can be edited or cancelled (a reason is required).
- **Activity:** the issuance log, downloadable.

### Campaigns (sub-tabs)

- **Overview:** per campaign, registrations by category, total, cap, uses left and closing date, plus the target strip.
- **Campaigns:** create or edit a campaign (unique name, type `shared` or `unique`, optional start and end dates, optional cap, notes).
- **Codes:**
  - Shared campaigns: type codes, one per line.
  - Unique campaigns: upload a CSV or XLSX with a `Promo Code` column (the optional `Usage` column `n/m` is summed into the cap when the cap is blank). Blank and duplicate rows are dropped, and the result is reported.
  - Codes can be removed.
  - **A code may belong to only one campaign.** A save that would create a clash is rejected, and the clashing codes are listed.
  - Codes are compared exactly after trimming, case-sensitive (matching the existing promo audit).
- **Unmatched codes:** promo codes found in registrations that aren't in any campaign, with counts. This is how the team spots codes such as Medic and adds them as campaigns.

**One-time seed:** the two KL Half xlsx lists in `promo_lists/` are imported as unique-code campaigns, using a button in Campaigns shown only while the campaigns document is empty. After the import is confirmed, the files are deleted from the repo.

### Analytics link

The Overview page's target pacing reads capacity from the saved plan, falling back to the built-in defaults if no plan is saved. The `allocation_plan` session override is removed.

## 3. Architecture

| Unit | Responsibility |
|---|---|
| `planning/categories.py` | `PLANNING_CATEGORIES`, `to_planning_category(name)`, `convert_quantities(dict)` |
| `planning/attribution.py` | `attribute(data, promo_column, corporate_aliases, comp_tags, campaign_codes) -> DataFrame` with columns `Group`, `Subgroup`, `Planning Category`, `Conflict`, `Other Matches`. Pure pandas, no Streamlit |
| `planning/metrics.py` | `plan_matrix`, `utilized_matrix`, `remaining`, `gaps`. Pure functions over the documents + attribution |
| `doc_store.py` | Named-document store with a revision check (`read(name)`, `save(name, data, expected_revision, action)`); local JSON or Supabase; a validator per document |
| `views/common.py` | Target strip, loading/saving helpers, the "upload registrations" placeholder |
| `views/executive_summary.py`, `views/plan_allocation.py`, `views/complimentary.py`, `views/campaigns.py` | The screens |
| `corporate_sales.py` | Switched to the 6 categories and plan targets |
| `admin_dashboard.py` | Grouped navigation; allocation section removed from `render_admin` |
| `app.py` | Routing; planning pages work without an upload; Overview targets come from the plan |

**Registration source boundary:** every page receives the prepared registrations DataFrame from `app.py` (columns: `Grouped Category`, `Corporate Group`, `Complimentary Programme`, `Market`, the promo column, `Registration Date Only`). A future export or API only needs to produce this frame.

### Storage

- **Corporate** stays on the existing `marathon_private.sales` table and RPCs (real records, already tested). Its `targets` field is kept but no longer used.
- **New** `marathon_private.documents(name text primary key, document jsonb)` and `marathon_private.document_revision(name, revision, document, archived_at)`, with RLS enabled and no public grants.
- New RPCs, callable by `service_role` only:
  - `marathon_doc_read(p_name)` returns the document, or an empty seed for `plan`, `complimentary` or `campaigns`.
  - `marathon_doc_save(p_name, p_data, p_expected_revision, p_action)` locks the row, rejects stale revisions (`PT409`), archives the previous version, bumps the revision and appends to history.
- Documents: `plan`, `complimentary`, `campaigns`. Each has `schema_version: 1`, `revision`, `history`, plus its payload. Tabs save independently.
- Local mode: `planning_data/<name>.json`, with the same atomic write, lock and backups as `sales_store`. **For development only.** A banner reads "Local storage — not for real data".
- **Deployed rule:** when the app runs on Streamlit Cloud (detected by the `sales_storage.require_supabase = true` secret), saving is refused unless the backend is Supabase.

### Persistence summary

- **Persisted in Supabase:** plan and history; corporate companies, aliases, orders and workflow; comp programmes, tag links and issuances; campaigns, shared codes and uploaded unique code lists.
- **Not persisted:** the registration CSV (personal data; the app is hosted in the US). All registration-derived numbers are recomputed on each upload.

## 4. Error handling

- No silent fallback: if Supabase fails, the save stops with the existing wording. Stale revisions ask the user to reload.
- All quantities, capacities and caps are whole numbers ≥ 0. Names are unique within a document.
- A code clash across campaigns is rejected, and the clashing codes are listed. A tag linked to two programmes is rejected.
- Upload problems (missing `Promo Code` column, unreadable file) show an error and nothing is saved.
- Missing plan: the Executive Summary shows the plan as 0, with a prompt to open Plan Allocation.

## 5. Testing

- `pytest` unit tests:
  - category mapping and quantity conversion
  - attribution priority, conflicts, unlinked/unconfigured, retail split, Unmapped
  - metrics (plan/utilized/remaining, oversold, negative remaining, gaps)
  - doc_store validation and stale-revision rejection (local)
  - Supabase RPC calls with simulated responses
- Streamlit `AppTest` smoke tests: each new page opens with a synthetic CSV and with no upload.
- No real registration data or codes in test fixtures.

## Out of scope (this trial)

Per-user logins and permissions, named audit trails, per-category eligibility for campaigns, storing registration data, the registration API integration, and splitting up the analytics part of `app.py`.
