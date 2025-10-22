import json
import re
import pandas as pd
import argparse
import numpy as np
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm
import time
from multiprocessing import Pool, cpu_count
from functools import partial


def normalize_org_name(name):
    """Normalize organization name for better matching"""
    if pd.isna(name):
        return ""

    name = str(name).upper().strip()

    # Remove common punctuation variations
    replacements = {
        ' INC.': ' INC',
        ' INC,': ' INC',
        ' LLC.': ' LLC',
        ' LLC,': ' LLC',
        ' P.C.': ' PC',
        ' P.C,': ' PC',
        ' P.A.': ' PA',
        ' P.A,': ' PA',
        ' L.L.C.': ' LLC',
        ' L.L.C': ' LLC',
        ' L.P.': ' LP',
        ' PLLC.': ' PLLC',
        ',': '',
        '.': '',
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    # Remove extra whitespace
    name = ' '.join(name.split())

    return name


def create_facility_key(org_name, city, state):
    """Create standardized facility key: 'ORG NAME, CITY, STATE'"""
    org_name = normalize_org_name(org_name)
    city = str(city).upper().strip() if not pd.isna(city) else ""
    state = str(state).upper().strip() if not pd.isna(state) else ""

    if org_name and city and state:
        return f"{org_name}, {city}, {state}"
    return None


def load_email_formats(formats_file='output/extracted_email_formats.json'):
    """Load extracted email formats"""
    with open(formats_file, 'r') as f:
        formats = json.load(f)

    # Normalize keys for matching
    normalized_formats = {}
    for key, value in formats.items():
        # Key is already in "Facility Name, City, State" format
        # Normalize it
        parts = key.rsplit(', ', 2)
        if len(parts) == 3:
            org, city, state = parts
            normalized_key = create_facility_key(org, city, state)
            if normalized_key:
                normalized_formats[normalized_key] = {
                    'original_key': key,
                    **value
                }

    return normalized_formats


def generate_email(first_name, last_name, email_format, domain):
    """Generate email address based on format template"""
    if not first_name or not last_name or pd.isna(first_name) or pd.isna(last_name):
        return None

    # Clean and lowercase names
    first = str(first_name).strip().lower()
    last = str(last_name).strip().lower()

    # Remove spaces, hyphens, apostrophes
    first = re.sub(r'[^a-z]', '', first)
    last = re.sub(r'[^a-z]', '', last)

    if not first or not last:
        return None

    first_initial = first[0] if first else ''
    last_initial = last[0] if last else ''

    # Apply format
    if email_format == '[first].[last]':
        return f"{first}.{last}@{domain}"
    elif email_format == '[first_initial][last]':
        return f"{first_initial}{last}@{domain}"
    elif email_format == '[first][last_initial]':
        return f"{first}{last_initial}@{domain}"
    elif email_format == '[first]':
        return f"{first}@{domain}"
    elif email_format == '[last]':
        return f"{last}@{domain}"
    elif email_format == '[first]_[last]':
        return f"{first}_{last}@{domain}"
    elif email_format == '[first]-[last]':
        return f"{first}-{last}@{domain}"
    elif email_format == '[first][last]':
        return f"{first}{last}@{domain}"

    return None


class FacilityMatcher:
    """Handles fuzzy matching with TF-IDF for facilities"""

    def __init__(self, email_formats, threshold=0.85):
        self.email_formats = email_formats
        self.threshold = threshold

        # Group facilities by city+state for efficient matching
        self.facilities_by_location = {}

        for key in email_formats.keys():
            parts = key.rsplit(', ', 2)
            if len(parts) == 3:
                org, city, state = parts
                location = f"{city}, {state}"

                if location not in self.facilities_by_location:
                    self.facilities_by_location[location] = []

                self.facilities_by_location[location].append({
                    'key': key,
                    'org_name': org
                })

    def match_facility(self, org_name, city, state):
        """
        Try to match facility using 3-tier approach:
        1. Exact match
        2. Fuzzy exact (normalized)
        3. TF-IDF similarity (within same city+state)
        """
        # Tier 1: Exact match
        exact_key = create_facility_key(org_name, city, state)
        if exact_key in self.email_formats:
            return {
                'matched_key': exact_key,
                'match_type': 'exact',
                'match_score': 1.0,
                'format_info': self.email_formats[exact_key]
            }

        # Tier 2 & 3: Check if this location exists in our database
        location = f"{str(city).upper().strip()}, {str(state).upper().strip()}"

        if location not in self.facilities_by_location:
            return None  # No facilities in this city+state

        candidates = self.facilities_by_location[location]

        # Tier 2: Fuzzy exact - check for very close matches
        normalized_org = normalize_org_name(org_name)
        for candidate in candidates:
            if normalized_org == candidate['org_name']:
                return {
                    'matched_key': candidate['key'],
                    'match_type': 'fuzzy_exact',
                    'match_score': 1.0,
                    'format_info': self.email_formats[candidate['key']]
                }

        # Tier 3: TF-IDF similarity
        if len(candidates) == 0:
            return None

        # Prepare texts for TF-IDF
        candidate_names = [c['org_name'] for c in candidates]
        all_names = [normalized_org] + candidate_names

        # Compute TF-IDF
        vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 3))
        tfidf_matrix = vectorizer.fit_transform(all_names)

        # Calculate similarity
        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

        # Find best match above threshold
        best_idx = np.argmax(similarities)
        best_score = similarities[best_idx]

        if best_score >= self.threshold:
            matched_candidate = candidates[best_idx]
            return {
                'matched_key': matched_candidate['key'],
                'match_type': 'tfidf',
                'match_score': float(best_score),
                'format_info': self.email_formats[matched_candidate['key']]
            }

        return None


