# Company trial deployment

Use a PRIVATE company-owned repository and a PRIVATE Streamlit app. Repository privacy and app viewer access are separate settings. Anyone invited to this pilot app can edit sales records; department-specific permissions and named-user audit trails are not implemented yet.

## Setup
1. Upload this bundle's contents to the private repository, including the hidden .streamlit/config.toml and .gitignore. Do not upload master registration CSVs, local sales JSON, real secrets, the Windows Python runtime, or backups. The bundled promo_lists contains real campaign codes: keep the repository private.
2. In the company's Supabase project SQL Editor, run supabase_setup.sql. It creates a private document store and revision archive with two server-only functions. It is safe to rerun without resetting sales records.
3. In Streamlit Community Cloud, connect the company GitHub account/organisation, choose this repository and app.py, and select Python 3.13. Organisation approval may be required for private repository access.
4. In Streamlit app Settings > Secrets, paste secrets.example.toml and replace the URL and key. Use a Supabase server SECRET key (sb_secret_), not the publishable key. Never commit the real secrets file. The adapter uses Supabase's HTTPS Data API, so no database password or PostgreSQL pooler is needed.
5. Set the Streamlit app to private and invite only trial editors. Confirm a non-invited account cannot open it BEFORE loading company records.
6. Open Corporate Sales. It must display Storage: Supabase. Save a sample company/order, reopen in a fresh session and confirm it persists. Test two simultaneous editors: the stale editor must be asked to reload instead of overwriting.

## Bring over existing local sales records
Download the sales backup from the existing local app. Preserve this original file securely. In a local copy of this bundle only, create .streamlit/secrets.toml with the same configuration. Run `python import_sales.py "path/to/corporate-sales-backup.json"`. Import refuses a non-empty destination, validates order milestones, and leaves the original file unchanged. The server assigns new revision numbers; previous history is retained in imported_history. Do not import until you are ready to use the cloud as the shared source of truth. Local-only edits made afterward do not synchronize automatically.

## What is persistent in this trial
- Companies and registration aliases, all orders/top-ups, quantities, invoice details, milestone dates, cancellations, notes, and Corporate Sales group targets.
- Prior saved versions remain in Supabase, and Download sales backup exports the current record.
- Management Slot Planning's saved corporate commitments reads this same cloud store.

The broader planning matrices and other allocation scenarios remain session-based. Registration CSVs remain session uploads and are not stored in Supabase. A fresh browser session needs the master CSV uploaded again for utilization analysis. This trial is not yet full cloud persistence for every tab.

## Operational limits
No silent local fallback: when Supabase is unavailable, saving stops. After an uncertain save, reload to check whether it completed before retrying. Other users see changes after Reload saved sales records; this is not live push synchronization. Revision archives are in the same database, so also download a backup at the end of each trial day. Free-tier availability and limits apply. Streamlit Community Cloud hosts the app in the US, even if Supabase is in Singapore; use a sanitized master sheet unless the company permits this processing location.

## Validation status
Local storage tests, mocked Supabase request/failure tests, and sales UI/navigation tests passed. Database SQL, real API authentication, cloud deployment, and concurrent remote saves still require the live project acceptance test. Do not call the deployment ready until those checks pass.
