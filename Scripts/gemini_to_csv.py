import os
import json
import sys
import tkinter as tk
from tkinter import filedialog
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()

# --- HELPER: LOGGING ---
def log(message):
    print(message, file=sys.stderr)

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    log("❌ Error: GEMINI_API_KEY not found.")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)

def get_gemini_response(clean_text, metadata):
    """
    Sends text + metadata to Gemini with strict financial rules.
    """
    
    # Metadata format is now: YYMM_Bank_DocType (e.g., 2511_Citi_CreditCard)
    parts = metadata.split('_')
    
    # CHANGED: Index 1 is now Bank, Index 2 is DocType
    bank_name = parts[1] if len(parts) > 1 else "Unknown Bank"
    doc_type = parts[2] if len(parts) > 2 else "Statement"
    
    prompt = f"""
    You are a financial data extraction engine.
    
    CONTEXT:
    - Document Type: {doc_type}
    - Bank Name: {bank_name}
    
    INSTRUCTIONS:
    1. Extract every VALID transaction.
    2. Output strict CSV format.
    3. NO MARKDOWN: Do not use ```csv or ``` tags. Just raw text.
    4. AMOUNT FORMAT: Plain number only. NO commas. NO currency symbols. (e.g. 1453.50, NOT 1,453.50).
    
    OUTPUT COLUMNS:
    Date, Description, Type, Category, Amount, Account, Original Description

    CRITICAL AMOUNT RULE (SGD ONLY):
    - This statement is billed in SGD.
    - ALWAYS extract the final converted SGD amount.
    - IGNORE original foreign currency amounts (e.g., if text says "MYR 54.19" and "SGD 17.46", extract 17.46).

    DETAILED COLUMN RULES:
    - Date: Format as YYYY-MM-DD.
    - Description: Clean, short merchant name (e.g., "Grab", "Netflix").
    - Type: "Expense", "Income", or "Transfer". Follow STRICT DEFINITIONS below.
    - Category: Choose from [Transport, Food, Groceries, Shopping, Subscriptions, Bills, Insurance, Travel, Transfer, Income, General]. Choose 'Transfer' ONLY if "Type" is ALSO Transfer. If Type is Expense/Income, choose a non-Transfer category. All PayLah transactions are Category: General. If Type is Income, Category must be Income only.
    - Amount: Negative for expenses (-15.50), Positive for income.
    - Original Description: The exact raw line from the text for verification. IMPORTANT: Remove all commas from this field to prevent breaking the CSV format.
    
    STRICT DEFINITIONS for "Type" column (Follow these exactly):
    1. **EXPENSE** (The default for almost everything)
       - Spending: Negative Amount (e.g. -15.90)
       - Refunds/Reversals: POSITIVE Amount (e.g. 15.90). 
       - Cashback: POSITIVE Amount. Tag as Expense.
       - Paylah or Paynow: Any amount sent from an account to Paylah or Paynow top up can be considered an Expense.
       
    2. **TRANSFER**
       - Payments TO the credit card (e.g. "MoneySend", "Payment Received", "Giro Deduction", "Bill Payment mBK", "PAYMT THRU E-BANK/HOMEB/CYBERB", "AUTO-PYT").
       - Payments TO IBKR
       
    3. **INCOME**
       - ONLY external earnings (Salary, Dividends, Bank Interest).
       - Do NOT use this for refunds.
        
    BANK STATEMENT TEXT:
    {clean_text}
    """

    response = client.models.generate_content(
        model='gemini-3-flash-preview',
        contents=prompt
    )
    
    return response.text.replace("```csv", "").replace("```", "").strip()

def main():
    file_path = None
    is_headless = False

    # 1. MODE DETECTION
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        is_headless = True
    else:
        root = tk.Tk()
        root.withdraw()
        log("Select a Processed JSON file...")
        file_path = filedialog.askopenfilename(title="Select JSON", filetypes=[("JSON Files", "*.json")])

    if not file_path:
        log("❌ No file selected.")
        return

    # 2. OUTPUT FOLDER SETUP
    # Go up one level from Scripts to find/create "Processed CSVs"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_folder = os.path.join(script_dir, "../Processed CSVs")
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    base_filename = os.path.basename(file_path)
    filename_no_ext = os.path.splitext(base_filename)[0]
    output_filename = os.path.join(output_folder, f"CSV_{filename_no_ext}.csv")

    log(f"Reading {base_filename}...")
    with open(file_path, 'r') as f:
        data = json.load(f)
        scrubbed_text = data[0]['scrubbed_content']
        smart_name = data[0].get('smart_name', 'Unknown')

    log(f"🤖 Sending to Gemini... (Context: {smart_name})")
    
    try:
        csv_output = get_gemini_response(scrubbed_text, smart_name)
        
        with open(output_filename, "w", newline="") as f:
            f.write(csv_output)
            
        # 3. REPORTING
        if is_headless:
            # For n8n: Print ONLY the JSON result
            print(json.dumps({"csv_file_path": output_filename}))
        else:
            # For Humans: Friendly Message
            log("-" * 40)
            log(f"🎉 Success! Saved to: {output_filename}")
            
    except Exception as e:
        log(f"❌ Error calling Gemini: {e}")
        # Exit with error code so n8n knows it failed
        sys.exit(1)

if __name__ == "__main__":
    main()