def process_single_record(row_data, email_formats, threshold):
    """Process a single admin record - designed for parallel execution"""
    idx, row = row_data

    org_name = row['Provider Organization Name (Legal Business Name)']
    city = row['Provider Business Practice Location Address City Name']
    state = row['Provider Business Practice Location Address State Name']
    first_name = row['Authorized Official First Name']
    last_name = row['Authorized Official Last Name']

    # Create facility key
    facility_key = create_facility_key(org_name, city, state)

    result = {
        'idx': idx,
        'facility_key': facility_key,
        'matched_facility': None,
        'match_type': None,
        'match_score': None,
        'generated_email': None,
        'email_format_used': None,
        'email_domain': None
    }

    if not facility_key:
        return result

    # Create matcher for this worker (can't share across processes)
    matcher = FacilityMatcher(email_formats, threshold=threshold)

    # Try to match
    match_result = matcher.match_facility(org_name, city, state)

    if match_result:
        result['matched_facility'] = match_result['matched_key']
        result['match_type'] = match_result['match_type']
        result['match_score'] = match_result['match_score']

        # Generate email
        format_info = match_result['format_info']
        email = generate_email(
            first_name,
            last_name,
            format_info['format'],
            format_info['domain']
        )

        if email:
            result['generated_email'] = email
            result['email_format_used'] = format_info['format']
            result['email_domain'] = format_info['domain']

    return result


def process_admin_data(admin_file, email_formats, threshold=0.85, max_records=None, n_workers=None):
    """Process admin data and generate emails with parallel processing"""

    print(f"\nLoading admin data from {admin_file}...")
    admin_df = pd.read_parquet(admin_file)

    if max_records:
        admin_df = admin_df.head(max_records).copy()
        print(f"Limited to {max_records} records for testing")

    print(f"Loaded {len(admin_df):,} admin records")

    # Reset index to avoid issues
    admin_df = admin_df.reset_index(drop=True)

    # Determine number of workers
    if n_workers is None:
        n_workers = max(1, cpu_count() - 1)  # Leave one CPU free

    print(f"Using {n_workers} parallel workers")

    # Prepare output columns
    admin_df['facility_key'] = None
    admin_df['matched_facility'] = None
    admin_df['match_type'] = None
    admin_df['match_score'] = None
    admin_df['generated_email'] = None
    admin_df['email_format_used'] = None
    admin_df['email_domain'] = None

    # Statistics
    stats = {
        'exact': 0,
        'fuzzy_exact': 0,
        'tfidf': 0,
        'unmatched': 0,
        'emails_generated': 0
    }

    print("\nProcessing admin records in parallel...")
    print("=" * 80)

    # Track timing
    start_time = time.time()

    # Prepare data for parallel processing
    row_data = [(idx, row) for idx, row in admin_df.iterrows()]

    # Create partial function with fixed parameters
    process_func = partial(process_single_record, email_formats=email_formats, threshold=threshold)

    # Process in parallel with progress bar
    with Pool(processes=n_workers) as pool:
        results = list(tqdm(
            pool.imap(process_func, row_data, chunksize=1000),
            total=len(row_data),
            desc="Processing",
            unit="records",
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
        ))

    # Apply results back to dataframe
    print("\nApplying results to dataframe...")
    for result in tqdm(results, desc="Updating", unit="records"):
        idx = result['idx']
        admin_df.at[idx, 'facility_key'] = result['facility_key']
        admin_df.at[idx, 'matched_facility'] = result['matched_facility']
        admin_df.at[idx, 'match_type'] = result['match_type']
        admin_df.at[idx, 'match_score'] = result['match_score']
        admin_df.at[idx, 'generated_email'] = result['generated_email']
        admin_df.at[idx, 'email_format_used'] = result['email_format_used']
        admin_df.at[idx, 'email_domain'] = result['email_domain']

        # Update statistics
        if result['generated_email']:
            stats['emails_generated'] += 1
        if result['match_type']:
            stats[result['match_type']] += 1
        else:
            stats['unmatched'] += 1

    # Final timing
    total_time = time.time() - start_time

    print(f"✓ Processing complete in {total_time/60:.1f} minutes ({len(admin_df)/total_time:.0f} records/sec)")

    return admin_df, stats


