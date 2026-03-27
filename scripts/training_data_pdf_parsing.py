#this script works poorly, i wanto to try using the "unstructured" python library to read those papers,
#or maybe try GROBID model

import fitz  # PyMuPDF
import json
import re
import os
import requests

# ==========================================
# CONFIGURATION
# ==========================================
PDF_DIRECTORY = "/home/marta/Pulpit/lcr_annotation/training_data/lcr_positive_papers"
OUTPUT_JSON = "/home/marta/Pulpit/lcr_annotation/training_data/extracted_papers_data_fixed.json"

def get_pmcid_from_title(title):
    """Fetches PMC ID from Europe PMC API based on the article title."""
    if not title or len(title) < 15:
        return "Unknown"
    
    clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', title[:100])
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {"query": f'TITLE:"{clean_title}"', "format": "json", "resultType": "lite"}
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("hitCount", 0) > 0:
                pmcid = data["resultList"]["result"][0].get("pmcid")
                if pmcid:
                    return pmcid
    except Exception:
        pass
    return "Unknown"

def clean_text(text):
    """Cleans the text from unnecessary newlines, broken words, and journal artifacts."""
    if not text:
        return ""
        
    artifacts = [
        r'(?i)\bARTICLE IN PRESS\b',
        r'(?i)\bNature Communications\b',
        r'(?i)https?://doi\.org/\S+',
        r'(?i)rights reserved\.',
        r'(?i)\bPRESS\b'
    ]
    for artifact in artifacts:
        text = re.sub(artifact, '', text)

    # Fix hyphenated line breaks (e.g. low-\ncomplexity -> low-complexity)
    text = re.sub(r'([a-z])-[\n\r]+\s*([a-z])', r'\1\2', text, flags=re.IGNORECASE)
    # Normalize spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def parse_single_pdf(pdf_path):
    print(f"Processing: {os.path.basename(pdf_path)} ...")
    
    article_data = {
        "pmc_id": "Unknown",
        "title": "",
        "abstract": "",
        "introduction": "",
        "results": "",
        "discussion": "",
        "conclusion": "",
        "authors": []
    }
    
    # Try to extract PMC_ID from filename
    filename_match = re.search(r'(PMC\d+)', os.path.basename(pdf_path), re.IGNORECASE)
    if filename_match:
        article_data["pmc_id"] = filename_match.group(1).upper()

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"  -> Error reading PDF: {e}")
        return article_data

    # State Machine variables
    current_section = "title"
    
    # Regex to identify headers (handles "1. Introduction", "Results:", "III. Discussion")
    header_regex = re.compile(
        r'^(?:\d+\.?\s*|[IVX]+\.?\s*)?(Abstract|Summary|Introduction|Background|Results|Discussion|Conclusions?|Methods|Materials and Methods|Experimental Procedures|References?)(?:\s*:|\.)?\s*(.*)', 
        re.IGNORECASE | re.DOTALL
    )

    for page in doc:
        # Define crop margins (ignore top 7% and bottom 7% for headers/footers/DOIs)
        rect = page.rect
        margin_y = rect.height * 0.07  
        
        # Extract blocks of text (preserves logical reading order)
        blocks = page.get_text("blocks")
        
        for b in blocks:
            # PyMuPDF block format: (x0, y0, x1, y1, "text", block_no, block_type)
            if b[6] != 0: # 0 means text block
                continue
                
            # Skip blocks that fall inside our header/footer crop margins
            if b[1] < rect.y0 + margin_y or b[3] > rect.y1 - margin_y:
                continue

            text = b[4].strip()
            if not text:
                continue

            # Try to match PMC ID in text if we still don't have it
            if article_data["pmc_id"] == "Unknown":
                pmc_match = re.search(r'\b(PMC\d{6,8})\b', text, re.IGNORECASE)
                if pmc_match:
                    article_data["pmc_id"] = pmc_match.group(1).upper()

            # Check if block is a section header
            match = header_regex.match(text)
            
            # To prevent false positives (like a sentence starting with "Results of the..."),
            # we only treat it as a header if the block is short OR it has a distinct separator like "1. Results."
            is_header = False
            if match:
                keyword = match.group(1).lower()
                remainder = match.group(2)
                
                if len(text) < 100: 
                    is_header = True
                elif bool(re.match(r'^(?:\d+\.?|[IVX]+\.?|.*:)', text)):
                    is_header = True

                if is_header:
                    # Route to the correct bucket
                    if "abstract" in keyword or "summary" in keyword:
                        current_section = "abstract"
                    elif "intro" in keyword or "background" in keyword:
                        current_section = "introduction"
                    elif "result" in keyword:
                        current_section = "results"
                    elif "discuss" in keyword:
                        current_section = "discussion"
                    elif "conclu" in keyword:
                        current_section = "conclusion"
                    elif "method" in keyword or "experi" in keyword:
                        current_section = "methods" # Temporarily routes out of main sections
                    elif "refer" in keyword or "bibliog" in keyword:
                        current_section = "references" # Routes out of main sections
                        
                    # If it was an inline header (e.g., "1. Results. We found that..."), keep the rest of the text
                    if remainder.strip():
                        text = remainder.strip()
                    else:
                        continue # Move to the next block

            # Auto-switch title to abstract if title gets too long (missed the abstract header)
            if current_section == "title" and len(article_data["title"]) > 400:
                current_section = "abstract"

            # Append text to the active bucket
            if current_section in article_data:
                article_data[current_section] += text + "\n"

    # Clean the extracted text
    for key in article_data.keys():
        if key not in ["pmc_id", "authors"]:
            article_data[key] = clean_text(article_data[key])

    # Fallback to Europe PMC API if PMC ID is still missing
    if article_data["pmc_id"] == "Unknown" and article_data["title"]:
        article_data["pmc_id"] = get_pmcid_from_title(article_data["title"])

    return article_data

def main():
    if not os.path.exists(PDF_DIRECTORY):
        print(f"Directory '{PDF_DIRECTORY}' does not exist. Please check the path.")
        return

    extracted_data = []
    
    for filename in os.listdir(PDF_DIRECTORY):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(PDF_DIRECTORY, filename)
            article_json = parse_single_pdf(pdf_path)
            if article_json:
                # Remove temporary routing keys so output matches your exact format
                article_json.pop("methods", None)
                article_json.pop("references", None)
                extracted_data.append(article_json)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=2)
        
    print(f"\nSuccess! Processed {len(extracted_data)} articles. Saved to {OUTPUT_JSON}.")

if __name__ == "__main__":
    main()