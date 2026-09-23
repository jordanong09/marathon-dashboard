"""One-time import into an empty Supabase store; run from the project directory."""
from pathlib import Path
import argparse
import sales_store
import sales_backend

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('backup',type=Path)
    args=parser.parse_args()
    if sales_backend.storage_label()!='Supabase':
        raise SystemExit('Set Supabase storage in .streamlit/secrets.toml first.')
    source=sales_store.read_store(args.backup) if args.backup.is_file() else None
    if source is None:
        raise SystemExit('Backup file does not exist.')
    current=sales_backend.read_store(args.backup)
    if current['revision']!=0 or current['companies'] or current['orders'] or current['targets']:
        raise SystemExit('Import stopped: the destination already has records.')
    # Preserve source history in a separate field; the server owns revision history.
    source['imported_history']=source.get('history',[])
    sales_backend.save_store(args.backup,source,0,'Imported existing local sales backup')
    print('Import complete. Keep your original local backup.')
