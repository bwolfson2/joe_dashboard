import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Healthcare Sales Lead Dashboard - CMS DAC Data",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better formatting
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_and_process_data():
    """Load and process the CMS DAC healthcare provider data from parquet chunks"""

    # Load from 3 parquet files (70% smaller than CSV, faster loading)
    parquet_files = [f"DAC_parquet_{i}.parquet" for i in range(1, 4)]

    dfs = []
    missing_files = []

    for parquet_file in parquet_files:
        try:
            chunk_df = pd.read_parquet(parquet_file)
            dfs.append(chunk_df)
        except FileNotFoundError:
            missing_files.append(parquet_file)

    if missing_files:
        st.error(f"Missing parquet files: {', '.join(missing_files)}")
        st.info("Run the split script to create parquet chunks")
        return pd.DataFrame()

    if not dfs:
        st.error("No data files found!")
        return pd.DataFrame()

    # Combine all chunks
    df = pd.concat(dfs, ignore_index=True)

    # Clean and process key fields
    df["num_org_mem"] = (
        pd.to_numeric(df["num_org_mem"], errors="coerce").fillna(0).astype(int)
    )

    # Clean phone numbers (they're loaded as floats in scientific notation)
    def clean_phone(phone):
        if pd.isna(phone):
            return ""
        # Convert float to int to string to avoid scientific notation
        phone_str = str(int(phone)) if isinstance(phone, float) else str(phone)
        # Remove any non-digits
        phone_clean = ''.join(filter(str.isdigit, phone_str))
        return phone_clean if len(phone_clean) == 10 else ""

    df["phone_clean"] = df["Telephone Number"].apply(clean_phone)
    df["has_phone"] = df["phone_clean"].str.len() == 10

    # For now, no emails in this dataset - we'll need the agent to find them
    df["email"] = ""
    df["has_email"] = False

    # Create provider full name
    df["provider_full_name"] = (
        df["Provider First Name"].fillna("")
        + " "
        + df["Provider Last Name"].fillna("")
    ).str.strip()

    # Create full address from components
    df["full_address"] = (
        df["adr_ln_1"].astype(str).replace("nan", "")
        + ", "
        + df["adr_ln_2"].astype(str).replace("nan", "")
        + ", "
        + df["City/Town"].astype(str).replace("nan", "")
        + ", "
        + df["State"].astype(str).replace("nan", "")
        + " "
        + df["ZIP Code"].astype(str).str.replace(".0", "").replace("nan", "")
    ).str.replace(", , ", ", ").str.replace(", ,", ",").str.strip(", ")

    # Clean states and cities
    df["state_clean"] = df["State"].astype(str).replace("nan", "Unknown")
    df["city_clean"] = df["City/Town"].astype(str).replace("nan", "Unknown")

    # Clean facility names
    df["Facility Name"] = df["Facility Name"].astype(str).replace("nan", "Unknown Organization")

    # Clean specialties
    df["pri_spec"] = df["pri_spec"].astype(str).replace("nan", "Unknown")
    df["sec_spec_all"] = df["sec_spec_all"].astype(str).replace("nan", "")

    # Credentials and education
    df["Cred"] = df["Cred"].astype(str).str.strip().replace("nan", "")
    df["Med_sch"] = df["Med_sch"].astype(str).replace("nan", "Unknown")
    df["Grd_yr"] = pd.to_numeric(df["Grd_yr"], errors="coerce")

    # Calculate organization size category
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

    # Lead scoring based on sales criteria
    df["lead_score"] = 0

    # Score based on organization member count
    df.loc[df["num_org_mem"] >= 1000, "lead_score"] += 10
    df.loc[(df["num_org_mem"] >= 300) & (df["num_org_mem"] < 1000), "lead_score"] += 8
    df.loc[(df["num_org_mem"] >= 100) & (df["num_org_mem"] < 300), "lead_score"] += 6
    df.loc[(df["num_org_mem"] >= 50) & (df["num_org_mem"] < 100), "lead_score"] += 4
    df.loc[(df["num_org_mem"] >= 10) & (df["num_org_mem"] < 50), "lead_score"] += 2
    df.loc[(df["num_org_mem"] > 0) & (df["num_org_mem"] < 10), "lead_score"] += 1

    # Score for having phone number
    df.loc[df["has_phone"], "lead_score"] += 2

    # Score for group assignment (more valuable for sales)
    df.loc[df["grp_assgn"] == "Y", "lead_score"] += 1

    # Score for telehealth capability
    df.loc[df["Telehlth"].notna() & (df["Telehlth"].str.strip() != ""), "lead_score"] += 1

    return df


