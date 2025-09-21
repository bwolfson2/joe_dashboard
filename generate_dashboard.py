#!/usr/bin/env python3
import csv
import json
from collections import Counter, defaultdict

def analyze_contact_data(filepath):
    """Analyze the contact data CSV for sales lead generation"""
    
    print("Loading and analyzing data for sales leads...")
    
    # Initialize counters and data structures
    total_records = 0
    leads_data = []
    
    # Counters for analysis
    states = []
    cities = []
    specializations = []
    business_names = []
    official_titles = []
    phone_numbers = []
    
    # Lead scoring factors
    large_organizations = []  # Based on doctor_count
    decision_makers = []  # Based on titles
    
    # Read CSV
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            total_records += 1
            
            # Extract key lead information
            lead_info = {
                'business_name': row.get('agreed_upon_name', '').strip(),
                'contact_name': f"{row.get('Authorized Official First Name', '')} {row.get('Authorized Official Last Name', '')}".strip(),
                'title': row.get('Authorized Official Title or Position', '').strip(),
                'phone': row.get('Authorized Official Telephone Number', '').strip(),
                'city': row.get('Provider Business Practice Location Address City Name', '').strip(),
                'state': row.get('Provider Business Practice Location Address State Name', '').strip(),
                'specialization': row.get('Classification_1', '').strip(),
                'doctor_count': row.get('doctor_count', '0').strip(),
                'is_sole_proprietor': row.get('Is Sole Proprietor', '').strip(),
                'address': row.get('address_1', '').strip()
            }
            
            # Score lead quality
            score = 0
            
            # Higher doctor count = larger organization = better lead
            try:
                doc_count = int(lead_info['doctor_count'])
                if doc_count > 10:
                    score += 3
                elif doc_count > 5:
                    score += 2
                elif doc_count > 0:
                    score += 1
            except:
                pass
            
            # Decision maker titles
            title_lower = lead_info['title'].lower()
            if any(t in title_lower for t in ['president', 'ceo', 'director', 'owner', 'manager', 'administrator']):
                score += 2
                decision_makers.append(lead_info)
            
            # Has phone number
            if lead_info['phone'] and lead_info['phone'] != '':
                score += 1
                phone_numbers.append(lead_info['phone'])
            
            # Not sole proprietor (larger org)
            if lead_info['is_sole_proprietor'] == 'N':
                score += 1
            
            lead_info['lead_score'] = score
            
            # Only keep leads with score > 0 and valid contact info
            if score > 0 and (lead_info['phone'] or lead_info['contact_name']):
                leads_data.append(lead_info)
            
            # Collect for analysis
            if lead_info['state']:
                states.append(lead_info['state'])
            if lead_info['city']:
                cities.append(lead_info['city'])
            if lead_info['specialization']:
                specializations.append(lead_info['specialization'])
            if lead_info['business_name']:
                business_names.append(lead_info['business_name'])
            if lead_info['title']:
                official_titles.append(lead_info['title'])
            
            # Track large organizations
            try:
                if int(lead_info['doctor_count']) >= 10:
                    large_organizations.append(lead_info)
            except:
                pass
            
            if total_records % 10000 == 0:
                print(f"Processed {total_records} records...")
    
    # Sort leads by score
    leads_data.sort(key=lambda x: x['lead_score'], reverse=True)
    
    # Count occurrences
    state_counts = Counter(states)
    city_counts = Counter(cities)
    spec_counts = Counter(specializations)
    title_counts = Counter(official_titles)
    
    # Get top leads by various criteria
    top_leads = leads_data[:100]  # Top 100 by score
    
    # Group leads by state for territory planning
    leads_by_state = defaultdict(list)
    for lead in leads_data[:1000]:  # Top 1000 leads
        if lead['state']:
            leads_by_state[lead['state']].append(lead)
    
    # Count leads by state
    leads_count_by_state = {state: len(leads) for state, leads in leads_by_state.items()}
    
    # Create dashboard data
    dashboard_data = {
        'summary': {
            'total_records_analyzed': total_records,
            'qualified_leads': len(leads_data),
            'high_value_leads': len([l for l in leads_data if l['lead_score'] >= 4]),
            'decision_makers_found': len(decision_makers),
            'large_organizations': len(large_organizations),
            'leads_with_phone': len([l for l in leads_data if l['phone']]),
            'unique_businesses': len(set(business_names))
        },
        'top_leads': top_leads[:50],  # Top 50 for display
        'leads_by_state_count': dict(Counter(leads_count_by_state).most_common(20)),
        'top_states_by_volume': dict(state_counts.most_common(10)),
        'top_cities': dict(city_counts.most_common(15)),
        'top_specializations': dict(spec_counts.most_common(15)),
        'decision_maker_titles': dict(title_counts.most_common(10)),
        'large_organizations': large_organizations[:20],  # Top 20 large orgs
        'territory_analysis': {
            'states_with_leads': len(leads_by_state),
            'avg_leads_per_state': len(leads_data) / max(len(leads_by_state), 1)
        }
    }
    
    return dashboard_data

if __name__ == "__main__":
    # Analyze the data
    data = analyze_contact_data('contact_info_for_joe.csv')
    
    # Save to JSON for the dashboard
    with open('dashboard_data.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print("\n✅ Sales lead dashboard data generated successfully!")
    print(f"📊 Total records analyzed: {data['summary']['total_records_analyzed']:,}")
    print(f"🎯 Qualified leads found: {data['summary']['qualified_leads']:,}")
    print(f"⭐ High-value leads: {data['summary']['high_value_leads']:,}")
    print(f"👔 Decision makers: {data['summary']['decision_makers_found']:,}")
    print(f"🏢 Large organizations: {data['summary']['large_organizations']:,}")
    print(f"📞 Leads with phone numbers: {data['summary']['leads_with_phone']:,}")