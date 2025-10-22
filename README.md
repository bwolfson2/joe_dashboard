# Joe Dashboard - Healthcare Sales Lead Dashboard

Interactive Streamlit dashboard for exploring 2.8M+ healthcare provider records with performance optimizations.

## 🎯 Overview

This project provides a high-performance sales lead dashboard with:
- **2.8M+ Provider Records**: Complete CMS DAC healthcare provider data
- **Performance Optimized**: 75% CPU reduction, 83% faster load times
- **Email Discovery**: Automated system for finding organizational email patterns

## ✨ Key Features

### Dashboard Features
- **Advanced Filtering**: By organization size, state, specialty, contact availability
- **Lead Scoring**: Intelligent ranking based on organization size and contact info
- **Analytics**: Territory analysis, specialty distribution, organization insights
- **Export Capabilities**: Download filtered leads in CSV format
- **Performance Optimized**: Preprocessed data + lazy loading = <1B CPU units

### Email Discovery Features
- **Smart Email Discovery**: Uses Serper API to find organizational email patterns
- **Comprehensive Pattern Matching**: Supports 7+ email format variations
- **Parallel Processing**: Multi-core processing for 1.8M+ records
- **Intelligent Matching**: 3-tier matching algorithm (exact, fuzzy, TF-IDF)
- **Caching System**: Avoids duplicate API calls

## 📁 Project Structure

```
joe_dashboard/
├── scripts/                    # Workflow scripts
│   ├── 01_data_preparation/
│   ├── 02_email_discovery/
│   ├── 03_email_extraction/
│   └── 04_admin_processing/
├── lib/                        # Reusable code
├── tests/                      # Test suite
├── output/                     # Results
└── data/                       # Input data
```

## 🚀 Quick Start

### Dashboard Setup (First Time)

```bash
# Install dependencies
pip install -r requirements.txt

# Preprocess data for optimal performance (run once)
python scripts/01_data_preparation/preprocess_for_dashboard.py

# Run the dashboard
streamlit run streamlit_app.py
```

**Or use the quick deploy script:**
```bash
./deploy_optimized.sh
```

### Email Discovery Workflow

```bash
cp .env.example .env
# Add SERPER_API_KEY to .env

# Run email discovery workflow
python scripts/02_email_discovery/serper_email_search.py -n 1000
python scripts/03_email_extraction/extract_email_formats.py --save-formats
python scripts/04_admin_processing/process_admin_emails.py -w 7
```

See [WORKFLOW.md](WORKFLOW.md) for detailed instructions.

## 📊 Performance & Results

### Dashboard Performance
- **Load Time**: 2-3 seconds (83% faster)
- **CPU Usage**: <1B units (75% reduction)
- **Memory Usage**: ~1GB (67% reduction)
- **Filter Speed**: 0.5-1s (90% faster)

### Email Discovery Results
- **933 facilities** with email formats
- **5,453 doctor emails** generated
- **92.3% test accuracy**
- **~8,000 records/sec** processing speed

## 📖 Documentation

- [WORKFLOW.md](WORKFLOW.md) - Email discovery workflow guide
- [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md) - Dashboard performance details

---

**Version**: 2.0.0 | Dashboard Optimized
