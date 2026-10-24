# BOLD ANALYSIS

A financial analytics and research platform for the Nifty 100 universe.

BOLD ANALYSIS combines ETL, validation, KPI modeling, screener logic, peer benchmarking, dashboarding, and reporting into a single workflow for equity research and investment analysis.

## Why it exists

The project turns raw financial source data into a clean, analytics-ready database and then layers on research workflows for:

- company profiling
- ratio and CAGR calculations
- screener-based investment filtering
- peer group comparison
- sector and valuation analysis
- report generation and dashboard exploration

## What’s included

- SQLite data warehouse with normalized financial tables
- schema validation and data-quality checks
- ratio engine for profitability, leverage, efficiency, and growth metrics
- preset and custom stock screeners
- peer percentile rankings and comparative analytics
- Streamlit dashboard for interactive analysis
- FastAPI service for programmatic access
- PDF and Excel report generation

## Architecture

```text
Raw Excel Data → ETL & Normalization → SQLite → Ratio Engine → Screener/Peer Analysis → Dashboard + API + Reports
```

## Repo structure

```text
.
├── README.md
├── Makefile
├── requirements.txt
├── data/
├── src/
│   ├── etl/
│   ├── analytics/
│   ├── screener/
│   ├── dashboard/
│   ├── api/
│   ├── nlp/
│   └── reports/
├── db/
├── tests/
├── output/
├── reports/
├── docs/
├── config/
├── notebooks/
└── .gitignore
```

## Quick start

### Setup

```bash
git clone https://github.com/abhi07-sr/BOLD-ANALYSIS-.git
cd BOLD-ANALYSIS-
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Common commands

```bash
make load
make ratios
make test
make report
make dashboard
make api
```

### Launch dashboard

```bash
streamlit run src/dashboard/app.py
```

### Launch API

```bash
uvicorn src.api.main:app --reload --port 8000
```

## Outputs

The project generates analyst-ready outputs including:

- `nifty100.db`
- audit and validation CSV files
- screener and peer comparison exports
- valuation summaries
- PDF tearsheets and sector reports
- dashboard and API deliverables

## Quality bar

The workflow is designed around disciplined QA and transparency:

- data integrity checks before analysis
- edge-case handling in calculations
- reproducible outputs
- testable analytics logic
- review-ready reporting artifacts

## Project status

This repository is structured as a full-stack equity research platform for the Nifty 100 universe, with a focus on clean data pipelines, KPI quality, analyst workflow automation, and presentable outputs.

## License

For internal research and analytical use. Review repository usage constraints before external reuse or redistribution.

---

Built for clean financial data, robust KPI modeling, and actionable investment analysis.
