import json
import re
import pandas as pd
import argparse
from pathlib import Path


def extract_formats_from_text_improved(text, source_link=''):
    """
    Comprehensive email format extraction supporting ALL known patterns:
    - RocketReach bracket notation: [first].[last] (ex. jane.doe@domain.com)
    - RocketReach numbered format: 1. first@domain.com (33.3%)
    - LeadIQ capitalized: FLast@domain.com, First.Last@domain.com, First_Last@domain.com
    - Percentage-based mentions
    - "most common" and "typically follows" patterns
    """
    extracted = []

    # PATTERN GROUP 1: RocketReach Bracket Notation with Examples
    # [first_initial][last] (ex. jdoe@domain.com)
    # IMPORTANT: Check more specific patterns FIRST to avoid false matches
    bracket_patterns = [
        (r'\[first\]\.\[last\]\s*\(ex\.\s*([a-z]+\.[a-z]+@[a-z0-9\-\.]+)', '[first].[last]'),
        (r'\[first\]_\[last\]\s*\(ex\.\s*([a-z]+_[a-z]+@[a-z0-9\-\.]+)', '[first]_[last]'),
        (r'\[first\]-\[last\]\s*\(ex\.\s*([a-z]+-[a-z]+@[a-z0-9\-\.]+)', '[first]-[last]'),
        (r'\[first_initial\]\[last\]\s*\(ex\.\s*([a-z]+@[a-z0-9\-\.]+)', '[first_initial][last]'),
        (r'\[first\]\[last_initial\]\s*\(ex\.\s*([a-z]+@[a-z0-9\-\.]+)', '[first][last_initial]'),
        (r'(?:format is |pattern is )\[first\]\s*\(ex\.\s*([a-z]+@[a-z0-9\-\.]+)', '[first]'),
        (r'(?:format is |pattern is )\[last\]\s*\(ex\.\s*([a-z]+@[a-z0-9\-\.]+)', '[last]'),
    ]

    for pattern, format_name in bracket_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            example_email = match.group(1).lower()
            domain = example_email.split('@')[1] if '@' in example_email else None
            if domain:
                extracted.append({
                    'format': format_name,
                    'domain': domain,
                    'example': example_email,
                    'source': source_link,
                    'confidence': 'high'
                })

    # PATTERN GROUP 2: RocketReach Numbered Format
    # "1. first@domain.com (33.3%)"
    # "1. first.last@domain.com (50%)"
    # IMPORTANT: Order matters! Check more specific patterns first
    numbered_patterns = [
        # Dotted: first.last@domain
        (r'1\.\s+([a-z]+)\.([a-z]+)@([a-z0-9\-\.]+\.[a-z]{2,})\s*\(', '[first].[last]'),
        # Underscore: first_last@domain
        (r'1\.\s+([a-z]+)_([a-z]+)@([a-z0-9\-\.]+\.[a-z]{2,})\s*\(', '[first]_[last]'),
        # Hyphen: first-last@domain
        (r'1\.\s+([a-z]+)-([a-z]+)@([a-z0-9\-\.]+\.[a-z]{2,})\s*\(', '[first]-[last]'),
        # Initial+Last: jdoe@domain (single letter + multiple letters)
        (r'1\.\s+([a-z])([a-z]{2,})@([a-z0-9\-\.]+\.[a-z]{2,})\s*\(', '[first_initial][last]'),
        # Simple: first@domain (multiple letters)
        (r'1\.\s+([a-z]{2,})@([a-z0-9\-\.]+\.[a-z]{2,})\s*\(', '[first]'),
    ]

    for pattern, format_name in numbered_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            # Last group is always the domain
            domain = groups[-1]

            # Reconstruct example email
            if format_name == '[first]':
                example_email = f"{groups[0]}@{domain}"
            elif format_name in ['[first].[last]', '[first]_[last]', '[first]-[last]']:
                sep = '.' if format_name == '[first].[last]' else ('_' if format_name == '[first]_[last]' else '-')
                example_email = f"{groups[0]}{sep}{groups[1]}@{domain}"
            elif format_name == '[first_initial][last]':
                example_email = f"{groups[0]}{groups[1]}@{domain}"

            extracted.append({
                'format': format_name,
                'domain': domain,
                'example': example_email.lower(),
                'source': source_link,
                'confidence': 'high'
            })
            break  # Use first numbered format found

    # PATTERN GROUP 3: LeadIQ Capitalized Formats
    # "typically follows the pattern of FLast@domain.com"
    # "typically follows the pattern of First.Last@domain.com"
    leadiq_patterns = [
        (r'(?:pattern of |format of )?FLast@([a-z0-9\-\.]+\.[a-z]{2,})', '[first_initial][last]'),
        (r'(?:pattern of |format of )?First\.Last@([a-z0-9\-\.]+\.[a-z]{2,})', '[first].[last]'),
        (r'(?:pattern of |format of )?First_Last@([a-z0-9\-\.]+\.[a-z]{2,})', '[first]_[last]'),
        (r'(?:pattern of |format of )?First-Last@([a-z0-9\-\.]+\.[a-z]{2,})', '[first]-[last]'),
        (r'(?:pattern of |format of )?FirstLast@([a-z0-9\-\.]+\.[a-z]{2,})', '[first][last]'),
        (r'(?:pattern of |format of )?First@([a-z0-9\-\.]+\.[a-z]{2,})', '[first]'),
    ]

    for pattern, format_name in leadiq_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            domain = match.group(1).lower()

            # Create example email
            if format_name == '[first_initial][last]':
                example_email = f"jdoe@{domain}"
            elif format_name == '[first].[last]':
                example_email = f"jane.doe@{domain}"
            elif format_name == '[first]_[last]':
                example_email = f"jane_doe@{domain}"
            elif format_name == '[first]-[last]':
                example_email = f"jane-doe@{domain}"
            elif format_name == '[first][last]':
                example_email = f"janedoe@{domain}"
            elif format_name == '[first]':
                example_email = f"jane@{domain}"

            extracted.append({
                'format': format_name,
                'domain': domain,
                'example': example_email,
                'source': source_link,
                'confidence': 'high'
            })

    # PATTERN GROUP 4: Fallback - Extract any email and infer format
    # This catches edge cases
    if not extracted:
        email_pattern = r'\b([a-zA-Z0-9]+(?:[._-][a-zA-Z0-9]+)?)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
        email_matches = re.finditer(email_pattern, text)

        for match in email_matches:
            local_part = match.group(1).lower()
            domain = match.group(2).lower()

            # Infer format from local part structure
            inferred_format = infer_format_from_local_part(local_part)

            if inferred_format:
                extracted.append({
                    'format': inferred_format,
                    'domain': domain,
                    'example': f"{local_part}@{domain}",
                    'source': source_link,
                    'confidence': 'medium'
                })
                break  # Use first email found

    return extracted


