#!/usr/bin/env python3
import csv

# Read first few rows to examine structure
with open('contact_info_for_joe.csv', 'r', encoding='utf-8', errors='ignore') as f:
    reader = csv.DictReader(f)
    
    # Get column names
    columns = reader.fieldnames
    print("=== KEY CONTACT FIELDS ===")
    for i, col in enumerate(columns, 1):
        if 'address' in col.lower() or 'phone' in col.lower() or 'email' in col.lower() or 'endpoint' in col.lower():
            print(f"{i}: {col}")
    
    print("\n=== FIRST 3 ROWS - KEY FIELDS ===")
    for row_num, row in enumerate(reader):
        if row_num >= 3:
            break
        
        print(f"\n--- ROW {row_num + 1} ---")
        print(f"Organization: {row.get('agreed_upon_name', '')[:50]}")
        print(f"Auth Phone: {row.get('Authorized Official Telephone Number', '')}")
        print(f"address_1: {row.get('address_1', '')[:100]}")
        print(f"address_2: {row.get('address_2', '')[:100]}")
        print(f"address_group: {row.get('address_group', '')[:100]}")
        
        # Check endpoint fields (might contain emails)
        endpoint = row.get('cf_Endpoint', '')
        endpoint_type = row.get('cf_Endpoint Type', '')
        endpoint_desc = row.get('cf_Endpoint Type Description', '')
        
        print(f"cf_Endpoint Type: {endpoint_type}")
        print(f"cf_Endpoint Desc: {endpoint_desc}")
        print(f"cf_Endpoint: {endpoint[:100]}")
        
        # Affiliation address
        print(f"Affiliation Address: {row.get('cf_Affiliation Address Line One', '')} {row.get('cf_Affiliation Address City', '')} {row.get('cf_Affiliation Address State', '')} {row.get('cf_Affiliation Address Postal Code', '')}")
        
        # Business addresses
        print(f"Mailing: {row.get('Provider Business Mailing Address City Name', '')}, {row.get('Provider Business Mailing Address State Name', '')}")
        print(f"Practice: {row.get('Provider Business Practice Location Address City Name', '')}, {row.get('Provider Business Practice Location Address State Name', '')}")