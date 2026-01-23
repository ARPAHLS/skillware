import os
import csv
import json
import shutil
from datetime import datetime

# Paths relative to this script (skillware/skills/finance/wallet_screening/maintenance/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NEW_NORM_DIR = os.path.join(BASE_DIR, 'new_norm')
PAST_NORM_DIR = os.path.join(BASE_DIR, 'past_norm')
# Data goes up one level to the skill's data folder
DATASETS_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'data'))
LOGS_DIR = os.path.join(BASE_DIR, 'norm_logs')

os.makedirs(NEW_NORM_DIR, exist_ok=True)
os.makedirs(PAST_NORM_DIR, exist_ok=True)
os.makedirs(DATASETS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

def normalize_israel_nbctf_csv(filepath):
    norm = []
    with open(filepath, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('schema', '').strip().lower() == 'wallet':
                address = row.get('account/wallet_id', '').strip().lower()
                if not address:
                    continue
                norm.append({
                    'address': address,
                    'network': row.get('platform', '').strip() or 'Unknown',
                    'label': 'Israel NBCTF',
                    'source': 'Israel NBCTF',
                    'source_url': row.get('order_url', '').strip(),
                    'reason': f"Sanctions Order {row.get('order_id', '').strip()}",
                    'jurisdiction': 'IL',
                    'extra': {k: v for k, v in row.items() if k not in ['account/wallet_id', 'platform', 'order_url', 'order_id']}
                })
    return norm

def normalize_fbi_lazarus_csv(filepath):
    norm = []
    with open(filepath, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            address = row.get('Address', '').strip().lower()
            if not address:
                continue
            norm.append({
                'address': address,
                'network': row.get('Network', '').strip(),
                'label': row.get('Linked to', '').strip() or 'FBI',
                'source': 'FBI',
                'source_url': row.get('Source URL', '').strip(),
                'reason': 'Sanctions/Blacklist',
                'jurisdiction': 'US',
                'extra': {k: v for k, v in row.items() if k not in ['Address', 'Network', 'Linked to', 'Source URL']}
            })
    return norm

def normalize_file(filepath):
    filename = os.path.basename(filepath)
    if 'nbctf' in filename.lower():
        return normalize_israel_nbctf_csv(filepath), 'israel_nbctf'
    elif 'lazarus' in filename.lower():
        return normalize_fbi_lazarus_csv(filepath), 'fbi_lazarus'
    else:
        # Try to guess structure or skip
        return [], None

def main():
    print(f"Scanning for new files in: {NEW_NORM_DIR}")
    log_entries = []
    if not os.path.exists(NEW_NORM_DIR):
         print("No new_norm directory found.")
         return

    files = os.listdir(NEW_NORM_DIR)
    if not files:
        print("No files found to normalize.")
        return

    for fname in files:
        fpath = os.path.join(NEW_NORM_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        norm_data, tag = normalize_file(fpath)
        if norm_data and tag:
            outname = f'normalized_{tag}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            outpath = os.path.join(DATASETS_DIR, outname)
            with open(outpath, 'w', encoding='utf-8') as outf:
                json.dump(norm_data, outf, indent=2, ensure_ascii=False)
            log_entries.append(f"Normalized {fname} to {outname} ({len(norm_data)} entries)")
        else:
            log_entries.append(f"Skipped {fname} (unrecognized format or no data)")
        # Move original to past_norm
        shutil.move(fpath, os.path.join(PAST_NORM_DIR, fname))
    # Write log
    logname = f'normlog_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    logpath = os.path.join(LOGS_DIR, logname)
    with open(logpath, 'w', encoding='utf-8') as logf:
        for entry in log_entries:
            logf.write(entry + '\n')
    print(f"Normalization complete. Log saved to {logpath}")

if __name__ == '__main__':
    main()