def infer_format_from_local_part(local_part):
    """Infer email format from the structure of the local part"""
    if '.' in local_part:
        parts = local_part.split('.')
        if len(parts) == 2 and len(parts[0]) > 1 and len(parts[1]) > 1:
            return '[first].[last]'
    elif '_' in local_part:
        parts = local_part.split('_')
        if len(parts) == 2 and len(parts[0]) > 1 and len(parts[1]) > 1:
            return '[first]_[last]'
    elif '-' in local_part:
        parts = local_part.split('-')
        if len(parts) == 2 and len(parts[0]) > 1 and len(parts[1]) > 1:
            return '[first]-[last]'
    elif len(local_part) > 2:
        # Could be [first_initial][last] like "jdoe"
        if len(local_part) <= 6:
            return '[first_initial][last]'
        else:
            return '[first]'

    return None


def extract_formats_from_serper_results(results_file):
    """Extract email formats from Serper results with priority logic"""
    with open(results_file, 'r') as f:
        results = json.load(f)

    email_formats = {}

    for entry in results:
        facility = entry['facility']
        search_results = entry.get('results', {})

        if not search_results:
            continue

        best_match = None
        best_priority = 0

        # Check answer box first (highest priority)
        answer_box = search_results.get('answerBox', {})
        if answer_box:
            snippet = answer_box.get('snippet', '')
            link = answer_box.get('link', '')

            formats = extract_formats_from_text_improved(snippet, link)
            if formats:
                best_match = formats[0]
                best_match['source_type'] = 'answerBox'
                best_priority = 100

        # Check organic results - prioritize first result and known sources
        if not best_match or best_priority < 90:
            for position, organic in enumerate(search_results.get('organic', [])):
                link = organic.get('link', '')
                snippet = organic.get('snippet', '')

                # Calculate priority
                priority = 0
                if 'rocketreach.co' in link:
                    priority = 80
                elif 'leadiq.com' in link:
                    priority = 70
                elif 'contactout.com' in link:
                    priority = 60
                elif 'signalhire.com' in link:
                    priority = 50

                # Boost first result
                if position == 0:
                    priority += 10

                if priority > best_priority:
                    formats = extract_formats_from_text_improved(snippet, link)
                    if formats:
                        best_match = formats[0]
                        best_match['source_type'] = 'organic'
                        best_priority = priority

        if best_match:
            email_formats[facility] = best_match

    return email_formats


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


