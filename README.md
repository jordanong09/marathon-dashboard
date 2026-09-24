# Marathon Management Dashboard

Clean deployment copy for a **private, company-owned GitHub repository**.

## Files
- `app.py`: Streamlit entry point, registration CSV preparation and analytics pages.
- `admin_dashboard.py`: dashboard styling, grouped navigation and chart rendering.
- `planning/`: pure planning logic — the six planning categories, registration attribution (Corporate → Complimentary → Campaign → Retail), plan/utilized/remaining metrics and promo-code list parsing.
- `views/`: Executive Summary, Plan Allocation, Complimentary and Campaigns pages, shared helpers and the page router.
- `corporate_sales.py`: company orders, invoices, payment stages and top-ups (targets come from the plan).
- `doc_store.py`: saved plan, complimentary and campaign records (local JSON for development, Supabase when deployed).
- `sales_store.py`: local JSON persistence and sales validation.
- `sales_backend.py`: storage settings and Supabase calls.
- `event_logo.png`, `promo_lists/`: logo and the two KL Half code lists (import once into Campaigns, then delete — see the trial guide).
- `tests/`: unit and page tests (`python -m pip install -r requirements-dev.txt`, then `python -m pytest`).
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
Follow `CLOUD_TRIAL_GUIDE.md`. Deploy `app.py` with Python 3.13 and enter real secrets only in Streamlit's Secrets settings. This copy contains real special campaign codes, so keep it private. App access must also be set to private separately.

Do not upload the original runtime folder, backups, master registration CSVs or sales JSON files. They are not needed to deploy. Existing local data is not automatically copied or synchronized.

Supabase integration is prepared and locally tested with simulated API responses. A live project connection and database acceptance test are still required before the company trial.
