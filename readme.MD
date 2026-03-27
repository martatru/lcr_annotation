# LCR Annotation and Validation Pipeline

This pipeline is designed to fetch, parse, and validate research papers concerning Low Complexity Regions (LCRs) to automate LCR annotation.

---

## Requirements

### Python Libraries
The scripts require the following Python packages:
* **PyMuPDF (fitz)**: Used for high-fidelity text extraction from PDF files.[cite: 1]
* **httpx**: Used for asynchronous HTTP requests to the NCBI and PMC APIs.[cite: 3]
* **lxml**: Required for parsing XML data from PubMed Central.[cite: 3]
* **requests**: Used for synchronous API calls to UniProt and Europe PMC.[cite: 1, 5]
* **asyncio**: Manages asynchronous fetching processes.[cite: 3]

### System Tools
* **SEG**: A local command-line tool for identifying low-complexity segments in protein sequences.[cite: 5]
* **CAST**: A local command-line tool for detecting compositionally biased regions in sequences.[cite: 5]

---

## Script Descriptions

### pmc_regex_miner.py
Fetches LCR-related papers from the PubMed Central API using search terms like "tandem repeat" and "intrinsically disordered," filtering results with a comprehensive regex list.[cite: 3]

### training_data_pdf_parsing.py
Extracts structured text from local PDF files using a state-machine approach to identify section headers and clean out journal artifacts (e.g., "Article in Press") but has to be updated, doesnt really work now :(.[cite: 1]

### lcr_classifier.py
Performs binary classification on gathered papers to identify which ones explicitly mention "LCR" or "low-complexity" in the text versus those that do not.[cite: 4]

### lcr_location_finder.py
Uses multiple regex patterns to extract coordinate ranges from paper text, including standard mentions like "residues 331-369" and protein-specific notations.[cite: 2]

### fetch_uniprot_check_seq.py
Identifies UniProt Accession Numbers in the paper text, downloads the corresponding FASTA sequence, and cross-references author-declared LCRs with predictions from SEG and CAST.[cite: 5]

---

## LABBOOK
26/03/2026

We created a way to fetch relevant papers via PubMed Central API, and later sort them by regex as mentioning LCR, or not mentioning LCR[cite: 6]

We research models and decided to use BioClinicalModernBERT, as well as later add BioLINKBERT[cite: 6]

I downloaded around 50 papers from the publikacje excel and started parsing through them with training_data_pdf_parsing.py, but decided to skipt to automatizing fetch_uniprot_check_seq.py[cite: 6]

--------------------------------------------------------------------------------------------------------------------------------------
27/03/2026

I started working on the fetch_uniprot_check_seq.py[cite: 6]

I came back to fixing the pdf positive articles parser[cite: 6]

We decided that we need to broaden our positive set, because it is biased with Rna-binding papers. Also, we need to create a negative set of papers without a function annotation[cite: 6]