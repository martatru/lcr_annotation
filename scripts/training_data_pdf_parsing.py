#this program has to be finished! we skipped to automatizing seg etc. so it was not finished

import os
import json
import re
import fitz  # PyMuPDF

# ==========================================
# KONFIGURACJA ŚCIEŻEK
# ==========================================
PDF_FOLDER = os.path.join("training_data", "lcr_positive_papers")
OUTPUT_JSON = os.path.join("training_data", "extracted_papers_data.json")

def extract_pmcid_from_filename(filename):
    match = re.search(r'(?:PMC)?(\d{6,8})', filename, re.IGNORECASE)
    if match:
        return match.group(1)
    return "Unknown"

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def split_sections_smart(full_text):
    sections = {
        "abstract": "",
        "introduction": "",
        "results": "",
        "discussion": "",
        "conclusion": ""
    }
    
    # Szukamy nagłówków, które są na początku nowej linii. 
    # Uwzględniamy opcjonalną numerację, np. "1. Introduction", "3.1 Results"
    header_pattern = re.compile(
        r'^\s*(?:[IVX\d]+\.?\s*)?(Abstract|Introduction|Results|Discussion|Conclusion|Methods|References)\s*$', 
        re.IGNORECASE | re.MULTILINE
    )
    
    matches = list(header_pattern.finditer(full_text))
    
    if not matches:
        return sections
        
    found_sections = []
    for m in matches:
        section_name = m.group(1).lower()
        found_sections.append({
            "name": section_name,
            "start": m.start(),
            "end_of_header": m.end()
        })
        
    # Wycinanie tekstu pomiędzy prawdziwymi nagłówkami
    for i, sec in enumerate(found_sections):
        name = sec["name"]
        
        # Używamy Methods i References tylko jako punktów odcięcia, nie zapisujemy ich
        if name not in sections:
            continue 
            
        start_text = sec["end_of_header"]
        end_text = found_sections[i+1]["start"] if i + 1 < len(found_sections) else len(full_text)
        
        sections[name] += full_text[start_text:end_text].strip() + " "
        
    for k in sections:
        sections[k] = clean_text(sections[k])
        
    return sections

def main():
    if not os.path.exists(PDF_FOLDER):
        print(f"Błąd: Nie znaleziono folderu {PDF_FOLDER}")
        return

    all_papers_data = []
    
    for filename in os.listdir(PDF_FOLDER):
        if not filename.lower().endswith('.pdf'):
            continue
            
        filepath = os.path.join(PDF_FOLDER, filename)
        print(f"Working on: {filename}...")
        
        try:
            pmc_id = extract_pmcid_from_filename(filename)
            doc = fitz.open(filepath)
            
            # Wyciąganie metadanych
            title = doc.metadata.get("title", "")
            author_str = doc.metadata.get("author", "")
            authors = [a.strip() for a in re.split(r'[,;]', author_str) if a.strip()] if author_str else []
            
            # Czytanie tekstu (sort=True pomaga w czytaniu kolumn)
            full_text = ""
            for page in doc:
                full_text += page.get_text("text", sort=True) + "\n"
                
            doc.close()
            
            # Podział na sekcje
            sections = split_sections_smart(full_text)
            
            # Ratowanie tytułu - bierzemy pierwsze 150 znaków, ale przerywamy na pierwszym znaku nowej linii
            if not title.strip() or "Microsoft Word" in title:
                first_lines = full_text.strip().split('\n')
                title = clean_text(first_lines[0]) if first_lines else "Unknown"
            else:
                title = clean_text(title)
            
            paper_data = {
                "pmc_id": pmc_id,
                "title": title,
                "abstract": sections.get("abstract", ""),
                "introduction": sections.get("introduction", ""),
                "results": sections.get("results", ""),
                "discussion": sections.get("discussion", ""),
                "conclusion": sections.get("conclusion", ""),
                "authors": authors
            }
            
            all_papers_data.append(paper_data)
            
        except Exception as e:
            print(f"  [!] Błąd podczas przetwarzania {filename}: {e}")

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_papers_data, f, indent=2, ensure_ascii=False)
        
    print(f"\nZakończono! Przetworzono {len(all_papers_data)} plików.")

if __name__ == "__main__":
    main()