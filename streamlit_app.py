import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Healthcare Sales Lead Dashboard",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better formatting
st.markdown("""
<style>
    .main > div {
        padding-top: 1rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .lead-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        margin-bottom: 15px;
        border-left: 4px solid #1f77b4;
    }
    .high-value {
        border-left: 4px solid #28a745 !important;
    }
    .contact-info {
        background-color: #e8f4f8;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_and_process_data():
    """Load and process the healthcare provider data"""
    # Load multiple CSV files and combine them
    csv_files = ['contact_info_1.csv', 'contact_info_2.csv', 'contact_info_3.csv', 'contact_info_4.csv']
    dfs = []
    for file in csv_files:
        try:
            df_part = pd.read_csv(file, low_memory=False)
            dfs.append(df_part)
        except FileNotFoundError:
            st.warning(f"File {file} not found, skipping...")

    if not dfs:
        st.error("No data files found!")
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)

    # Keep all records to show all members, but we'll group by organization later

    # Clean and process key fields
    df['doctor_count'] = pd.to_numeric(df['doctor_count'], errors='coerce').fillna(0).astype(int)
    df['phone_clean'] = df['Authorized Official Telephone Number'].astype(str).str.replace('.0', '').str.strip()
    df['has_phone'] = df['phone_clean'].apply(lambda x: x != 'nan' and x != '' and len(x) > 5)
    
    # Extract email from cf_Endpoint field
    df['email'] = df['cf_Endpoint'].apply(lambda x: str(x) if '@' in str(x) else '')
    df['has_email'] = df['email'] != ''
    
    # Create full contact name
    df['contact_full_name'] = (df['Authorized Official First Name'].fillna('') + ' ' +
                                df['Authorized Official Last Name'].fillna('')).str.strip()

    # Create provider name (individual doctor)
    df['provider_full_name'] = (df['Provider First Name'].fillna('') + ' ' +
                                df['Provider Last Name (Legal Name)'].fillna('')).str.strip()
    df['is_individual_provider'] = df['provider_full_name'] != ''
    
    # Process addresses - use address_group which contains both addresses
    df['full_address'] = df['address_group'].fillna('')
    
    # Also get individual address components
    df['mailing_address'] = df['address_1'].fillna('')
    df['practice_address'] = df['address_2'].fillna('')
    
    # Clean states and cities
    df['state_clean'] = df['Provider Business Practice Location Address State Name'].fillna('Unknown')
    df['city_clean'] = df['Provider Business Practice Location Address City Name'].fillna('Unknown')
    df['mailing_city'] = df['Provider Business Mailing Address City Name'].fillna('')
    df['mailing_state'] = df['Provider Business Mailing Address State Name'].fillna('')
    
    # Affiliation address if available
    df['affiliation_address'] = (
        df['cf_Affiliation Address Line One'].astype(str).replace('nan', '') + ' ' +
        df['cf_Affiliation Address Line Two'].astype(str).replace('nan', '') + ' ' +
        df['cf_Affiliation Address City'].astype(str).replace('nan', '') + ', ' +
        df['cf_Affiliation Address State'].astype(str).replace('nan', '') + ' ' +
        df['cf_Affiliation Address Postal Code'].astype(str).replace('nan', '')
    ).str.strip().str.replace('  ', ' ').str.strip(', ')
    
    # Calculate organization size category
    def categorize_org_size(count):
        if count >= 50:
            return "Enterprise (50+ doctors)"
        elif count >= 20:
            return "Large (20-49 doctors)"
        elif count >= 10:
            return "Medium (10-19 doctors)"
        elif count >= 5:
            return "Small Group (5-9 doctors)"
        elif count > 0:
            return "Small Practice (1-4 doctors)"
        else:
            return "Unknown"
    
    df['org_size_category'] = df['doctor_count'].apply(categorize_org_size)
    
    # Lead scoring based on sales criteria
    df['lead_score'] = 0
    
    # Score based on doctor count (organization size)
    df.loc[df['doctor_count'] >= 50, 'lead_score'] += 5
    df.loc[(df['doctor_count'] >= 20) & (df['doctor_count'] < 50), 'lead_score'] += 4
    df.loc[(df['doctor_count'] >= 10) & (df['doctor_count'] < 20), 'lead_score'] += 3
    df.loc[(df['doctor_count'] >= 5) & (df['doctor_count'] < 10), 'lead_score'] += 2
    df.loc[(df['doctor_count'] > 0) & (df['doctor_count'] < 5), 'lead_score'] += 1
    
    # Score for having leadership contact
    leadership_titles = ['PRESIDENT', 'CEO', 'DIRECTOR', 'ADMINISTRATOR', 'MANAGER', 'OWNER', 'PARTNER', 'CHIEF']
    df['is_leadership'] = df['Authorized Official Title or Position'].str.upper().apply(
        lambda x: any(title in str(x) for title in leadership_titles) if pd.notna(x) else False
    )
    df.loc[df['is_leadership'], 'lead_score'] += 3
    
    # Score for having phone number
    df.loc[df['has_phone'], 'lead_score'] += 2
    
    # Score for having email
    df.loc[df['has_email'], 'lead_score'] += 2
    
    # Score for not being sole proprietor (larger organization)
    df.loc[df['Is Sole Proprietor'] == 'N', 'lead_score'] += 1
    
    return df

def format_phone(phone):
    """Format phone number for display"""
    phone = str(phone).replace('.0', '').strip()
    if len(phone) == 10:
        return f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
    return phone

def format_address(address):
    """Format address for display"""
    if pd.isna(address) or address == '':
        return "Not available"
    # Split multiple addresses if pipe separator exists
    if '|' in address:
        addresses = address.split('|')
        return addresses[0].strip()  # Return first address
    return address.strip()

def main():
    st.title("🏥 Healthcare Sales Lead Dashboard")
    st.markdown("**Complete Contact Information:** Addresses | Emails | Phone Numbers | Leadership")
    
    # Load data
    with st.spinner("Loading healthcare provider data..."):
        df = load_and_process_data()
    
    # Sidebar filters
    with st.sidebar:
        st.header("🎯 Lead Filters")
        
        # Organization size filter
        st.subheader("Organization Size")
        size_categories = df['org_size_category'].unique()
        # Only set defaults that exist in the data
        default_sizes = [size for size in ["Enterprise (50+ doctors)", "Large (20-49 doctors)", "Medium (10-19 doctors)"]
                        if size in size_categories]
        selected_sizes = st.multiselect(
            "Select organization sizes:",
            sorted(size_categories),
            default=default_sizes if default_sizes else sorted(size_categories)[:3] if len(size_categories) >= 3 else sorted(size_categories)
        )
        
        # State filter
        st.subheader("Geographic Filter")
        states = df['state_clean'].unique()
        states = [s for s in states if s != 'Unknown']
        selected_states = st.multiselect(
            "Select states:",
            sorted(states),
            default=[]
        )
        
        # Contact filters
        st.subheader("Contact Requirements")
        only_leadership = st.checkbox("Only show leadership contacts", value=True)
        only_with_phone = st.checkbox("Must have phone number", value=True)
        only_with_email = st.checkbox("Must have email address", value=False)
        
        # Minimum doctor count
        min_doctors = st.slider(
            "Minimum doctor count:",
            min_value=0,
            max_value=100,
            value=5,
            step=1
        )
        
        # Apply filters
        filtered_df = df.copy()
        
        if selected_sizes:
            filtered_df = filtered_df[filtered_df['org_size_category'].isin(selected_sizes)]
        if selected_states:
            filtered_df = filtered_df[filtered_df['state_clean'].isin(selected_states)]
        if only_leadership:
            filtered_df = filtered_df[filtered_df['is_leadership']]
        if only_with_phone:
            filtered_df = filtered_df[filtered_df['has_phone']]
        if only_with_email:
            filtered_df = filtered_df[filtered_df['has_email']]
        
        filtered_df = filtered_df[filtered_df['doctor_count'] >= min_doctors]
        
        # Sort by lead score and doctor count
        filtered_df = filtered_df.sort_values(['lead_score', 'doctor_count'], ascending=False)
    
    # Key metrics
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric(
            "Total Leads",
            f"{len(filtered_df):,}",
            delta=f"{len(filtered_df[filtered_df['lead_score'] >= 8]):,} high-value"
        )
    
    with col2:
        avg_doctors = filtered_df['doctor_count'].mean()
        st.metric(
            "Avg. Doctors",
            f"{avg_doctors:.1f}",
            delta=f"Total: {filtered_df['doctor_count'].sum():,}"
        )
    
    with col3:
        leadership_count = filtered_df['is_leadership'].sum()
        st.metric(
            "Leadership",
            f"{leadership_count:,}",
            delta=f"{(leadership_count/len(filtered_df)*100):.0f}%" if len(filtered_df) > 0 else "0%"
        )
    
    with col4:
        phone_count = filtered_df['has_phone'].sum()
        st.metric(
            "With Phone",
            f"{phone_count:,}",
            delta=f"{(phone_count/len(filtered_df)*100):.0f}%" if len(filtered_df) > 0 else "0%"
        )
    
    with col5:
        email_count = filtered_df['has_email'].sum()
        st.metric(
            "With Email",
            f"{email_count:,}",
            delta=f"{(email_count/len(filtered_df)*100):.0f}%" if len(filtered_df) > 0 else "0%"
        )
    
    with col6:
        enterprise_count = len(filtered_df[filtered_df['doctor_count'] >= 50])
        st.metric(
            "Enterprise",
            f"{enterprise_count:,}",
            delta="50+ doctors"
        )
    
    # Main content tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🎯 High-Value Targets",
        "📊 Organization Analysis", 
        "🗺️ Territory Overview",
        "📋 Full Lead List",
        "📞 Contact Export"
    ])
    
    with tab1:
        st.header("High-Value Sales Targets")
        st.markdown("Organizations with complete contact information and highest sales potential")

        # Group by organization and get aggregated info
        org_groups = filtered_df.groupby('agreed_upon_name').agg({
            'lead_score': 'first',
            'doctor_count': 'first',
            'org_size_category': 'first',
            'has_email': 'max',
            'has_phone': 'max',
            'state_clean': 'first',
            'city_clean': 'first',
            'phone_clean': 'first',
            'email': 'first',
            'contact_full_name': 'first',
            'Authorized Official Title or Position': 'first',
            'practice_address': 'first',
            'mailing_address': 'first',
            'full_address': 'first',
            'affiliation_address': 'first',
            'Classification_1': 'first',
            'Is Sole Proprietor': 'first',
            'NPI': 'first'
        }).reset_index()

        # Sort by lead score and doctor count
        org_groups = org_groups.sort_values(['lead_score', 'doctor_count'], ascending=False)

        # Create two columns for lead cards
        col1, col2 = st.columns(2)

        for idx, (_, lead) in enumerate(org_groups.iterrows()):
            with col1 if idx % 2 == 0 else col2:
                score_color = "🟢" if lead['lead_score'] >= 10 else "🟡" if lead['lead_score'] >= 7 else "🔵"
                email_icon = "📧" if lead['has_email'] else ""
                phone_icon = "📱" if lead['has_phone'] else ""
                
                with st.expander(f"{score_color} **{lead['agreed_upon_name'][:50]}** (Score: {lead['lead_score']}/13 | {lead['doctor_count']} doctors) {email_icon}{phone_icon}"):
                    # Organization info
                    st.markdown("### 🏥 Organization Details")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write(f"**Doctor Count:** {lead['doctor_count']} physicians")
                        st.write(f"**Category:** {lead['org_size_category']}")
                        st.write(f"**Specialization:** {lead['Classification_1']}")
                    with col_b:
                        st.write(f"**Location:** {lead['city_clean']}, {lead['state_clean']}")
                        st.write(f"**Sole Proprietor:** {'Yes' if lead['Is Sole Proprietor'] == 'Y' else 'No'}")
                        st.write(f"**NPI:** {lead['NPI']}")
                    
                    # Contact info
                    st.markdown("### 👤 Decision Maker Contact")
                    if lead['contact_full_name']:
                        col_c, col_d = st.columns(2)
                        with col_c:
                            st.write(f"**Name:** {lead['contact_full_name']}")
                            st.write(f"**Title:** {lead['Authorized Official Title or Position']}")
                        with col_d:
                            if lead['has_phone']:
                                st.write(f"**📞 Phone:** {format_phone(lead['phone_clean'])}")
                            else:
                                st.write("**📞 Phone:** Not available")
                            
                            if lead['has_email']:
                                st.write(f"**📧 Email:** {lead['email']}")
                            else:
                                st.write("**📧 Email:** Not available")
                    
                    # Address information
                    st.markdown("### 📍 Address Information")
                    
                    # Practice address
                    if pd.notna(lead['practice_address']) and lead['practice_address']:
                        st.write("**Practice Location:**")
                        st.write(f"  {format_address(lead['practice_address'])}")
                    
                    # Mailing address
                    if pd.notna(lead['mailing_address']) and lead['mailing_address']:
                        st.write("**Mailing Address:**")
                        st.write(f"  {format_address(lead['mailing_address'])}")
                    
                    # Full address group if different
                    if pd.notna(lead['full_address']) and lead['full_address']:
                        if '|' in lead['full_address']:
                            st.write("**All Locations:**")
                            for addr in lead['full_address'].split('|'):
                                st.write(f"  • {addr.strip()}")

                    # Show all members/providers in this organization
                    org_members = filtered_df[filtered_df['agreed_upon_name'] == lead['agreed_upon_name']]
                    if len(org_members) > 0:
                        st.markdown("### 👥 Organization Members")

                        # Show individual providers
                        providers = org_members[org_members['is_individual_provider']]['provider_full_name'].unique()
                        providers = [p for p in providers if p]  # Filter out empty names

                        if providers:
                            st.write(f"**Providers ({len(providers)}):**")
                            # Show all providers with contact info where available
                            for provider_name in providers[:20]:
                                # Get the row for this provider
                                provider_rows = org_members[org_members['provider_full_name'] == provider_name]
                                if not provider_rows.empty:
                                    provider_row = provider_rows.iloc[0]
                                    phone = provider_row.get('phone_clean', '')
                                    email = provider_row.get('email', '')

                                    provider_info = f"  • {provider_name}"
                                    if phone and phone != 'nan' and len(str(phone)) > 5:
                                        provider_info += f" | 📞 {format_phone(str(phone))}"
                                    if email and email != '':
                                        provider_info += f" | 📧 {email}"

                                    st.write(provider_info)
                                else:
                                    st.write(f"  • {provider_name}")
                            if len(providers) > 20:
                                st.write(f"  _...and {len(providers) - 20} more providers_")

                        # Show other decision makers/contacts
                        other_contacts = org_members[~org_members['contact_full_name'].isin(['', lead['contact_full_name']])]['contact_full_name'].unique()
                        other_contacts = [c for c in other_contacts if c]  # Filter out empty names

                        if other_contacts:
                            st.write(f"**Other Contacts ({len(other_contacts)}):**")
                            for contact in other_contacts[:10]:
                                contact_row = org_members[org_members['contact_full_name'] == contact].iloc[0]
                                title = contact_row.get('Authorized Official Title or Position', '')
                                phone = contact_row.get('phone_clean', '')
                                email = contact_row.get('email', '')

                                contact_info = f"  • {contact}"
                                if title and title != 'nan':
                                    contact_info += f" - {title}"
                                if phone and phone != 'nan' and len(str(phone)) > 5:
                                    contact_info += f" | 📞 {format_phone(str(phone))}"
                                if email and email != '':
                                    contact_info += f" | 📧 {email}"

                                st.write(contact_info)
                            if len(other_contacts) > 10:
                                st.write(f"  _...and {len(other_contacts) - 10} more contacts_")
    
    with tab2:
        st.header("Organization Size Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Organization size distribution
            size_dist = filtered_df.groupby('org_size_category')['doctor_count'].agg(['count', 'sum']).reset_index()
            size_dist.columns = ['Category', 'Number of Organizations', 'Total Doctors']
            
            fig = px.bar(
                size_dist,
                x='Category',
                y='Number of Organizations',
                title="Organizations by Size Category",
                text='Number of Organizations',
                color='Total Doctors',
                color_continuous_scale='Blues'
            )
            fig.update_traces(texttemplate='%{text}', textposition='outside')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Top organizations by doctor count
            st.subheader("Largest Healthcare Organizations")
            top_orgs = filtered_df.nlargest(10, 'doctor_count')[['agreed_upon_name', 'doctor_count', 'state_clean', 'has_email', 'has_phone']]
            top_orgs['Contact Status'] = top_orgs.apply(lambda x: 
                '📧📱' if x['has_email'] and x['has_phone'] else 
                '📧' if x['has_email'] else 
                '📱' if x['has_phone'] else '❌', axis=1)
            display_orgs = top_orgs[['agreed_upon_name', 'doctor_count', 'state_clean', 'Contact Status']].copy()
            display_orgs.columns = ['Organization', 'Doctors', 'State', 'Contact']
            st.dataframe(display_orgs, hide_index=True, use_container_width=True)
        
        # Contact availability analysis
        st.subheader("Contact Information Availability")
        col3, col4, col5 = st.columns(3)
        
        with col3:
            contact_stats = pd.DataFrame({
                'Type': ['Phone Only', 'Email Only', 'Both', 'Neither'],
                'Count': [
                    len(filtered_df[filtered_df['has_phone'] & ~filtered_df['has_email']]),
                    len(filtered_df[~filtered_df['has_phone'] & filtered_df['has_email']]),
                    len(filtered_df[filtered_df['has_phone'] & filtered_df['has_email']]),
                    len(filtered_df[~filtered_df['has_phone'] & ~filtered_df['has_email']])
                ]
            })
            fig = px.pie(contact_stats, values='Count', names='Type', title="Contact Information Coverage")
            st.plotly_chart(fig, use_container_width=True)
        
        with col4:
            # Leadership distribution
            leadership_df = filtered_df[filtered_df['is_leadership']]
            title_counts = leadership_df['Authorized Official Title or Position'].value_counts().head(10)
            
            title_df = pd.DataFrame({
                'Title': title_counts.index,
                'Count': title_counts.values
            })
            
            fig = px.bar(
                title_df,
                x='Count',
                y='Title',
                orientation='h',
                title="Top 10 Leadership Titles"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col5:
            # Email domains analysis for those with emails
            email_df = filtered_df[filtered_df['has_email']].copy()
            if len(email_df) > 0:
                email_df['domain'] = email_df['email'].str.split('@').str[1]
                domain_counts = email_df['domain'].value_counts().head(10)
                
                st.subheader("Top Email Domains")
                for domain, count in domain_counts.items():
                    st.write(f"**{domain}:** {count}")
    
    with tab3:
        st.header("Territory Analysis")
        
        # State-level metrics
        state_metrics = filtered_df.groupby('state_clean').agg({
            'doctor_count': ['sum', 'mean'],
            'agreed_upon_name': 'count',
            'is_leadership': 'sum',
            'has_phone': 'sum',
            'has_email': 'sum'
        }).round(1)
        
        state_metrics.columns = ['Total Doctors', 'Avg Doctors/Org', 'Organizations', 'Leadership Contacts', 'With Phone', 'With Email']
        state_metrics = state_metrics.sort_values('Total Doctors', ascending=False).head(20)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            fig = px.bar(
                state_metrics.reset_index(),
                x='state_clean',
                y='Total Doctors',
                title="Total Doctors by State (Top 20)",
                text='Total Doctors',
                color='Organizations',
                color_continuous_scale='Viridis'
            )
            fig.update_traces(texttemplate='%{text}', textposition='outside')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Top 10 States Summary")
            st.dataframe(
                state_metrics.head(10),
                use_container_width=True
            )
        
        # City analysis
        st.subheader("Top Cities by Total Doctors")
        city_metrics = filtered_df.groupby('city_clean').agg({
            'doctor_count': 'sum',
            'agreed_upon_name': 'count',
            'has_phone': 'sum',
            'has_email': 'sum'
        }).sort_values('doctor_count', ascending=False).head(15)
        city_metrics.columns = ['Total Doctors', 'Organizations', 'With Phone', 'With Email']
        
        fig = px.bar(
            city_metrics.reset_index(),
            x='city_clean',
            y='Total Doctors',
            title="Top 15 Cities by Healthcare Presence",
            text='Total Doctors',
            hover_data=['Organizations', 'With Phone', 'With Email']
        )
        fig.update_traces(texttemplate='%{text}', textposition='outside')
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.header("Complete Lead List")
        st.markdown("Search and browse all filtered leads with complete contact information")
        
        # Prepare display dataframe
        display_cols = [
            'lead_score', 'agreed_upon_name', 'doctor_count', 'org_size_category',
            'contact_full_name', 'Authorized Official Title or Position',
            'phone_clean', 'email', 'city_clean', 'state_clean', 
            'mailing_address', 'Classification_1'
        ]
        
        display_df = filtered_df[display_cols].copy()
        display_df.columns = [
            'Score', 'Organization', 'Doctors', 'Size Category',
            'Contact Name', 'Title', 'Phone', 'Email', 'City', 'State',
            'Address', 'Specialization'
        ]
        
        # Add search
        search_term = st.text_input("🔍 Search organizations, contacts, cities, or emails:")
        if search_term:
            mask = display_df.apply(lambda x: x.astype(str).str.contains(search_term, case=False).any(), axis=1)
            display_df = display_df[mask]
        
        # Contact status filter
        col1, col2, col3 = st.columns(3)
        with col1:
            show_with_email = st.checkbox("Show only with email", value=False)
        with col2:
            show_with_phone = st.checkbox("Show only with phone", value=False)
        with col3:
            show_with_both = st.checkbox("Show only with both email & phone", value=False)
        
        if show_with_both:
            display_df = display_df[(display_df['Email'] != '') & (display_df['Phone'] != 'nan')]
        elif show_with_email:
            display_df = display_df[display_df['Email'] != '']
        elif show_with_phone:
            display_df = display_df[display_df['Phone'] != 'nan']
        
        st.dataframe(
            display_df,
            use_container_width=True,
            height=600,
            column_config={
                "Score": st.column_config.NumberColumn("Score", format="%d ⭐"),
                "Doctors": st.column_config.NumberColumn("Doctors", format="%d"),
                "Phone": st.column_config.TextColumn("Phone", width="medium"),
                "Email": st.column_config.TextColumn("Email", width="large"),
                "Address": st.column_config.TextColumn("Address", width="large"),
            }
        )

        st.info(f"Showing all {len(display_df):,} filtered leads")
    
    with tab5:
        st.header("Export Contact List")
        st.markdown("Download filtered leads with complete contact information for CRM import")
        
        # Prepare export data with all contact fields
        export_df = filtered_df[[
            'agreed_upon_name', 'doctor_count', 'org_size_category',
            'contact_full_name', 'Authorized Official Title or Position',
            'phone_clean', 'email',
            'mailing_address', 'practice_address', 'full_address',
            'city_clean', 'state_clean', 'mailing_city', 'mailing_state',
            'Classification_1', 'lead_score', 'NPI',
            'Is Sole Proprietor', 'is_leadership', 'has_phone', 'has_email'
        ]].copy()
        
        export_df.columns = [
            'Organization_Name', 'Doctor_Count', 'Size_Category',
            'Contact_Name', 'Contact_Title', 'Phone', 'Email',
            'Mailing_Address', 'Practice_Address', 'All_Addresses',
            'City', 'State', 'Mailing_City', 'Mailing_State',
            'Specialization', 'Lead_Score', 'NPI',
            'Is_Sole_Proprietor', 'Is_Leadership', 'Has_Phone', 'Has_Email'
        ]
        
        # Show preview
        st.subheader("Export Preview")
        preview_cols = ['Organization_Name', 'Contact_Name', 'Phone', 'Email', 'City', 'State', 'Lead_Score']
        st.dataframe(export_df[preview_cols].head(10), use_container_width=True)
        
        # Export statistics
        st.subheader("Export Statistics")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Records", f"{len(export_df):,}")
        with col2:
            st.metric("With Email", f"{export_df['Has_Email'].sum():,}")
        with col3:
            st.metric("With Phone", f"{export_df['Has_Phone'].sum():,}")
        with col4:
            st.metric("Leadership", f"{export_df['Is_Leadership'].sum():,}")
        
        # Export options
        st.subheader("Download Options")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # High-value leads with complete contact info
            complete_contact_df = export_df[(export_df['Has_Email']) & (export_df['Has_Phone']) & (export_df['Lead_Score'] >= 8)]
            csv_complete = complete_contact_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"⭐ Premium Leads ({len(complete_contact_df):,})",
                data=csv_complete,
                file_name=f'premium_leads_complete_contact_{datetime.now().strftime("%Y%m%d")}.csv',
                mime='text/csv',
                help="High-score leads with both email and phone"
            )
        
        with col2:
            # All filtered leads
            csv_all = export_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📥 All Filtered Leads ({len(export_df):,})",
                data=csv_all,
                file_name=f'all_filtered_leads_{datetime.now().strftime("%Y%m%d")}.csv',
                mime='text/csv'
            )
        
        with col3:
            # Email campaign list
            email_list_df = export_df[export_df['Has_Email']][['Organization_Name', 'Contact_Name', 'Contact_Title', 'Email', 'Doctor_Count', 'City', 'State']]
            csv_email = email_list_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📧 Email Campaign List ({len(email_list_df):,})",
                data=csv_email,
                file_name=f'email_campaign_list_{datetime.now().strftime("%Y%m%d")}.csv',
                mime='text/csv',
                help="Contacts with email addresses for email campaigns"
            )

if __name__ == "__main__":
    main()