#!/bin/bash
# Streamlit Cloud startup script
# This runs automatically before the app starts

echo "🔧 Checking for preprocessed data..."

if [ ! -f "data/preprocessed_dashboard_data.parquet" ]; then
    echo "📊 Preprocessed data not found. Running preprocessing..."
    python scripts/01_data_preparation/preprocess_for_dashboard.py

    if [ $? -eq 0 ]; then
        echo "✅ Preprocessing complete!"
    else
        echo "❌ Preprocessing failed!"
        exit 1
    fi
else
    echo "✅ Preprocessed data already exists. Skipping preprocessing."
fi
