setup:
	pip install -r requirements.txt

dev:
	pip install -e ".[dev]" && pre-commit install

pipeline:
	python pipeline.py

fast:
	python pipeline.py --fast

dashboard:
	streamlit run dashboard/app.py

report:
	python report/build_report.py

test:
	pytest -q

lint:
	ruff check . && ruff format --check .

format:
	ruff format . && ruff check . --fix

audit:
	pip-audit -r requirements-lock.txt

release: lint test
	python tools/make_submission.py && python tools/make_photo_placeholders.py && python tools/checksums.py

.PHONY: setup dev pipeline fast dashboard report test lint format audit release
