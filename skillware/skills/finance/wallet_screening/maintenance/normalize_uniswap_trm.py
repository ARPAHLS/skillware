import csv
import json
import os

# Paths relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NEW_NORM_DIR = os.path.join(BASE_DIR, 'new_norm')
# Output goes to skill's data folder
DATASETS_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'data'))

def get_etherscan_label(address):
    # Optionally, use Etherscan API to get contract label
    # For now, just return None (or use a mapping for known addresses)
    known_labels = {
        "0x000000000000000000000000000000000000dead": "Ethereum Dead Address (Burn Address)",
        "0x910Cbd523D972eb0a6f4cAe4618aD62622b39DbF": "Tornado Cash",
        # Add more known addresses here if desired
    }
    return known_labels.get(address.lower())

def normalize_uniswap_trm_csv(csv_path):
    seen = set()
    entries = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            address = row['address']
            category = row['category']
            risk = row['categoryRiskScoreLevelLabel']
            if not address.lower().startswith('0x'):
                continue  # skip non-Ethereum addresses
            if (category not in ['Mixer', 'Sanctions', 'Scam', 'Hacked or Stolen Funds']) or (risk not in ['High', 'Severe']):
                continue
            key = (address.lower(), category, risk)
            if key in seen:
                continue
            seen.add(key)
            label = get_etherscan_label(address) or category
            entry = {
                "address": address,
                "name": label,
                "created_at": "",  # Not available in CSV
                "creator": "",
                "reason": f"{category} ({risk})",
                "source": "Uniswap-TRM Risk List",
                "jurisdictions_blocked": [],
                "severity": "critical" if risk == "Severe" else "high",
                "known_victims": [],
                "related_hashes": [],
                "references": [],
                "tags": [category.lower(), "uniswap-trm"],
                "notes": f"category: {category}, risk: {risk}, riskType: {row.get('riskType', '')}, totalVolumeUsd: {row.get('totalVolumeUsd', '')}"
            }
            entries.append(entry)
    return entries

if __name__ == "__main__":
    if not os.path.exists(NEW_NORM_DIR):
        print(f"Directory not found: {NEW_NORM_DIR}")
        exit(1)
        
    csv_path = os.path.join(NEW_NORM_DIR, "uniswap-trm.csv")
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        exit(1)

    output_path = os.path.join(DATASETS_DIR, "normalized_uniswap_trm.json")
    
    normalized = normalize_uniswap_trm_csv(csv_path)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)
    print(f"Normalized {len(normalized)} entries to {output_path}")
