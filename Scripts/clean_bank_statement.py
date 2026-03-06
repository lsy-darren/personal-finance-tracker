import pypdf
import re
import json
import os
import sys
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==========================================
# 🔧 USER CONFIGURATION
# ==========================================

# 1. OUTPUT FOLDER
OUTPUT_DIR = "../Processed" 

# ==========================================

# --- HELPER: LOGGING ---
def log(message):
    print(message, file=sys.stderr)

def extract_text_from_pdf(pdf_path):
    try:
        reader = pypdf.PdfReader(pdf_path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
        return full_text
    except Exception as e:
        log(f"Error reading PDF: {e}")
        return ""

def scrub_pii(text):
    """
    Removes sensitive data using .env variables and patterns.
    """
    
    # 1. Scrub from .env (SENSITIVE_DATA)
    # This handles Names, NRIC, Accounts, Addresses all in one go.
    env_sensitive = os.getenv("SENSITIVE_DATA", "")
    if env_sensitive:
        # Handle newlines if the user used quotes for multiline values in .env
        env_sensitive = env_sensitive.replace('\n', ',')
        
        # Split by comma and strip whitespace
        secure_terms = [t.strip() for t in env_sensitive.split(',') if t.strip()]
        for term in secure_terms:
            # Create a flexible pattern:
            # "Darren Lee" becomes D[\s-]*a[\s-]*r... etc.
            # This matches "Darren Lee", "DarrenLee", "Darren - Lee"
            clean_term = term.replace(" ", "").replace("-", "")
            spaced_pattern = r"[\s-]*".join(re.escape(char) for char in clean_term)
            
            # Use a generic [REDACTED] label for simplicity, or we could try to detect types
            text = re.sub(spaced_pattern, '[REDACTED]', text, flags=re.IGNORECASE)

    # 2. Scrub NRIC (Standard S1234567Z format - Safety Net)
    text = re.sub(r'(?i)[S|T|F|G]\s*\d{7}\s*[A-Z]', '[NRIC_REDACTED]', text)
    
    # 3. Scrub Singapore Postal Codes (6 Digits - Safety Net)
    text = re.sub(r'(?i)(Singapore|S)\s*\(?\d{6}\)?', '[POSTAL_REDACTED]', text)

    # 4. Scrub Credit Card Numbers (The "Smart" Regex for remaining unmatched cards)
    text = re.sub(r'(?<!\.)\b(?:\d[\s-]*){13,19}\b', '[ACC_NUM_REDACTED]', text)
    
    # 5. Generic Name/Address Blocks (Safety Net for other names)
    text = re.sub(r'(?i)(Mr|Ms|Mrs|Dr)\.?\s+[A-Za-z]+.*?\n', '[NAME_REDACTED]\n', text)
    
    return text

def detect_metadata(text):
    """
    Scans text for Bank, Type, and specifically the STATEMENT Date.
    Returns: YYMM_Bank_DocType
    """
    text_lower = text.lower()
    
    # A. Detect Bank
    bank = "UnknownBank"
    if "uob" in text_lower: bank = "UOB"
    elif "dbs" in text_lower: bank = "DBS"
    elif "citi" in text_lower: bank = "Citi"
    elif "amex" in text_lower: bank = "Amex"
    elif "ocbc" in text_lower: bank = "OCBC"
    elif "ibkr" in text_lower: bank = "IBKR"
    elif "standard chartered" in text_lower: bank = "StanChart"
    elif "hsbc" in text_lower: bank = "HSBC"

    # B. Detect Type
    doc_type = "Statement"
    
    # 1. Strong Indicators for Bank Accounts (Withdrawals/Deposits columns)
    if "withdrawals" in text_lower and "deposits" in text_lower:
        doc_type = "Account"
    # 2. Strong Indicators for Credit Cards (Look for limits/min payments)
    elif "credit limit" in text_lower or "minimum payment" in text_lower:
        doc_type = "CreditCard"
    # 3. Fallback Keyword Matching
    elif "credit card" in text_lower:
        doc_type = "CreditCard"
    elif "savings" in text_lower or "account" in text_lower:
        doc_type = "Account"
    elif "investment" in text_lower:
        doc_type = "Investments"

    # C. Detect Date (Logic: Hunt for 'Statement Date' first)
    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"
    }
    
    date_pattern = r'\b(\d{1,2}[\s-]+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,.-]+(\d{1,2}[\s,.-]+)?(202\d)'
    
    statement_match = re.search(r'(?:statement|issue)\s+date.*?(' + date_pattern + ')', text_lower, re.DOTALL)
    
    target_match = None
    if statement_match:
        target_match = re.search(date_pattern, statement_match.group(0))
    else:
        target_match = re.search(date_pattern, text_lower)

    detected_date = datetime.now().strftime("%y%m")
    
    if target_match:
        match_str = target_match.group(0)
        mon_str = next((m for m in months if m in match_str), "01")
        month_num = months[mon_str]
        
        year_match = re.search(r'202\d', match_str)
        year = year_match.group(0)[2:] if year_match else "25"
        
        detected_date = f"{year}{month_num}"

    return f"{detected_date}_{bank}_{doc_type}"

def main():
    files_to_process = []
    is_headless = False

    # 1. SETUP OUTPUT DIRECTORY
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir_path = os.path.join(script_dir, OUTPUT_DIR)
    if not os.path.exists(output_dir_path):
        os.makedirs(output_dir_path)

    # 2. DETERMINE INPUT SOURCE
    if len(sys.argv) > 1:
        # Headless Mode
        files_to_process = [sys.argv[1]]
        is_headless = True
    else:
        # Manual Mode
        root = tk.Tk()
        root.withdraw()
        log(f"📂 Output Folder: {output_dir_path}")
        log("waiting for file selection...")
        
        selected_files = filedialog.askopenfilenames(
            title="Select Bank Statements",
            filetypes=[("PDF Files", "*.pdf")]
        )
        if not selected_files:
            log("❌ No files selected.")
            return
        files_to_process = list(selected_files)

    # 3. PROCESSING LOOP
    processed_paths = []
    
    if not is_headless:
        log(f"\nProcessing {len(files_to_process)} files...")
        log("-" * 40)

    for file_path in files_to_process:
        original_filename = os.path.basename(file_path)
        if not is_headless:
            print(f"📄 Reading: {original_filename}...", end=" ", file=sys.stderr)

        raw_text = extract_text_from_pdf(file_path)
        if not raw_text:
            log("❌ Failed to read text.")
            continue

        clean_text = scrub_pii(raw_text)
        smart_name = detect_metadata(clean_text)
        
        file_data = {
            "original_filename": original_filename,
            "smart_name": smart_name,
            "scrubbed_content": clean_text
        }

        output_filename = f"Processed_{smart_name}.json"
        output_path = os.path.join(output_dir_path, output_filename)
        
        with open(output_path, 'w') as f:
            json.dump([file_data], f, indent=4)
            
        processed_paths.append(output_path)
        
        if not is_headless:
            print(f"✅ Saved as: {output_filename}", file=sys.stderr)

    # 4. FINAL REPORTING
    if is_headless:
        if processed_paths:
            print(json.dumps({"json_file_path": processed_paths[0]}))
    else:
        log("-" * 40)
        log("🎉 All done.")

if __name__ == "__main__":
    main()