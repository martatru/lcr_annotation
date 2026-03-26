#later we want to add a bioclinical modernBERT model here to look if there is an annotation present,
#also, i havent been able to test if this script works yet because we didnt have the model at the moment

import json
import re
import os

# ==========================================
# PATH CONFIGURATION
# ==========================================
INPUT_JSON = os.path.join("training_data", "extracted_papers_data.json")
OUTPUT_JSON = os.path.join("training_data", "lcr_locations_found.json")

# ==========================================
# REGEX TOOLKIT FOR LCR LOCATIONS
# ==========================================
# 1. Standard mentions (including typos like "reside")
PATTERN_STANDARD = re.compile(
    r"(?i)(?:residues?|reside|amino acids?|a\.a\.|aa)\s*(?:~|approx\.\s*)?(\d+)\s*(?:-|to|and)\s*(\d+)"
)

# 2. Protein name with parentheses e.g., Ccr4(1-229)
PATTERN_PARENS = re.compile(
    r"(?:[A-Za-z0-9_-]+)\s*\((\d+)\s*-\s*(\d+)\)"
)

# 3. Direct attachments e.g., ZLD1117-1487
PATTERN_DIRECT = re.compile(
    r"[A-Za-z]+(?:_|-)?(\d{1,4})\s*-\s*(\d{1,4})\b"
)

# 4. Prefix ranges e.g., 331-369-residue or 76-115 region
PATTERN_PREFIX = re.compile(
    r"\b(\d+)\s*-\s*(\d+)\s*(?:-residue|\s+region)\b"
)

# 5. Amino acid codes e.g., G263-Y319 or Ser219 to Ser335
PATTERN_AMINO_ACIDS = re.compile(
    r"\b[A-Z][a-z]{0,2}(\d+)\s*(?:-|to)\s*[A-Z][a-z]{0,2}(\d+)\b"
)

# 6. Deletion shorthand e.g., 316del346
PATTERN_DELETION = re.compile(
    r"\b(\d+)del(\d+)\b"
)

ALL_PATTERNS = [
    PATTERN_STANDARD,
    PATTERN_PARENS,
    PATTERN_DIRECT,
    PATTERN_PREFIX,
    PATTERN_AMINO_ACIDS,
    PATTERN_DELETION
]

def find_and_filter_locations(text):
    """
    Extracts coordinate ranges using multiple regex patterns,
    removes duplicates, and filters out illogical ranges.
    """
    if not text:
        return []

    raw_locations = []
    
    # Gather all matches from all patterns
    for pattern in ALL_PATTERNS:
        matches = pattern.findall(text)
        for start, end in matches:
            start_idx, end_idx = int(start), int(end)
            
            # Sanity check: valid protein ranges (start < end, and reasonably sized)
            if start_idx < end_idx and end_idx < 10000:
                raw_locations.append((start_idx, end_idx))

    # Deduplicate exact matches using a set
    unique_locations = list(set(raw_locations))
    
    # Sort logically by start position, then by end position for clean output
    unique_locations.sort(key=lambda x: (x[0], x[1]))

    # Convert back to a list of dictionaries for the final JSON structure
    final_locations = [{"start": loc[0], "end": loc[1]} for loc in unique_locations]

    return final_locations

def main():
    if not os.path.exists(INPUT_JSON):
        print(f"Error: Could not find {INPUT_JSON}. Please ensure the PDF parsing script has run.")
        return

    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        papers = json.load(f)

    results = []
    print(f"Scanning {len(papers)} papers using the advanced regex toolkit...")

    for paper in papers:
        pmc_id = paper.get("pmc_id", "Unknown")
        title = paper.get("title", "Unknown")
        
        # Combine all available text sections
        full_text = " ".join([
            paper.get("abstract", ""),
            paper.get("introduction", ""),
            paper.get("results", ""),
            paper.get("discussion", ""),
            paper.get("conclusion", "")
        ])

        locations = find_and_filter_locations(full_text)

        if locations:
            results.append({
                "pmc_id": pmc_id,
                "title": title,
                "lcr_mentions": locations
            })

    # Save to output file
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Extraction complete! Found coordinates in {len(results)} papers.")
    print(f"Data successfully saved to: {OUTPUT_JSON}")

if __name__ == "__main__":
    main()

#example output
"""
[
  {
    "pmc_id": "11178883",
    "title": "Paper Title...",
    "lcr_mentions": [
      {"start": 331, "end": 369},
      {"start": 267, "end": 414}
    ]
  }
]
"""