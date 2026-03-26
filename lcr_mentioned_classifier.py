import json
import re

def classify_lcr_papers(input_filepath, mentioned_filepath, not_mentioned_filepath):

    lcr_pattern = re.compile(r'\b(LCRs?|low[- ]complexity)\b', re.IGNORECASE)

    lcr_mentioned_ids = []
    lcr_not_mentioned_ids = []

    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            papers = json.load(f)
    except FileNotFoundError:
        print(f"Błąd: Nie znaleziono pliku {input_filepath}.")
        return

    for paper in papers:
        pmc_id = paper.get("pmc_id")
        if not pmc_id:
            continue

        full_text_parts = [
            paper.get("title", ""),
            paper.get("abstract", ""),
            paper.get("introduction", ""),
            paper.get("results", ""),
            paper.get("discussion", ""),
            paper.get("conclusion", "")
        ]
        full_text = " ".join(filter(None, full_text_parts))

        if lcr_pattern.search(full_text):
            lcr_mentioned_ids.append(pmc_id)
        else:
            lcr_not_mentioned_ids.append(pmc_id)

    # Zapis wyników do plików JSON
    with open(mentioned_filepath, 'w', encoding='utf-8') as f:
        json.dump(lcr_mentioned_ids, f, indent=2)

    with open(not_mentioned_filepath, 'w', encoding='utf-8') as f:
        json.dump(lcr_not_mentioned_ids, f, indent=2)

    print("Classification has ended succesfully!")
    print(f" {len(lcr_mentioned_ids)} publications mentioning LCR directly were found.")
    print(f" {len(lcr_not_mentioned_ids)} publications not mentioning LCR were found.")

if __name__ == "__main__":
    INPUT_FILE = "pmc_lcr_full.json"
    OUT_MENTIONED = "lcr_mentioned_ids.json"
    OUT_NOT_MENTIONED = "lcr_not_mentioned_ids.json"

    classify_lcr_papers(INPUT_FILE, OUT_MENTIONED, OUT_NOT_MENTIONED)