@st.cache_data
def filter_dataframe(
    df,
    selected_sizes,  # Kept for backwards compatibility but not used
    selected_states,
    selected_specialties,
    only_with_phone,
    min_members,
    max_members,
    only_group_practices,
    only_telehealth,
):
    """Cache filtered results for better performance"""
    filtered_df = df.copy()

    # Filter by member count first (most selective)
    filtered_df = filtered_df[
        (filtered_df["num_org_mem"] >= min_members)
        & (filtered_df["num_org_mem"] <= max_members)
    ]

    if selected_states:
        filtered_df = filtered_df[filtered_df["state_clean"].isin(selected_states)]
    if selected_specialties:
        filtered_df = filtered_df[filtered_df["pri_spec"].isin(selected_specialties)]
    if only_with_phone:
        filtered_df = filtered_df[filtered_df["has_phone"]]
    if only_group_practices:
        filtered_df = filtered_df[filtered_df["grp_assgn"] == "Y"]
    if only_telehealth:
        filtered_df = filtered_df[filtered_df["Telehlth"].notna() & (filtered_df["Telehlth"].str.strip() != "")]

    # Sort by lead score and organization size
    filtered_df = filtered_df.sort_values(
        ["lead_score", "num_org_mem"], ascending=False
    )

    return filtered_df


def format_phone(phone):
    """Format phone number for display"""
    phone = str(phone).replace(".0", "").strip()
    if len(phone) == 10:
        return f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
    return phone


def format_address(address):
    """Format address for display"""
    if pd.isna(address) or address == "":
        return "Not available"
    return address.strip()


