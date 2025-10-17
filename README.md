# Healthcare Sales Lead Dashboard

A powerful Streamlit dashboard for analyzing healthcare provider data from CMS (Centers for Medicare & Medicaid Services) to identify high-value sales leads.

## Features

### 📊 Dashboard
- **2.8M+ Provider Records** from CMS DAC (Doctor and Clinician) database
- **Organization Analysis** - Group providers by facility with member counts
- **Advanced Filtering** - By size, specialty, location, and more
- **Lead Scoring** - Intelligent scoring based on organization size, contact availability, and other factors
- **Territory Analysis** - Geographic distribution and market insights
- **Export Capabilities** - CSV exports for CRM integration

### 🤖 Email Discovery Agent
- **AI-Powered** - Uses GPT-4o-mini for intelligent email extraction
- **Web Search** - Serper API for finding organization websites and contact pages
- **Cost-Effective** - ~$0.50-1.00 per 100 organizations
- **Caching** - Avoids redundant searches and API calls
- **Batch Processing** - Process multiple organizations efficiently

## Data Source

The dashboard uses the **CMS DAC National Downloadable File**, which contains:
- Individual provider information (NPI, name, credentials, specialty)
- Organization affiliations (facility name, org PAC ID, member count)
- Practice locations (address, city, state, ZIP)
- Contact information (phone numbers)
- Medical education details
- Telehealth capabilities

**Original Data**: 2.8M records, 672MB CSV → 208MB Parquet (70% smaller!)
**Split into**: 3 Parquet files (~70MB each, git-friendly)
**Data URL**: https://data.cms.gov/provider-data/sites/default/files/resources/52c3f098d7e56028a298fd297cb0b38d_1757685921/DAC_NationalDownloadableFile.csv

## Setup

### Option 1: Docker (Recommended)

**Prerequisites**: Docker and Docker Compose installed

The chunked data files are included in the repository, so no download needed!

1. **Build and run with Docker Compose**:
```bash
docker-compose up --build
```

2. **Access the dashboard** at `http://localhost:8501`

To run in detached mode:
```bash
docker-compose up -d
```

To stop:
```bash
docker-compose down
```

### Option 2: Local Installation

1. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

2. **Data Setup** - Choose one option:

   **Option A: Use parquet files (recommended - already in repo)**
   - The 3 parquet files (`DAC_parquet_1.parquet` through `DAC_parquet_3.parquet`) are included
   - Just run the app, no download needed!
   - 70% smaller than CSV, faster loading

   **Option B: Download and convert fresh data**
   ```bash
   # Download the full CMS file (672MB)
   curl -o DAC_NationalDownloadableFile.csv "https://data.cms.gov/provider-data/sites/default/files/resources/52c3f098d7e56028a298fd297cb0b38d_1757685921/DAC_NationalDownloadableFile.csv"

   # Convert to 3 parquet chunks
   python split_data.py
   ```

3. **Run the Dashboard**:
```bash
streamlit run streamlit_app.py
```

The dashboard will open in your browser at `http://localhost:8501`

## Email Discovery Agent Setup

### 1. Get API Keys

**Serper API** (Web Search):
- Sign up at https://serper.dev/
- First 2,500 searches are free
- Then $5 per 1,000 searches

**OpenAI API** (Email Extraction):
- Get key at https://platform.openai.com/api-keys
- Uses GPT-4o-mini: ~$0.15 per 1M input tokens

### 2. Configure Environment

Copy the example env file:
```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
```
SERPER_API_KEY=your_serper_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Run Email Discovery

First, export high-value leads from the dashboard (use the "Contact Export" tab).

Then run the email agent:
```bash
python email_agent.py
```

The agent will:
1. Load your exported leads
2. Search for each organization's website and contact info
3. Use AI to extract emails from search results
4. Save results to `email_discoveries.csv`
5. Cache results to avoid redundant searches

### Cost Estimation

- **100 organizations**: ~$0.50-1.00
- **1,000 organizations**: ~$5-10
- **10,000 organizations**: ~$50-100

Caching significantly reduces costs for repeated runs.

## Usage Tips

### Finding High-Value Targets

