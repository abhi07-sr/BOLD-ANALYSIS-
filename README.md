# BOLD ANALYTICS 

Financial intelligence for the Nifty 100 universe.

BOLD ANALYSIS is a research and analytics platform that turns raw financial data into a clean, queryable database and a decision-ready investment workflow.

## Overview

Built for equity research, screening, benchmarking, and reporting, BOLD ANALYSIS combines:

- ETL and data normalization
- data-quality validation and auditing
- ratio and CAGR analytics
- peer comparison and screener logic
- interactive dashboard views
- FastAPI-based programmatic access
- report generation and export workflows

## Highlights

- SQLite-powered data foundation for company and market data
- validation-first approach with audit and rejection tracking
- profitability, leverage, efficiency, growth, and valuation analytics
- preset and custom stock screeners
- peer percentile analysis and benchmark comparisons
- Streamlit dashboard for analyst workflows
- API layer for integration and automation

## Architecture

```text
Raw Data → ETL → SQLite → Validation → Ratio Engine → Screener/Peer Analysis → Dashboard + API + Reports
```

## Repository Structure

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

## Quick Start

### 1) Clone

```bash
git clone https://github.com/abhi07-sr/BOLD-ANALYSIS-.git
cd BOLD-ANALYSIS-
```

### 2) Setup environment

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3) Run the workflow

```bash
make load
make ratios
make test
```

### 4) Launch dashboard

```bash
streamlit run src/dashboard/app.py
```

### 5) Launch API

```bash
uvicorn src.api.main:app --reload --port 8000
```

## Key Outputs

The project generates analyst-ready files such as:

- `nifty100.db`
- `output/load_audit.csv`
- `output/validation_failures.csv`
- `output/screener_output.xlsx`
- `output/peer_comparison.xlsx`
- `output/valuation_summary.xlsx`
- `reports/tearsheets/`
- `reports/sector/`
- `docs/analyst_guide.pdf`

## Why This Project

BOLD ANALYSIS is designed to provide a transparent, structured, and reusable workflow for evaluating large-cap Indian companies with robust financial logic, analyst-friendly outputs, and easy access through dashboard and API interfaces.

## License

This project is intended for research and analytical use. Review repository usage constraints before external reuse or redistribution.

---

Built for clean financial data, actionable insights, and investment-grade analysis.