def main():
    st.title("🏥 Healthcare Sales Lead Dashboard - CMS DAC Data")
    st.markdown(
        "**2.8M+ Provider Records** | Phone Numbers | Organization Membership | Specialties"
    )

    # Load data
    with st.spinner("Loading CMS DAC healthcare provider data..."):
        df = load_and_process_data()

    if df.empty:
        st.error("No data loaded. Please check the data file.")
        return

    # Sidebar filters
    with st.sidebar:
        st.header("🎯 Lead Filters")

        # Member count range filter
        st.subheader("Organization Member Count")
        max_member_count = int(df["num_org_mem"].max())
        col_min, col_max = st.columns(2)
        with col_min:
            min_members = st.number_input(
                "Min members:", min_value=0, max_value=max_member_count, value=2, step=1
            )
        with col_max:
            max_members = st.number_input(
                "Max members:",
                min_value=0,
                max_value=max_member_count,
                value=50,
                step=10,
            )

        # State filter
        st.subheader("Geographic Filter")
        states = sorted([s for s in df["state_clean"].unique() if s != "Unknown"])
        selected_states = st.multiselect("Select states:", states, default=[])

        # Specialty filter
        st.subheader("Specialty Filter")
        specialties = df["pri_spec"].value_counts().head(30).index.tolist()
        selected_specialties = st.multiselect(
            "Select specialties (top 30):",
            specialties,
            default=[]
        )

        # Contact filters
        st.subheader("Contact Requirements")
        only_with_phone = st.checkbox("Must have phone number", value=True)
        only_group_practices = st.checkbox("Group practices only", value=False)
        only_telehealth = st.checkbox("Offers telehealth", value=False)

        # Results per page
        st.subheader("Display Options")
        items_per_page = st.selectbox(
            "Results per page:",
            options=[25, 50, 100, 200],
            index=1  # Default to 50
        )

        # Apply filters using cached function
        filtered_df = filter_dataframe(
            df,
            None,  # No size categories
            tuple(selected_states) if selected_states else None,
            tuple(selected_specialties) if selected_specialties else None,
            only_with_phone,
            min_members,
            max_members,
            only_group_practices,
            only_telehealth,
        )

    # Key metrics
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric(
            "Total Records",
            f"{len(filtered_df):,}",
            delta=f"{len(filtered_df[filtered_df['lead_score'] >= 8]):,} high-value",
        )

    with col2:
        avg_members = filtered_df["num_org_mem"].mean()
        st.metric(
            "Avg. Members",
            f"{avg_members:.1f}",
            delta=f"Total: {filtered_df['num_org_mem'].sum():,}",
        )

    with col3:
        unique_facilities = filtered_df["Facility Name"].nunique()
        st.metric(
            "Unique Facilities",
            f"{unique_facilities:,}",
        )

    with col4:
        phone_count = filtered_df["has_phone"].sum()
        st.metric(
            "With Phone",
            f"{phone_count:,}",
            delta=(
                f"{(phone_count/len(filtered_df)*100):.0f}%"
                if len(filtered_df) > 0
                else "0%"
            ),
        )

    with col5:
        group_practices = len(filtered_df[filtered_df["grp_assgn"] == "Y"])
        st.metric(
            "Group Practices",
            f"{group_practices:,}",
            delta=(
                f"{(group_practices/len(filtered_df)*100):.0f}%"
                if len(filtered_df) > 0
                else "0%"
            ),
        )

    with col6:
        health_systems = len(filtered_df[filtered_df["num_org_mem"] >= 1000])
        st.metric("Health Systems", f"{health_systems:,}", delta="1000+ members")

    # Main content tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "🎯 Top Organizations",
            "👥 Provider Details",
            "📊 Analytics",
            "🗺️ Territory Overview",
            "📞 Contact Export",
        ]
    )

    with tab1:
        st.header("Top Healthcare Organizations by Size")
        st.markdown(
            "Organizations ranked by member count with complete contact information"
        )

        # Group by facility and organization
        org_groups = (
            filtered_df.groupby(["Facility Name", "org_pac_id"])
            .agg(
                {
                    "lead_score": "max",
                    "num_org_mem": "first",
                    "org_size_category": "first",
                    "has_phone": "max",
                    "state_clean": "first",
                    "city_clean": "first",
                    "phone_clean": "first",
                    "full_address": "first",
                    "pri_spec": lambda x: x.mode()[0] if not x.mode().empty else "Unknown",
                    "NPI": "count",  # Count of providers
                    "grp_assgn": "first",
                    "Telehlth": "first",
                }
            )
            .reset_index()
            .sort_values(["num_org_mem", "lead_score"], ascending=False)
        )

        org_groups.rename(columns={"NPI": "provider_count"}, inplace=True)

        # Add pagination
        total_orgs = len(org_groups)

        if total_orgs > items_per_page:
            total_pages = (total_orgs // items_per_page) + (1 if total_orgs % items_per_page > 0 else 0)

            col_page, col_info = st.columns([1, 2])
            with col_page:
                page = st.number_input(
                    f"Page:",
                    min_value=1,
                    max_value=total_pages,
                    value=1,
                    step=1,
                    key="org_page"
                )
            with col_info:
                start_idx = (page - 1) * items_per_page
                end_idx = min(start_idx + items_per_page, total_orgs)
                st.info(f"Showing {start_idx+1}-{end_idx} of {total_orgs:,} organizations (Page {page}/{total_pages})")

            org_groups_page = org_groups.iloc[start_idx:end_idx]
        else:
            org_groups_page = org_groups
            st.info(f"Showing all {total_orgs:,} organizations")

        # Create two columns for lead cards
        col1, col2 = st.columns(2)

        for idx, (_, lead) in enumerate(org_groups_page.iterrows()):
            with col1 if idx % 2 == 0 else col2:
                score_color = (
                    "🟢"
                    if lead["lead_score"] >= 10
                    else "🟡" if lead["lead_score"] >= 6 else "🔵"
                )
                phone_icon = "📱" if lead["has_phone"] else "❌"
                group_icon = "👥" if lead["grp_assgn"] == "Y" else ""
                telehealth_icon = "💻" if pd.notna(lead["Telehlth"]) and lead["Telehlth"] != "" else ""

                with st.expander(
                    f"{score_color} **{lead['Facility Name'][:50]}** ({lead['num_org_mem']} members | {lead['provider_count']} providers) {phone_icon}{group_icon}{telehealth_icon}",
                    expanded=False,
                ):
                    # Organization info
                    st.markdown("### 🏥 Organization Details")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write(f"**Organization Members:** {lead['num_org_mem']}")
                        st.write(f"**Providers in Dataset:** {lead['provider_count']}")
                        st.write(f"**Category:** {lead['org_size_category']}")
                        st.write(f"**Primary Specialty:** {lead['pri_spec']}")
                    with col_b:
                        st.write(
                            f"**Location:** {lead['city_clean']}, {lead['state_clean']}"
                        )
                        st.write(f"**Org PAC ID:** {lead['org_pac_id']}")
                        st.write(
                            f"**Group Practice:** {'Yes' if lead['grp_assgn'] == 'Y' else 'No'}"
                        )
                        st.write(f"**Lead Score:** {lead['lead_score']}/14")

                    # Contact info
                    st.markdown("### 📞 Contact Information")
                    if lead["has_phone"]:
                        st.write(f"**Phone:** {format_phone(lead['phone_clean'])}")
                    else:
                        st.write("**Phone:** Not available")

                    st.write("**Email:** 🤖 Use Email Discovery Agent (see below)")

                    # Address information
                    st.markdown("### 📍 Address")
                    st.write(format_address(lead["full_address"]))

                    # Telehealth info
                    if pd.notna(lead["Telehlth"]) and lead["Telehlth"] != "":
                        st.markdown("### 💻 Telehealth")
                        st.write(f"{lead['Telehlth']}")

                    # Show providers at this organization
                    org_providers = filtered_df[
                        (filtered_df["Facility Name"] == lead["Facility Name"])
                        & (filtered_df["org_pac_id"] == lead["org_pac_id"])
                    ].head(20)  # Limit to first 20 for performance

                    if len(org_providers) > 0:
                        st.markdown("### 👨‍⚕️ Sample Providers")
                        for _, provider in org_providers.iterrows():
                            provider_info = f"• **{provider['provider_full_name']}**"
                            if provider["Cred"]:
                                provider_info += f", {provider['Cred']}"
                            provider_info += f" - {provider['pri_spec']}"
                            if provider["sec_spec_all"]:
                                provider_info += f" (Also: {provider['sec_spec_all'][:50]})"
                            st.write(provider_info)

                        if lead["provider_count"] > 20:
                            st.write(f"_...and {lead['provider_count'] - 20} more providers_")

    with tab2:
        st.header("Individual Provider Details")
        st.markdown("Search and explore individual healthcare providers")

        # Search functionality
        search_term = st.text_input(
            "🔍 Search by provider name, facility, specialty, or city:"
        )

        search_df = filtered_df.copy()
        if search_term:
            mask = (
                search_df["provider_full_name"].str.contains(search_term, case=False, na=False)
                | search_df["Facility Name"].str.contains(search_term, case=False, na=False)
                | search_df["pri_spec"].str.contains(search_term, case=False, na=False)
                | search_df["city_clean"].str.contains(search_term, case=False, na=False)
            )
            search_df = search_df[mask]

        # Display provider table
        display_cols = [
            "provider_full_name",
            "Cred",
            "pri_spec",
            "Facility Name",
            "num_org_mem",
            "city_clean",
            "state_clean",
            "phone_clean",
            "Med_sch",
            "Grd_yr",
        ]

        display_df = search_df[display_cols].copy()
        display_df.columns = [
            "Provider Name",
            "Credentials",
            "Specialty",
            "Facility",
            "Org Members",
            "City",
            "State",
            "Phone",
            "Medical School",
            "Graduation Year",
        ]

        # Add pagination
        providers_per_page = 100
        total_items = len(display_df)

        if total_items > providers_per_page:
            total_pages = (total_items // providers_per_page) + (1 if total_items % providers_per_page > 0 else 0)

            col_page, col_info = st.columns([1, 2])
            with col_page:
                page_num = st.number_input(
                    f"Page:",
                    min_value=1,
                    max_value=total_pages,
                    value=1,
                    step=1,
                    key="provider_list_page",
                )
            with col_info:
                start_idx = (page_num - 1) * providers_per_page
                end_idx = min(start_idx + providers_per_page, total_items)
                st.info(f"Showing {start_idx+1}-{end_idx} of {total_items:,} providers (Page {page_num}/{total_pages})")

            display_page = display_df.iloc[start_idx:end_idx]
        else:
            display_page = display_df
            st.info(f"Showing all {len(display_df):,} providers")

        st.dataframe(
            display_page,
            use_container_width=True,
            height=600,
            column_config={
                "Org Members": st.column_config.NumberColumn("Org Members", format="%d"),
                "Graduation Year": st.column_config.NumberColumn("Grad Year", format="%d"),
            },
        )

    with tab3:
        st.header("Organization & Provider Analytics")

        col1, col2 = st.columns(2)

        with col1:
            # Organization size distribution
            size_dist = (
                filtered_df.groupby("org_size_category")
                .agg({"num_org_mem": ["count", "sum"]})
                .reset_index()
            )
            size_dist.columns = ["Category", "Provider Count", "Total Members"]

            fig = px.bar(
                size_dist,
                x="Category",
                y="Provider Count",
                title="Providers by Organization Size Category",
                text="Provider Count",
                color="Total Members",
                color_continuous_scale="Blues",
            )
            fig.update_traces(texttemplate="%{text}", textposition="outside")
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Top specialties
            specialty_counts = filtered_df["pri_spec"].value_counts().head(15)
            specialty_df = pd.DataFrame({
                'Specialty': specialty_counts.index,
                'Count': specialty_counts.values
            })
            fig = px.bar(
                specialty_df,
                x="Count",
                y="Specialty",
                orientation="h",
                title="Top 15 Specialties",
            )
            st.plotly_chart(fig, use_container_width=True)

        # Top facilities by member count
        st.subheader("Largest Healthcare Organizations")
        top_facilities = (
            filtered_df.groupby("Facility Name")
            .agg(
                {
                    "num_org_mem": "first",
                    "NPI": "count",
                    "state_clean": "first",
                    "city_clean": "first",
                    "has_phone": "max",
                }
            )
            .reset_index()
            .sort_values("num_org_mem", ascending=False)
            .head(20)
        )
        top_facilities.columns = [
            "Facility",
            "Members",
            "Providers",
            "State",
            "City",
            "Has Phone",
        ]
        top_facilities["Contact"] = top_facilities["Has Phone"].apply(
            lambda x: "📱" if x else "❌"
        )
        display_facilities = top_facilities[["Facility", "Members", "Providers", "City", "State", "Contact"]]
        st.dataframe(display_facilities, hide_index=True, use_container_width=True, height=400)

        # Gender distribution
        col3, col4 = st.columns(2)
        with col3:
            gender_dist = filtered_df["gndr"].value_counts()
            fig = px.pie(
                values=gender_dist.values,
                names=gender_dist.index,
                title="Provider Gender Distribution",
            )
            st.plotly_chart(fig, use_container_width=True)

        with col4:
            # Graduation year distribution (for recent grads)
            grad_years = filtered_df[filtered_df["Grd_yr"] >= 2000]["Grd_yr"].value_counts().sort_index()
            grad_years_df = pd.DataFrame({
                'Year': grad_years.index,
                'Count': grad_years.values
            })
            fig = px.line(
                grad_years_df,
                x="Year",
                y="Count",
                title="Provider Graduation Years (2000+)",
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab4:
        st.header("Territory Analysis")

        # State-level metrics
        state_metrics = (
            filtered_df.groupby("state_clean")
            .agg(
                {
                    "num_org_mem": ["sum", "mean"],
                    "NPI": "count",
                    "Facility Name": "nunique",
                    "has_phone": "sum",
                }
            )
            .round(1)
        )

        state_metrics.columns = [
            "Total Members",
            "Avg Members/Provider",
            "Providers",
            "Unique Facilities",
            "With Phone",
        ]
        state_metrics = state_metrics.sort_values(
            "Total Members", ascending=False
        ).head(25)

        col1, col2 = st.columns([2, 1])

        with col1:
            fig = px.bar(
                state_metrics.reset_index(),
                x="state_clean",
                y="Total Members",
                title="Total Organization Members by State (Top 25)",
                text="Total Members",
                color="Providers",
                color_continuous_scale="Viridis",
            )
            fig.update_traces(texttemplate="%{text}", textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Top 10 States")
            st.dataframe(state_metrics.head(10), use_container_width=True)

        # City analysis
        st.subheader("Top Cities by Provider Count")
        city_metrics = (
            filtered_df.groupby(["city_clean", "state_clean"])
            .agg(
                {
                    "NPI": "count",
                    "Facility Name": "nunique",
                    "num_org_mem": "sum",
                    "has_phone": "sum",
                }
            )
            .sort_values("NPI", ascending=False)
            .head(20)
        )
        city_metrics.columns = [
            "Providers",
            "Facilities",
            "Total Members",
            "With Phone",
        ]
        city_metrics = city_metrics.reset_index()
        city_metrics["Location"] = city_metrics["city_clean"] + ", " + city_metrics["state_clean"]

        fig = px.bar(
            city_metrics,
            x="Location",
            y="Providers",
            title="Top 20 Cities by Provider Count",
            text="Providers",
            hover_data=["Facilities", "Total Members", "With Phone"],
        )
        fig.update_traces(texttemplate="%{text}", textposition="outside")
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)

    with tab5:
        st.header("Export Contact List")
        st.markdown(
            "Download filtered data for outreach. **Note:** Emails not included in CMS data - use Email Discovery Agent below."
        )

        # Prepare export data
        export_df = filtered_df[
            [
                "Facility Name",
                "org_pac_id",
                "num_org_mem",
                "org_size_category",
                "provider_full_name",
                "Cred",
                "pri_spec",
                "sec_spec_all",
                "phone_clean",
                "full_address",
                "city_clean",
                "state_clean",
                "ZIP Code",
                "grp_assgn",
                "ind_assgn",
                "lead_score",
                "NPI",
                "Ind_PAC_ID",
                "gndr",
                "Med_sch",
                "Grd_yr",
                "Telehlth",
            ]
        ].copy()

        export_df.columns = [
            "Facility_Name",
            "Organization_PAC_ID",
            "Organization_Members",
            "Size_Category",
            "Provider_Name",
            "Credentials",
            "Primary_Specialty",
            "Secondary_Specialties",
            "Phone",
            "Address",
            "City",
            "State",
            "ZIP",
            "Group_Assignment",
            "Individual_Assignment",
            "Lead_Score",
            "NPI",
            "Individual_PAC_ID",
            "Gender",
            "Medical_School",
            "Graduation_Year",
            "Telehealth",
        ]

        # Show preview
        st.subheader("Export Preview")
        preview_cols = [
            "Facility_Name",
            "Organization_Members",
            "Provider_Name",
            "Phone",
            "City",
            "State",
            "Lead_Score",
        ]
        st.dataframe(export_df[preview_cols].head(10), use_container_width=True)

        # Export statistics
        st.subheader("Export Statistics")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Records", f"{len(export_df):,}")
        with col2:
            unique_facilities = export_df["Facility_Name"].nunique()
            st.metric("Unique Facilities", f"{unique_facilities:,}")
        with col3:
            with_phone = len(export_df[export_df["Phone"] != ""])
            st.metric("With Phone", f"{with_phone:,}")
        with col4:
            high_value = len(export_df[export_df["Lead_Score"] >= 8])
            st.metric("High Value", f"{high_value:,}")

        # Export options
        st.subheader("Download Options")
        col1, col2, col3 = st.columns(3)

        with col1:
            # High-value leads
            high_value_df = export_df[export_df["Lead_Score"] >= 8]
            csv_high = high_value_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=f"⭐ High-Value Leads ({len(high_value_df):,})",
                data=csv_high,
                file_name=f'high_value_leads_{datetime.now().strftime("%Y%m%d")}.csv',
                mime="text/csv",
                help="Organizations with lead score >= 8",
            )

        with col2:
            # All filtered data
            csv_all = export_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=f"📥 All Filtered Data ({len(export_df):,})",
                data=csv_all,
                file_name=f'all_filtered_data_{datetime.now().strftime("%Y%m%d")}.csv',
                mime="text/csv",
            )

        with col3:
            # Large organizations only
            large_orgs_df = export_df[export_df["Organization_Members"] >= 100]
            csv_large = large_orgs_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=f"🏢 Large Organizations ({len(large_orgs_df):,})",
                data=csv_large,
                file_name=f'large_organizations_{datetime.now().strftime("%Y%m%d")}.csv',
                mime="text/csv",
                help="Organizations with 100+ members",
            )

        # Email Discovery Agent Section
        st.divider()
        st.subheader("🤖 Email Discovery Agent")
        st.markdown("""
        **Note:** The CMS DAC dataset does not include email addresses. To find emails for your leads,
        you'll need to use the Email Discovery Agent (see implementation details below).

        The agent will:
        1. Take facility names and addresses as input
        2. Search for organization websites
        3. Find contact pages and staff directories
        4. Extract email patterns and specific contact emails
        5. Return results in a structured format

        **See the `email_agent.py` file for the implementation.**
        """)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if "SessionInfo" in str(e):
            st.error("Session initialization error. Please refresh the page.")
            st.stop()
        else:
            raise e