1. **Filter by Organization Size**: Focus on "Enterprise" or "Health System" categories (1000+ members)
2. **Geographic Focus**: Select specific states or regions for your territory
3. **Specialty Targeting**: Filter by relevant specialties for your product
4. **Lead Scoring**: Sort by lead score to prioritize organizations with complete contact info

### Email Discovery Strategy

1. **Start Small**: Test with 10-20 organizations first to verify quality
2. **Focus on High-Value**: Export and process only high-lead-score organizations
3. **Verify Results**: Check the confidence level and manually verify a sample
4. **Batch Processing**: Process in batches of 100-500 to manage costs

### Data Freshness

The CMS DAC file is updated regularly. To refresh your data:
1. Download the latest file from the CMS website
2. Replace the existing `DAC_NationalDownloadableFile.csv`
3. Restart the Streamlit app (it will reload the data)

## Dashboard Tabs

### 🎯 Top Organizations
- View organizations ranked by size
- See facility details, member counts, and provider lists
- Phone numbers and addresses included
- Lead scoring for prioritization

### 👥 Provider Details
- Search individual providers
- Filter by name, specialty, facility, or location
- View credentials and education details

### 📊 Analytics
- Organization size distribution
- Specialty analysis
- Gender and graduation year trends
- Top facilities by member count

### 🗺️ Territory Overview
- State-level provider and organization metrics
- Top cities by provider count
- Geographic distribution visualizations

### 📞 Contact Export
- Export filtered data to CSV
- Multiple export options:
  - High-value leads only
  - All filtered data
  - Large organizations (100+ members)
- Email discovery agent instructions

## Lead Scoring System

Organizations are scored based on:
- **Organization Size** (0-10 points)
  - 1000+ members: 10 points
  - 300-999 members: 8 points
  - 100-299 members: 6 points
  - 50-99 members: 4 points
  - 10-49 members: 2 points
  - 1-9 members: 1 point
- **Phone Number** (2 points)
- **Group Practice** (1 point)
- **Telehealth Capability** (1 point)

**Maximum Score**: 14 points

Organizations with scores ≥8 are considered "high-value" leads.

## File Structure

```
joe_dashboard/
├── streamlit_app.py              # Main dashboard application
├── email_agent.py                # Email discovery agent
├── split_data.py                 # Script to convert CSV to parquet chunks
├── DAC_parquet_1.parquet         # CMS data chunk 1 (70MB, git-friendly)
├── DAC_parquet_2.parquet         # CMS data chunk 2 (70MB)
├── DAC_parquet_3.parquet         # CMS data chunk 3 (70MB)
├── requirements.txt              # Python dependencies (includes pyarrow)
├── Dockerfile                    # Docker image definition
├── docker-compose.yml            # Docker compose configuration
├── .env.example                  # Example environment variables
├── .env                          # Your API keys (create this)
├── .gitignore                    # Git ignore patterns
├── email_cache.json              # Email discovery cache (auto-generated)
├── email_discoveries.csv         # Email discovery results (auto-generated)
└── README.md                     # This file

Note: Original CSV files are excluded from git (too large)
Parquet format is 70% smaller and faster to load!
```

## Troubleshooting

### Dashboard won't load
- Ensure all 3 parquet files (`DAC_parquet_1.parquet` through `DAC_parquet_3.parquet`) are present
- If files are missing, run `python split_data.py` after downloading the full CMS CSV
- Check that all dependencies are installed, including pyarrow: `pip install -r requirements.txt`
- Try clearing Streamlit cache: `streamlit cache clear`

### Email agent errors
- Verify API keys are set in `.env` file
- Check API key validity and credits
- Ensure you have exported leads from the dashboard first
- Check internet connection for API calls

### Performance issues
- The initial data load may take 30-60 seconds (2.8M records)
- Data is cached after first load
- Use filters to reduce the dataset size
- Consider processing emails in smaller batches

## License

This project uses public CMS data. Please review CMS data usage policies.

## Support

For issues or questions, please check:
- CMS Data Documentation: https://data.cms.gov/
- Streamlit Documentation: https://docs.streamlit.io/
- OpenAI API Documentation: https://platform.openai.com/docs
- Serper API Documentation: https://serper.dev/docs