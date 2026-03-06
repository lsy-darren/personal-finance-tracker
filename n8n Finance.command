#!/bin/bash

# 1. Navigate to the folder where this file is saved
cd "$(dirname "$0")"

# 2. Clear screen for neatness
clear

echo "=========================================="
echo "   💰 Finance Batch Processor"
echo "=========================================="
echo "Scanning 'Input' folder for statements..."
echo ""

# 3. Run the Python Script
python3.12 Scripts/run_batch.py

echo ""
echo "=========================================="
# 4. Pause so you can read the results
read -p "Press Enter to close..."