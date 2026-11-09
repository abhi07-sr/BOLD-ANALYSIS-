.PHONY: load ratios screener peer test report dashboard api clean help

help:
	@echo "Available targets:"
	@echo "  load      - Run ETL pipeline to load and validate data into nifty100.db"
	@echo "  ratios    - Compute or verify financial ratios"
	@echo "  test      - Run test suite (pytest tests/etl)"
	@echo "  report    - Generate data quality audit and validation reports"
	@echo "  dashboard - Launch analytics dashboard"
	@echo "  api       - Start FastAPI application server"
	@echo "  clean     - Remove temporary files and cached databases"

load:
	python -m src.etl.loader

ratios:
	python -m src.analytics.engine

screener:
	python -m src.screener.engine

peer:
	python -m src.analytics.peer

test:
	pytest tests -v

report:
	python -m src.etl.validator

dashboard:
	python -c "print('Dashboard module ready for Sprint 2')"

api:
	python -c "print('API module ready for Sprint 2')"

clean:
	python -c "import os, glob; [os.remove(f) for f in glob.glob('*.pyc') + glob.glob('**/*.pyc', recursive=True)]"

