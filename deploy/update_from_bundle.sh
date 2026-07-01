#!/bin/sh
# Runs ON the server after you push a fresh bundle (see DEPLOY.md):
#
#   fly ssh console -C "sh /app/deploy/update_from_bundle.sh"
#
# First boot (no live DB yet): installs the full bundle, DB included.
# Updates: replaces models/CSVs wholesale, but MERGES the DB — only the shared
# tables (results, cards, odds, saved predictions) are refreshed; accounts, picks,
# and friendships created on the server are preserved.
set -e

BUNDLE="${1:-/data/bundle.tar.gz}"
DATA_ROOT="${DATA_ROOT:-/data}"
INCOMING="$DATA_ROOT/_incoming"

if [ ! -f "$BUNDLE" ]; then
    echo "Bundle not found: $BUNDLE"
    echo "Push it first:  fly ssh sftp put deploy/deploy_bundle.tar.gz /data/bundle.tar.gz"
    exit 1
fi

rm -rf "$INCOMING"
mkdir -p "$INCOMING"
tar -xzf "$BUNDLE" -C "$INCOMING"

if [ -f "$DATA_ROOT/data/app.db" ]; then
    echo "Live DB found - merging shared tables (accounts/picks preserved)..."
    (cd /app/backend && python -c "
import os
from app.db.bundle_sync import sync_shared_tables
root = os.environ.get('DATA_ROOT', '/data')
replaced = sync_shared_tables(f'{root}/data/app.db', f'{root}/_incoming/data/app.db')
for table, rows in replaced.items():
    print(f'  {table}: {rows} rows')
")
    rm -f "$INCOMING/data/app.db"
else
    echo "No live DB - first boot, installing the full bundle."
fi

# Models + CSVs are global artifacts: overwrite wholesale.
cp -r "$INCOMING/." "$DATA_ROOT/"
rm -rf "$INCOMING" "$BUNDLE"
echo "Done. The server hot-reloads changed model/data files automatically."
