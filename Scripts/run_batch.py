import os
import sys
import glob
import json
import shutil
import subprocess
import requests
from dotenv import load_dotenv

# ================= CONFIGURATION =================
INPUT_DIR = "../Input"
ARCHIVE_DIR = "../Archive"
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/bank-statement"

SCRUBBER_SCRIPT = "clean_bank_statement.py"
BRIDGE_SCRIPT = "gemini_to_csv.py"
# =================================================

def log(msg):
    print(f"[Batch] {msg}")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, INPUT_DIR)
    archive_path = os.path.join(script_dir, ARCHIVE_DIR)

    if not os.path.exists(archive_path):
        os.makedirs(archive_path)

    pdf_files = glob.glob(os.path.join(input_path, "*.pdf"))
    
    if not pdf_files:
        log("⚠️  No PDFs found in Input folder.")
        return

    log(f"🚀 Found {len(pdf_files)} statements. Starting batch process...")
    print("-" * 50)

    for pdf_file in pdf_files:
        filename = os.path.basename(pdf_file)
        log(f"📄 Processing: {filename}...")

        try:
            # 1. RUN SCRUBBER
            scrubber_cmd = os.path.join(script_dir, SCRUBBER_SCRIPT)
            res1 = subprocess.run([sys.executable, scrubber_cmd, pdf_file], capture_output=True, text=True)
            
            if res1.returncode != 0:
                log(f"❌ Scrubber Failed: {res1.stderr}")
                continue
                
            try:
                scrub_data = json.loads(res1.stdout.strip())
                json_path = scrub_data['json_file_path']
            except:
                log(f"❌ Could not parse Scrubber JSON: {res1.stdout}")
                continue

            # 2. RUN BRIDGE
            bridge_cmd = os.path.join(script_dir, BRIDGE_SCRIPT)
            res2 = subprocess.run([sys.executable, bridge_cmd, json_path], capture_output=True, text=True)
            
            if res2.returncode != 0:
                log(f"❌ Bridge Failed: {res2.stderr}")
                continue

            try:
                bridge_data = json.loads(res2.stdout.strip())
                csv_path = bridge_data['csv_file_path']
            except:
                log(f"❌ Could not parse Bridge JSON: {res2.stdout}")
                continue

            # 3. SEND TO N8N
            with open(csv_path, 'r') as f:
                csv_content = f.read()
            
            payload = {"filename": os.path.basename(csv_path), "csv_data": csv_content}
            
            try:
                n8n_res = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=10)
                if n8n_res.status_code == 200:
                    log("   ✅ Sent to Google Sheets")
                else:
                    log(f"   ⚠️ n8n Error: {n8n_res.status_code} - {n8n_res.text}")
            except Exception as e:
                log(f"   ⚠️ n8n Connection Failed: {e}")

            # 4. ARCHIVE THE PDF
            destination = os.path.join(archive_path, filename)
            shutil.move(pdf_file, destination)
            log(f"   📦 Archived to {ARCHIVE_DIR}")

        except Exception as e:
            log(f"❌ Critical Error on {filename}: {e}")
        
        print("-" * 50)

    log("🎉 Batch Complete.")

if __name__ == "__main__":
    main()