def main():
    parser = argparse.ArgumentParser(
        description='Add administrators with email generation based on facility matching'
    )
    parser.add_argument(
        '-a', '--admin-file',
        type=str,
        default='data/admin.parquet',
        help='Path to admin parquet file (default: data/admin.parquet)'
    )
    parser.add_argument(
        '-f', '--formats-file',
        type=str,
        default="output/email_formats/extracted_email_formats.json",
        help='Path to extracted email formats JSON (default: output/extracted_email_formats_improved.json)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default="output/admins/admins_with_emails.csv",
        help='Path to output CSV file (default: output/admins_with_emails.csv)'
    )
    parser.add_argument(
        '-t', '--threshold',
        type=float,
        default=0.85,
        help='TF-IDF similarity threshold (default: 0.85)'
    )
    parser.add_argument(
        '-m', '--max-records',
        type=int,
        default=None,
        help='Maximum records to process (for testing)'
    )
    parser.add_argument(
        '-w', '--workers',
        type=int,
        default=None,
        help='Number of parallel workers (default: auto-detect, uses CPU count - 1)'
    )
    parser.add_argument(
        '--save-unmatched',
        action='store_true',
        help='Save unmatched records to separate file'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("Administrator Email Generation (PARALLELIZED)")
    print("=" * 80)

    # Load email formats
    print(f"\nLoading email formats from {args.formats_file}...")
    email_formats = load_email_formats(args.formats_file)
    print(f"✓ Loaded {len(email_formats)} facility email formats")

    # Process admin data
    admin_df, stats = process_admin_data(
        args.admin_file,
        email_formats,
        threshold=args.threshold,
        max_records=args.max_records,
        n_workers=args.workers
    )

    # Save results
    print(f"\nSaving results to {args.output}...")
    admin_df.to_csv(args.output, index=False)
    print(f"✓ Saved {len(admin_df):,} records")

    # Save unmatched if requested
    if args.save_unmatched:
        unmatched_df = admin_df[admin_df['match_type'].isna()]
        unmatched_file = args.output.replace('.csv', '_unmatched.csv')
        unmatched_df.to_csv(unmatched_file, index=False)
        print(f"✓ Saved {len(unmatched_df):,} unmatched records to {unmatched_file}")

    # Print statistics
    print("\n" + "=" * 80)
    print("MATCHING STATISTICS")
    print("=" * 80)
    print(f"Total records processed:    {len(admin_df):,}")
    print(f"\nMatching Results:")
    print(f"  Exact matches:            {stats['exact']:,}")
    print(f"  Fuzzy exact matches:      {stats['fuzzy_exact']:,}")
    print(f"  TF-IDF matches:           {stats['tfidf']:,}")
    print(f"  Unmatched:                {stats['unmatched']:,}")
    print(f"\nEmail Generation:")
    print(f"  Emails generated:         {stats['emails_generated']:,}")
    print(f"  Success rate:             {stats['emails_generated']/len(admin_df)*100:.2f}%")

    # Show sample results
    print("\n" + "=" * 80)
    print("SAMPLE GENERATED EMAILS")
    print("=" * 80)

    sample = admin_df[admin_df['generated_email'].notna()].head(10)
    for idx, row in sample.iterrows():
        print(f"\n{row['Authorized Official First Name']} {row['Authorized Official Last Name']}")
        print(f"  Title: {row['Authorized Official Title or Position']}")
        print(f"  Organization: {row['Provider Organization Name (Legal Business Name)']}")
        print(f"  Location: {row['Provider Business Practice Location Address City Name']}, {row['Provider Business Practice Location Address State Name']}")
        print(f"  Matched: {row['matched_facility']}")
        print(f"  Match Type: {row['match_type']} (score: {row['match_score']:.3f})")
        print(f"  Email: {row['generated_email']}")
        print(f"  Format: {row['email_format_used']}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
