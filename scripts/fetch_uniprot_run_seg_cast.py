#this code is supposed to fetch uniprot id from a paper, take priorly extracted LCR ranges, run SEG and CAST
#this code probably won't work at the first try, bcs i didnt have the inpot to test it yet
import re
import os
import requests
import subprocess
import tempfile

# ==========================================
# PATH CONFIGURATION
# ==========================================
PAPERS_JSON = os.path.join("training_data", "extracted_papers_data.json")
LCR_JSON = os.path.join("training_data", "lcr_locations_found.json")

# Official Regex for UniProt Accession Numbers (e.g., P12345, A0A022Y195)
UNIPROT_REGEX = re.compile(
    r"\b([O,P,Q][0-9][A-Z0-9]{3}[0-9]|[A-N,R-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})\b"
)

def extract_uniprot_ids(text):
    """Finds unique UniProt IDs in the provided text."""
    if not text:
        return []
    matches = UNIPROT_REGEX.findall(text)
    # Extract the first element from the match group and remove duplicates
    return list(set(match[0] for match in matches))

def download_fasta(uniprot_id):
    """Downloads the FASTA sequence from UniProt API."""
    url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.fasta"
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    return None

def parse_tool_output(output):
    """
    Universal parser looking for coordinate ranges like '10 - 50' or '10..50' 
    in the standard output.
    NOTE: You might need to adjust the regex depending on how your specific 
    local builds of SEG/CAST format their terminal output.
    """
    found_ranges = []
    # Looks for patterns like: 123-456, 123 - 456, 123..456
    range_pattern = re.compile(r"\b(\d+)\s*(?:-|\.\.)\s*(\d+)\b")
    
    for line in output.splitlines():
        matches = range_pattern.findall(line)
        for start, end in matches:
            found_ranges.append({"start": int(start), "end": int(end)})
            
    return found_ranges

def run_local_tool(tool_name, fasta_path):
    """Runs the specified CLI tool and parses its output for LCR ranges."""
    try:
        # Standard execution assumption: `seg file.fasta` or `cast file.fasta`
        result = subprocess.run(
            [tool_name, fasta_path], 
            capture_output=True, 
            text=True, 
            check=False
        )
        # Combine stdout and stderr (sometimes results are piped to stderr)
        full_output = result.stdout + "\n" + result.stderr
        return parse_tool_output(full_output)
    except FileNotFoundError:
        print(f"ERROR: The tool '{tool_name}' was not found in your system's PATH.")
        return []

def check_overlap(declared_lcrs, predicted_lcrs):
    """
    Checks if ANY of the declared LCRs overlap with ANY of the predicted LCRs.
    Two ranges (A, B) and (C, D) overlap if max(A, C) <= min(B, D).
    """
    for decl in declared_lcrs:
        d_start, d_end = decl["start"], decl["end"]
        for pred in predicted_lcrs:
            p_start, p_end = pred["start"], pred["end"]
            
            # Condition for range overlap
            if max(d_start, p_start) <= min(d_end, p_end):
                return True
    return False

def main():
    if not os.path.exists(PAPERS_JSON) or not os.path.exists(LCR_JSON):
        print("Missing input files. Please ensure the previous extraction script ran successfully.")
        return

    # Load previously declared LCR ranges
    with open(LCR_JSON, "r", encoding="utf-8") as f:
        lcr_data = json.load(f)
        
    # Create a dictionary mapping pmc_id -> declared ranges for quick lookups
    declared_dict = {item["pmc_id"]: item["lcr_mentions"] for item in lcr_data}

    # Load original paper texts
    with open(PAPERS_JSON, "r", encoding="utf-8") as f:
        papers = json.load(f)

    for paper in papers:
        pmc_id = paper.get("pmc_id", "Unknown")
        
        # We only care about papers where LCRs were actually found in the previous step
        if pmc_id not in declared_dict:
            continue
            
        declared_lcrs = declared_dict[pmc_id]
        
        # Merge all sections to search for UniProt IDs
        full_text = " ".join([
            paper.get("abstract", ""),
            paper.get("introduction", ""),
            paper.get("results", ""),
            paper.get("discussion", ""),
            paper.get("conclusion", "")
        ])

        # Extract UniProt IDs
        uniprot_ids = extract_uniprot_ids(full_text)
        
        if not uniprot_ids:
            continue
            
        print(f"\n[{pmc_id}] Found UniProt IDs: {uniprot_ids}")
        
        for uid in uniprot_ids:
            print(f"  Downloading FASTA for {uid}...")
            fasta_text = download_fasta(uid)
            
            if not fasta_text:
                print(f"  -> Failed to download sequence for {uid}.")
                continue

            # Save the FASTA string to a temporary file to pass to CLI tools
            with tempfile.NamedTemporaryFile(mode='w', suffix=".fasta", delete=False) as tmp:
                tmp.write(fasta_text)
                tmp_path = tmp.name

            # STEP 1: RUN SEG
            print(f"  -> Running SEG...")
            seg_lcrs = run_local_tool("seg", tmp_path)
            
            if seg_lcrs and check_overlap(declared_lcrs, seg_lcrs):
                print(f"  [SUCCESS] SEG confirmed overlap with declared LCRs for protein {uid}!")
                os.remove(tmp_path)
                continue # Move on to the next protein/paper
            
            # STEP 2: RUN CAST (Fallback if SEG found no overlap)
            print(f"  -> SEG found no overlap. Running CAST...")
            cast_lcrs = run_local_tool("cast", tmp_path)
            
            if cast_lcrs and check_overlap(declared_lcrs, cast_lcrs):
                print(f"  [SUCCESS] CAST confirmed overlap with declared LCRs for protein {uid}!")
            else:
                print(f"  [NO OVERLAP] Neither tool (SEG/CAST) confirmed the declared LCRs for {uid}.")

            # Clean up temporary file
            os.remove(tmp_path)

if __name__ == "__main__":
    main()