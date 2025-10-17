#!/usr/bin/env python3
"""
Split the large CMS DAC file into 3 parquet chunks for git compatibility.

The original CSV file (672MB) is too large for git. This script converts it to
3 parquet files (~70MB each) that can be committed to git.

Parquet advantages:
- 70% smaller than CSV
- Faster to load (binary format)
- Preserves data types
- Compressed (snappy)
"""

import pandas as pd
import os
import sys

def split_cms_data():
    """Split DAC_NationalDownloadableFile.csv into 3 parquet chunks"""

    input_file = 'DAC_NationalDownloadableFile.csv'

    if not os.path.exists(input_file):
        print(f"❌ Error: {input_file} not found!")
        print("\nPlease download it first:")
        print('curl -o DAC_NationalDownloadableFile.csv "https://data.cms.gov/provider-data/sites/default/files/resources/52c3f098d7e56028a298fd297cb0b38d_1757685921/DAC_NationalDownloadableFile.csv"')
        sys.exit(1)

    print(f"📂 Reading {input_file}...")

    # Read the full file
    df = pd.read_csv(input_file, low_memory=False)

    # Strip column names (some have tabs)
    df.columns = df.columns.str.strip()

    print(f"✓ Total rows: {len(df):,}")
    print(f"✓ Total size: {os.path.getsize(input_file) / (1024*1024):.1f} MB (CSV)")

    # Calculate chunk size
    num_chunks = 3
    chunk_size = len(df) // num_chunks

    print(f"\n📦 Converting to {num_chunks} Parquet chunks (~{chunk_size:,} rows each)...\n")

    # Split into chunks
    total_size = 0
    for i in range(num_chunks):
        start_idx = i * chunk_size
        # Last chunk gets the remainder
        if i == num_chunks - 1:
            end_idx = len(df)
        else:
            end_idx = (i + 1) * chunk_size

        chunk = df.iloc[start_idx:end_idx]
        filename = f'DAC_parquet_{i+1}.parquet'

        chunk.to_parquet(filename, compression='snappy', index=False)
        size_mb = os.path.getsize(filename) / (1024*1024)
        total_size += size_mb

        print(f"  ✓ {filename}: {len(chunk):,} rows, {size_mb:.1f} MB")

    csv_size = os.path.getsize(input_file) / (1024*1024)
    compression_pct = (1 - total_size/csv_size) * 100

    print(f"\n✅ Done! Created {num_chunks} parquet files.")
    print(f"   CSV size: {csv_size:.1f} MB")
    print(f"   Parquet total: {total_size:.1f} MB")
    print(f"   Compression: {compression_pct:.1f}% smaller")
    print(f"\n💡 You can now delete the original {input_file} to save space.")
    print("   The parquet files will be used by the application.")

if __name__ == "__main__":
    split_cms_data()
