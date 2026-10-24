# BOLD ANALYSIS

A multi-sprint financial analytics platform for Nifty 100 research, covering ETL, data quality, valuation, ratios, profiling, screening, peer comparison, dashboards, and API-driven analysis.

BOLD ANALYSIS transforms raw financial source files into a clean analytics-ready database and then layers on powerful investment workflows for screening, benchmarking, and reporting.

## Overview

BOLD ANALYSIS is designed for equity research and investment analysis workflows. It combines financial data ingestion, schema validation, KPI generation, screener logic, peer benchmarking, and a rich interactive dashboard into a single project workflow.

The platform is structured to support:

- clean financial data loading from Excel sources
- rigorous data-quality validation and audit outputs
- ratio engine calculations across multiple years
- sector and company-level analytics
- peer group comparisons and screening filters
- dashboard and API access for analysts
- report generation for insights and review

## Why This Project

The core objective is to build a reproducible, production-style financial research pipeline for Indian large-cap equities. The project focuses on transparency, data discipline, and analyst usability.

It brings together:

- ETL and data normalization
- KPI formula computation and edge-case handling
- equity screener presets and custom thresholds
- peer percentile analysis
- interactive dashboard views
- API-based access to analytics data
- PDF report generation and summary outputs

## Key Features

### Data foundation
- SQLite database generation from raw source files
- standardized schema with 10 core tables
- row-level audit logging and rejection tracking
- data quality validation rules and failure exports

### Analytics engine
- profitability ratios
- leverage and efficiency metrics
- CAGR and growth analysis
- cash flow intelligence
- valuation and market cap-based indicators
- cluster profiling and sector benchmarking

### Screener and peer analysis
- preset screeners for quality, value, growth, dividend, debt-free, and turnaround strategies
- custom threshold-based filtering
- peer percentile ranking across peer groups
- radar comparison charts and benchmark views

### Reporting and dashboards
- Streamlit multi-page dashboard
- company profile, screener, sector, trends, and capital allocation screens
- PDF tearsheets and sector summaries
- exports for CSV, Excel, and PDF use cases

### API access
- FastAPI back end for programmatic analytics access
- endpoints for companies, sectors, screener, peers, valuation, and health checks
- OpenAPI documentation available through FastAPI

## Architecture

```text
Source Financial Data
        ↓
ETL + Normalization
        ↓
SQLite Data Warehouse
        ↓
Validation + Data Quality Checks
        ↓
Ratio & KPI Engine
        ↓
Screener + Peer Ranking + Clustering
        ↓
Dashboard + API + Reporting Layer
```

## Project Structure

```text
BOLD-ANALYSIS-
├── README.md
├── Makefile
├── requirements.txt
├── data/
│   └── nifty100.db
├── src/
│   ├── etl/
│   ├── analytics/
│   ├── screener/
│   ├── dashboard/
│   ├── api/
│   ├── nlp/
│   └── reports/
├── db/
│   └── schema.sql
├── tests/
│   ├── etl/
│   ├── kpi/
│   ├── dq/
│   └── api/
├── output/
│   ├── load_audit.csv
│   ├── validation_failures.csv
│   ├── screener_output.xlsx
│   ├── peer_comparison.xlsx
│   ├── valuation_summary.xlsx
│   └── ...
├── reports/
│   ├── tearsheets/
│   ├── sector/
│   ├── portfolio/
│   └── pytest_report.html
├── docs/
│   ├── analyst_guide.pdf
│   └── acceptance_checklist.pdf
├── config/
│   └── screener_config.yaml
├── notebooks/
│   └── exploratory_queries.sql
└── .gitignore
```

## Tech Stack

- Python
- Pandas
- SQLite
- Plotly
- Streamlit
- FastAPI
- SQLAlchemy / DB interactions as needed
- ReportLab / PDF generation tools
- Pytest for automated validation
- Excel and CSV data processing workflows

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/abhi07-sr/BOLD-ANALYSIS-.git
cd BOLD-ANALYSIS-
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate
```

On Windows:

```bash
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the ETL / load pipeline

```bash
make load
```

### 5. Generate ratios and analytics outputs

```bash
make ratios
```

### 6. Run tests

```bash
make test
```

## Dashboard

Launch the Streamlit dashboard:

```bash
streamlit run src/dashboard/app.py
```

This app includes:

- Home overview
- Company profile views
- Screener with live filtering
- Peer comparison screens
- Sector and trend analysis
- Capital allocation map
- Reports and export screens

## API

Start the FastAPI service:

```bash
uvicorn src.api.main:app --reload --port 8000
```

Then open:

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI spec: `http://localhost:8000/openapi.json`

## Key Commands

```bash
make load      # Load source files into SQLite
make ratios    # Compute financial ratios and related KPIs
make test      # Run pytest validation suite
make report    # Generate reports and exports
make dashboard # Start the Streamlit dashboard
make api       # Start the API service
make clean     # Remove generated artifacts and cache
```

## Data Quality Standards

The project enforces disciplined validation logic, including:

- PK and FK integrity checks
- financial consistency checks
- balance-sheet sanity rules
- margin and sales QA rules
- audit logging for failures and anomalies
- manual review and sign-off flow for critical output

## Sprint-Based Delivery Model

The repository is organized around a structured delivery roadmap covering:

- Data foundation and ETL
- Ratio engine and financial analytics
- Screener and peer ranking
- Dashboard and valuation layer
- NLP and reporting modules
- API and clustering work
- QA, review, and sign-off

## Output Artifacts

The project generates analytics and reporting outputs such as:

- `nifty100.db`
- `output/load_audit.csv`
- `output/validation_failures.csv`
- `output/screener_output.xlsx`
- `output/peer_comparison.xlsx`
- `output/valuation_summary.xlsx`
- `output/pros_cons_generated.csv`
- `output/cashflow_intelligence.xlsx`
- company and sector PDF reports
- clustering and portfolio summary files

## Acceptance and QA

The project targets a disciplined quality bar with emphasis on:

- 0 failing tests in the validated suite
- data integrity checks before analytics use
- documented edge cases and anomaly handling
- consistent dashboard and API behavior
- analyst-ready reporting outputs

## Project Status

This repository is structured as a full-stack financial analytics platform for equity research and portfolio analysis. It is intended to be extended and refined as the ETL, analytics, dashboard, and reporting modules are completed.

## License

This project is intended for analytical and research workflows. Please review repository usage constraints and validate any commercial or external redistribution before reuse.

## Contributors

This project is organized as a collaborative, sprint-based implementation for research and analytics work.

---

Built for clean financial data, robust KPI logic, and analyst-grade outputs.
