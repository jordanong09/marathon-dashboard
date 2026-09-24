# Marathon Management Dashboard

Clean deployment copy for a **private, company-owned GitHub repository**.

## Files
- `app.py`: Streamlit entry point, registration CSV preparation and analytics pages.
- `admin_dashboard.py`: dashboard styling, grouped navigation and chart rendering.
- `planning/`: pure planning logic — the six planning categories, registration attribution (Corporate → Complimentary → Campaign → Retail), plan/utilized/remaining metrics, company-name matching, corporate utilization by category, complimentary tag capture, promo-code campaign detection, pace to close and management recommendations.
- `views/`: Executive Summary, Plan Allocation, Complimentary and Campaigns pages, shared helpers and the page router.
- `corporate_sales.py`: company orders, invoices, payment stages and top-ups (targets come from the plan).
- `doc_store.py`: saved plan, complimentary and campaign records (local JSON for development, Supabase when deployed).
- `sales_store.py`: local JSON persistence and sales validation.
- `sales_backend.py`: storage settings and Supabase calls.
- `event_logo.png`: event logo.
- `tests/`: unit and page tests (`python -m pip install -r requirements-dev.txt`, then `python -m pytest`).
- `scripts/benchmark.py`: times every page on a synthetic registration file (`python scripts/benchmark.py 60000`). Target: each page responds in about 2 seconds after the CSV has loaded.

## What happens on each registration upload
The CSV is never stored. Each upload is compared with the saved records:
- New `COMPLIMENTARY_` tags are saved as complimentary programmes (or linked to a programme with the same name).
- Promo codes that no campaign claims are grouped into families by their leading letters (RGSIM1, RG-SIM-2 → RGSIM); a lone code keeps its own name (EARLY10). Groups with 5+ registrations are saved as automatic campaigns and later codes of the same family join them; smaller groups wait under Campaigns → Detected codes. Campaigns already saved separately but sharing a family are offered as a one-click merge.
- Company names in `GROUP_REGISTRATION_` rows are matched to Corporate Sales companies, ignoring case, punctuation, bracketed notes and suffixes such as Pte/Ltd; confirm matches under Corporate Sales → Companies.
Saved programmes, campaigns, links, orders and issuances are never removed by an upload.

Utilized means places reserved on orders for Corporate, and registrations for Complimentary, Campaign and Retail. Complimentary and Campaigns each show a programme/campaign × race category table of registrations, sorted by sign-ups. The Executive Summary turns the plan, utilization and the last 14 days of activity into pace to close and recommendations. The registration close date is set in Plan Allocation.
- `docs/superpowers/`: design spec and implementation plan for the slot allocation redesign.
- `.streamlit/config.toml`: theme and Streamlit settings.
- `requirements.txt`: dependencies matched to the tested application.
- `supabase_setup.sql`, `secrets.example.toml`, `import_sales.py`: cloud database setup and controlled import.
- `CLOUD_TRIAL_GUIDE.md`: deployment, privacy settings, migration and acceptance checks.
- `.gitignore`: excludes local records, secrets, logs and runtime files.

## Run locally
Install Python 3.13, open a terminal in this folder, then:

```text
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The original application's bundled Python can also run this copy using its full executable path. This clean folder deliberately does not duplicate that large Windows runtime.

Without Supabase configuration, records save to `planning_data/` in this folder (`corporate_sales.json`, `plan.json`, `complimentary.json`, `campaigns.json`) and every planning page shows a "Local storage — not for real data" banner. This starts empty: your existing records remain in the original application folder. Do not use this clean copy for new real sales until your existing records have been migrated and your intended storage is configured.

## Deploy
Follow `CLOUD_TRIAL_GUIDE.md`. Deploy `app.py` with Python 3.13 and enter real secrets only in Streamlit's Secrets settings. Campaign codes now live in Supabase, but older commits still contain the former code lists, so keep the repository private. App access must also be set to private separately.

Do not upload the original runtime folder, backups, master registration CSVs or sales JSON files. They are not needed to deploy. Existing local data is not automatically copied or synchronized.
