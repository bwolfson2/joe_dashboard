# Sales Lead Dashboard

A Streamlit-based dashboard for analyzing and managing healthcare provider contact information for sales lead generation.

## Features

- **Lead Scoring System**: Automatically scores leads based on:
  - Organization size (doctor count)
  - Decision maker titles
  - Contact information availability
  - Business structure

- **Interactive Filtering**: Filter leads by:
  - State
  - Specialization
  - Minimum lead score

- **Multiple Views**:
  - Top scoring leads
  - Analytics and visualizations
  - Geographic distribution
  - Searchable lead list
  - Lead quality trends

- **Export Functionality**: Download filtered leads as CSV

## Quick Start

### Using Docker (Recommended)

1. Build and run with Docker Compose:
```bash
docker-compose up --build
```

2. Access the dashboard at `http://localhost:8501`

### Manual Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the Streamlit app:
```bash
streamlit run streamlit_app.py
```

3. Access the dashboard at `http://localhost:8501`

## Docker Commands

Build the image:
```bash
docker build -t sales-dashboard .
```

Run the container:
```bash
docker run -p 8501:8501 -v $(pwd)/contact_info_for_joe.csv:/app/contact_info_for_joe.csv sales-dashboard
```

Stop the container:
```bash
docker-compose down
```

## Data Processing

The dashboard processes the CSV file to:
- Score leads based on multiple criteria
- Identify decision makers
- Find large organizations
- Extract contact information
- Analyze geographic distribution

## Lead Scoring Criteria

- **Organization Size**: 1-3 points based on doctor count
- **Decision Maker Title**: 2 points for executives/managers
- **Phone Number**: 1 point if available
- **Business Type**: 1 point for non-sole proprietors

## Requirements

- Python 3.11+
- Docker and Docker Compose (for containerized deployment)
- At least 2GB RAM for processing large datasets