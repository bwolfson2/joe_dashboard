"""
Preprocessing script for dashboard - Run this ONCE to prepare optimized data.
This moves all expensive CPU operations out of the dashboard.
"""
import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa
from pathlib import Path

def clean_phone(phone):
    """Clean phone numbers"""
    if pd.isna(phone):
        return ""
    phone_str = str(int(phone)) if isinstance(phone, float) else str(phone)
    phone_clean = ''.join(filter(str.isdigit, phone_str))
    return phone_clean if len(phone_clean) == 10 else ""

def preprocess_data():
    """Load, clean, and save preprocessed data"""
    print("Loading parquet files...")
    parquet_files = [f"DAC_parquet_{i}.parquet" for i in range(1, 4)]

    dfs = []
    for parquet_file in parquet_files:
        try:
            chunk_df = pd.read_parquet(parquet_file)
            dfs.append(chunk_df)
            print(f"Loaded {parquet_file}: {len(chunk_df):,} rows")
        except FileNotFoundError:
            print(f"Missing: {parquet_file}")

    if not dfs:
        print("ERROR: No data files found!")
        return

    print("\nCombining chunks...")
    df = pd.concat(dfs, ignore_index=True)
    print(f"Total rows: {len(df):,}")

    print("\nCleaning data...")
    # Clean numeric fields
    df["num_org_mem"] = pd.to_numeric(df["num_org_mem"], errors="coerce").fillna(0).astype(int)

    # Clean phone numbers
    print("  - Cleaning phone numbers...")
    df["phone_clean"] = df["Telephone Number"].apply(clean_phone)
    df["has_phone"] = df["phone_clean"].str.len() == 10

    # Email placeholder
    df["email"] = ""
    df["has_email"] = False

    # Provider full name
    print("  - Creating provider names...")
    df["provider_full_name"] = (
        df["Provider First Name"].fillna("") + " " + df["Provider Last Name"].fillna("")
    ).str.strip()

    # Full address
    print("  - Building addresses...")
    df["full_address"] = (
        df["adr_ln_1"].astype(str).replace("nan", "")
        + ", " + df["adr_ln_2"].astype(str).replace("nan", "")
        + ", " + df["City/Town"].astype(str).replace("nan", "")
        + ", " + df["State"].astype(str).replace("nan", "")
        + " " + df["ZIP Code"].astype(str).str.replace(".0", "").replace("nan", "")
    ).str.replace(", , ", ", ").str.replace(", ,", ",").str.strip(", ")

    # Clean location fields
    print("  - Cleaning locations...")
    df["state_clean"] = df["State"].astype(str).replace("nan", "Unknown")
    df["city_clean"] = df["City/Town"].astype(str).replace("nan", "Unknown")

    # Clean facility names
    df["Facility Name"] = df["Facility Name"].astype(str).replace("nan", "Unknown Organization")

    # Clean specialties
    print("  - Cleaning specialties...")
    df["pri_spec"] = df["pri_spec"].astype(str).replace("nan", "Unknown")
    df["sec_spec_all"] = df["sec_spec_all"].astype(str).replace("nan", "")

    # Credentials and education
    df["Cred"] = df["Cred"].astype(str).str.strip().replace("nan", "")
    df["Med_sch"] = df["Med_sch"].astype(str).replace("nan", "Unknown")
    df["Grd_yr"] = pd.to_numeric(df["Grd_yr"], errors="coerce")

    # Organization size category
    print("  - Categorizing organization sizes...")
    df["org_size_category"] = pd.cut(
        df["num_org_mem"],
        bins=[-1, 0, 10, 50, 100, 300, 1000, float("inf")],
        labels=[
            "Unknown",
            "Small Practice (1-10 members)",
            "Medium (11-50 members)",
            "Large (51-100 members)",
            "Very Large (101-300 members)",
            "Enterprise (301-1000 members)",
            "Health System (1000+ members)",
        ],
    )

    # Lead scoring
    print("  - Calculating lead scores...")
    df["lead_score"] = 0
    df.loc[df["num_org_mem"] >= 1000, "lead_score"] += 10
    df.loc[(df["num_org_mem"] >= 300) & (df["num_org_mem"] < 1000), "lead_score"] += 8
    df.loc[(df["num_org_mem"] >= 100) & (df["num_org_mem"] < 300), "lead_score"] += 6
    df.loc[(df["num_org_mem"] >= 50) & (df["num_org_mem"] < 100), "lead_score"] += 4
    df.loc[(df["num_org_mem"] >= 10) & (df["num_org_mem"] < 50), "lead_score"] += 2
    df.loc[(df["num_org_mem"] > 0) & (df["num_org_mem"] < 10), "lead_score"] += 1
    df.loc[df["has_phone"], "lead_score"] += 2
    df.loc[df["grp_assgn"] == "Y", "lead_score"] += 1
    df.loc[df["Telehlth"].notna() & (df["Telehlth"].str.strip() != ""), "lead_score"] += 1

    # Select only needed columns to reduce file size
    print("\nSelecting columns...")
    columns_to_keep = [
        # Organization info
        "Facility Name", "org_pac_id", "num_org_mem", "org_size_category",
        "grp_assgn", "lead_score",
        # Provider info
        "provider_full_name", "NPI", "Ind_PAC_ID", "Cred", "gndr",
        "pri_spec", "sec_spec_all",
        # Contact
        "phone_clean", "has_phone", "email", "has_email",
        # Location
        "full_address", "city_clean", "state_clean", "ZIP Code",
        # Education
        "Med_sch", "Grd_yr",
        # Other
        "ind_assgn", "Telehlth"
    ]

    df_clean = df[columns_to_keep].copy()

    # Save as compressed parquet with optimal settings
    print("\nSaving preprocessed data...")
    output_file = "data/preprocessed_dashboard_data.parquet"
    Path("data").mkdir(exist_ok=True)

    df_clean.to_parquet(
        output_file,
        engine='pyarrow',
        compression='snappy',  # Fast compression/decompression
        index=False
    )

    file_size_mb = Path(output_file).stat().st_size / (1024 * 1024)
    print(f"\n✅ Saved to {output_file}")
    print(f"   Rows: {len(df_clean):,}")
    print(f"   Columns: {len(df_clean.columns)}")
    print(f"   Size: {file_size_mb:.1f} MB")
    print(f"   Memory: {df_clean.memory_usage(deep=True).sum() / (1024**2):.1f} MB")

    return df_clean

if __name__ == "__main__":
    df = preprocess_data()
    print("\n" + "="*60)
    print("Preprocessing complete! Update streamlit_app.py to use:")
    print("  data/preprocessed_dashboard_data.parquet")
    print("="*60)
