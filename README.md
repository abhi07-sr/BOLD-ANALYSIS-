# BOLD ANALYSIS

BOLD ANALYSIS is a full-stack equity research and analytics platform for the Nifty 100 universe. The project ingests source financial data, validates it, builds a normalized SQLite data foundation, computes a rich ratio engine, runs a screener and peer analysis, and exposes the outputs via a Streamlit dashboard and FastAPI service.

The repository is organized around a multi-sprint delivery plan covering ETL, data quality, analytics, dashboarding, reports, NLP, clustering, and API services.

## Project Overview

This project turns raw company financial data into an analytics-ready warehouse for:

- Data ingestion and ETL from Excel and supplemental sources
- Schema validation and DQ checks
- Ratio and CAGR calculations across multiple years
- Screener presets and composite quality scoring
- Peer percentile ranking and radar comparison
- Investment dashboard and company profile views
- PDF tearsheets, sector reports, and portfolio summaries
- NLP-based pros/cons generation and cash flow intelligence
- FastAPI endpoints for programmatic access
- KMeans cluster labeling and portfolio diagnostics

## Why This Project Exists

The goal is to create a reproducible analytics workflow for Indian large-cap equity research, with a strong emphasis on:

- clean financial data capture
- transparent formula logic and edge-case handling
- business-ready outputs for analysts and portfolio managers
- testable data quality gates
- a dashboard and API usable beyond the notebook workflow

## Core Architecture

- Data layer: SQLite database (`nifty100.db`)
- ETL layer: Excel loaders, schema validation, normalizers, and audit exports
- Analytics layer: profitability, leverage, efficiency, CAGR, valuation, and clustering modules
- Screener layer: preset screeners and custom threshold filters
- Dashboard layer: Streamlit multi-page analytics UI
- API layer: FastAPI endpoints for company, screener, peer, and sector data
- Reporting layer: PDF tearsheets, sector reports, and portfolio summaries
- NLP layer: parser and generated pros/cons logic

## Repository Layout

```text
.
├── README.md
├── Makefile
├── requirements.txt
├── data/
│   ├── source_excel/
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
│   ├── capital_allocation.csv
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
└── notebooks/
    └── exploratory_queries.sql
```

## Project Workflow

The project follows a sprint-based development flow with the following major phases:

1. Data Foundation
   - load source data, validate schema, and populate SQLite
   - enforce DQ rules and issue tracking for failures

2. Ratio Engine
   - compute profitability, leverage, efficiency, CAGR, and cash flow KPIs
   - populate `financial_ratios` and related outputs

3. Screener and Peer Analysis
   - apply preset filters and score quality
   - rank companies within peer groups and generate comparison exports

4. Dashboard and API
   - expose company, screener, sector, and valuation analytics through a UI and service layer

5. Reporting and NLP
   - generate tearsheets, sector reports, pros/cons, and insight summaries

6. Cluster and QA
   - assign cluster archetypes, run acceptance gating, and verify full-suite test health

## Data Foundations and Quality Rules

The project enforces a strict data-quality framework:

- 10 canonical SQLite tables for company, financial, price, and ratio data
- 12 source files and 7 core Excel inputs
- 16 validation rules across primary keys, foreign keys, balance checks, margin checks, and sales sanity rules
- row audit and rejection logging
- manual review of sampled companies and edge-case fixes

## Key Commands

The Makefile standardizes the project workflow:

```bash
make load
make ratios
make test
make report
make dashboard
make api
make clean
```

### Run the ETL load

```bash
make load
```

### Generate ratio tables and analytics outputs

```bash
make ratios
```

### Run the test suite

```bash
make test
```

### Generate reports and tearsheets

```bash
make report
```

### Launch the dashboard

```bash
make dashboard
```

### Launch the API

```bash
make api
```

## Local Setup

### 1) Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Load data and run tests

```bash
make load
make test
```

## Dashboard

Launch the Streamlit analytics dashboard:

```bash
streamlit run src/dashboard/app.py
```

The dashboard includes screens for:

- Home
- Company profile
- Screener
- Peer comparison
- Trends
- Sectors
- Capital allocation
- Reports

## API

Run the FastAPI app:

```bash
uvicorn src.api.main:app --reload --port 8000
```

Open the docs:

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Testing

The project aims for a strong automated QA posture:

- ETL unit tests
- KPI formula tests
- DQ rule tests
- API integration tests
- full pytest suite and HTML report generation

Example:

```bash
pytest tests/ -v --html=reports/pytest_report.html
```

## Important Project Rules

- Use `pd.read_excel(path, header=1)` for core Excel loads when applicable
- Normalize `company_id` by trimming spaces and uppercasing before joins
- Store all monetary values in INR Crore
- Skip the Financials sector when applying D/E screener logic
- Handle formula edge cases such as negative equity, zero denominators, turnaround scenarios, and debt-free cases explicitly
- Clearly label simulated datasets in dashboards and reports
- Run `make test` before every Git commit

## Deliverables Snapshot

The project is designed to produce the following outputs:

- `nifty100.db` with a populated warehouse of financial tables
- `output/load_audit.csv`
- `output/validation_failures.csv`
- `output/screener_output.xlsx`
- `output/peer_comparison.xlsx`
- `output/valuation_summary.xlsx`
- `output/valuation_flags.csv`
- `output/pros_cons_generated.csv`
- `output/cashflow_intelligence.xlsx`
- `reports/tearsheets/` PDF company reports
- `reports/sector/` PDF sector summaries
- `reports/portfolio/` portfolio summary PDF
- `src/api/main.py` with 16+ FastAPI endpoints
- `docs/analyst_guide.pdf`

## Acceptance Philosophy

The project enforces acceptance gates covering:

- full data load integrity
- ratio quality and validation
- screener quality and peer comparison correctness
- dashboard responsiveness and chart rendering
- API availability and contract correctness
- pytest health and zero-failure compliance

## Contributing

This repository is intended for a structured analytical research workflow and follows reproducible engineering practices:

- small, testable modules
- explicit validations and edge-case handling
- consistent naming and output conventions
- reviewable data quality artifacts

## License

This project is intended for internal analytical and research use. Please check the repository owner and project governance before commercial reuse or redistribution.

## Status

The repository is structured as a multi-sprint analytics platform for Nifty 100 research, with emphasis on clean financial data, robust ratio logic, and analyst-friendly reporting.

## Authors / Maintainers

Project delivery is organized around the sprint plan defined in this repository and is intended to support a team workflow led by the project owner and analytics lead.

---

This README is intentionally written as a project-level overview for an analytics platform that follows a full ETL-to-dashboard pipeline. It can be refined further as the repository fills in implementation modules and generated output artifacts.