def apply_formats_to_csv(csv_file, email_formats, output_file):
    """Apply email formats to the doctor CSV file"""
    print(f"\nReading {csv_file}...")
    df = pd.read_csv(csv_file, low_memory=False)

    print(f"Loaded {len(df):,} records")
    print(f"Found email formats for {len(email_formats)} unique facilities")

    # Create new columns
    df['generated_email'] = None
    df['email_format_used'] = None
    df['email_domain'] = None
    df['email_source'] = None
    df['email_confidence'] = None

    # Apply formats
    emails_generated = 0
    facilities_with_emails = set()

    for idx, row in df.iterrows():
        facility_key = row['full_name_city_state']

        if facility_key in email_formats:
            format_info = email_formats[facility_key]

            email = generate_email(
                row.get('Provider First Name'),
                row.get('Provider Last Name'),
                format_info['format'],
                format_info['domain']
            )

            if email:
                df.at[idx, 'generated_email'] = email
                df.at[idx, 'email_format_used'] = format_info['format']
                df.at[idx, 'email_domain'] = format_info['domain']
                df.at[idx, 'email_source'] = format_info.get('source_type', 'unknown')
                df.at[idx, 'email_confidence'] = format_info.get('confidence', 'unknown')
                emails_generated += 1
                facilities_with_emails.add(facility_key)

    # Save to new CSV
    df.to_csv(output_file, index=False)

    print(f"\n✓ Generated {emails_generated:,} email addresses")
    print(f"✓ Covered {len(facilities_with_emails)} unique facilities")
    print(f"✓ Results saved to: {output_file}")

    # Print summary
    print("\n" + "=" * 80)
    print("Email Format Summary:")
    print("=" * 80)
    format_counts = df['email_format_used'].value_counts()
    for format_type, count in format_counts.items():
        if pd.notna(format_type):
            print(f"  {format_type:30} {count:6,} emails")

    print("\n" + "=" * 80)
    print("Confidence Level Summary:")
    print("=" * 80)
    conf_counts = df['email_confidence'].value_counts()
    for conf_type, count in conf_counts.items():
        if pd.notna(conf_type):
            print(f"  {conf_type:30} {count:6,} emails")

    # Show sample emails
    print("\n" + "=" * 80)
    print("Sample Generated Emails:")
    print("=" * 80)
    sample = df[df['generated_email'].notna()].head(10)
    for idx, row in sample.iterrows():
        print(f"  {row['provider_full_name']:40} → {row['generated_email']}")
        print(f"    Facility: {row['Facility Name']}")
        print(f"    Format: {row['email_format_used']} (confidence: {row['email_confidence']})")
        print()

    return df


def main():
    parser = argparse.ArgumentParser(
        description='Extract email formats from Serper results (IMPROVED VERSION)'
    )
    parser.add_argument(
        '-r', '--results',
        type=str,
        help='Path to Serper results JSON file'
    )
    parser.add_argument(
        '-c', '--csv',
        type=str,
        default='cleaned_md_doctors.csv',
        help='Path to input CSV file'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='output/doctors/doctors_with_emails.csv',
        help='Path to output CSV file'
    )
    parser.add_argument(
        '--save-formats',
        action='store_true',
        help='Save extracted email formats to JSON'
    )

    args = parser.parse_args()

    # Find latest results file if not specified
    if not args.results:
        import glob
        results_files = glob.glob('output/serper_results_*.json')
        if results_files:
            args.results = max(results_files)
            print(f"Using latest results file: {args.results}")
        else:
            print("Error: No Serper results files found")
            return

    print("=" * 80)
    print("IMPROVED Email Format Extractor & Applier")
    print("=" * 80)

    # Extract formats
    print(f"\nExtracting email formats from {args.results}...")
    email_formats = extract_formats_from_serper_results(args.results)

    print(f"\n✓ Extracted {len(email_formats)} email formats")

    # Save formats if requested
    if args.save_formats:
        formats_file = 'output/email_formats/extracted_email_formats.json'
        with open(formats_file, 'w') as f:
            json.dump(email_formats, f, indent=2)
        print(f"✓ Saved email formats to {formats_file}")

    # Apply to CSV
    print("\n" + "=" * 80)
    df = apply_formats_to_csv(args.csv, email_formats, args.output)
    print("=" * 80)


if __name__ == "__main__":
    main()
