# Marathon Management Dashboard

Clean deployment copy for a **private, company-owned GitHub repository**.

## Files
- `app.py`: Streamlit entry point and registration analytics.
- `admin_dashboard.py`: navigation, dashboard styling, charts and campaign views.
- `corporate_sales.py`: company orders, invoices, payment stages and top-ups.
- `slot_planning.py`: management allocation scenarios and corporate commitments.
- `sales_store.py`: local JSON persistence and sales validation.
- `sales_backend.py`: optional Supabase persistence.
- `event_logo.png`, `promo_lists/`: logo and the two required special campaign code lists.
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

Without Supabase configuration, corporate sales saves to `planning_data/corporate_sales.json` in this folder. This starts empty: your existing records remain in the original application folder. Do not use this clean copy for new real sales until your existing records have been migrated and your intended storage is configured.

## Deploy
Follow `CLOUD_TRIAL_GUIDE.md`. Deploy `app.py` with Python 3.13 and enter real secrets only in Streamlit's Secrets settings. This copy contains real special campaign codes, so keep it private. App access must also be set to private separately.

Do not upload the original runtime folder, backups, master registration CSVs or sales JSON files. They are not needed to deploy. Existing local data is not automatically copied or synchronized.

Supabase integration is prepared and locally tested with simulated API responses. A live project connection and database acceptance test are still required before the company trial.
