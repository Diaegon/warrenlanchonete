# Repository Guidelines

## Project Structure & Module Organization

This repository is the ingestion service for Warren data collection. The Python package lives in `warren_ingestion/`; keep crawler code under `warren_ingestion/spiders/` and add supporting modules nearby as needed, for example `items.py`, `pipelines.py`, or `settings.py`. Dependencies are in `pyproject.toml`, container setup is in `Dockerfile`, and runtime examples belong in `.env.example`.

There are currently no committed tests. When adding tests, create `tests/` mirroring the package structure, such as `tests/spiders/test_<spider_name>.py`.

## Build, Test, and Development Commands

- `uv pip install --system -r pyproject.toml`: install dependencies into the active Python environment.
- `python -m pip install -e .`: install the package in editable mode if you are developing outside the Docker image.
- `scrapy list`: list available spiders; this is also the Docker image default command.
- `docker build -t warren-ingestion .`: build the ingestion container.
- `docker run --env-file .env warren-ingestion scrapy list`: run Scrapy in the container with local configuration.

Add a test runner dependency before introducing test commands; `pytest` is the expected default for new Python tests.

## Coding Style & Naming Conventions

Use Python 3.12 features where they simplify code, but keep crawler logic straightforward. Follow PEP 8 with 4-space indentation, snake_case module and function names, PascalCase classes, and descriptive spider names such as `company_filings`. Prefer typed signatures for reusable parsing, database, and transformation helpers. Keep spider side effects isolated from parsing functions so they can be unit tested.

## Testing Guidelines

Use `pytest` for new tests. Name files `test_*.py` and test functions `test_*`. For spiders, cover parsing with saved HTML fixtures or minimal inline responses rather than live network calls. Test database writes through small repository or pipeline units with a disposable database or mocked SQLAlchemy session.

## Commit & Pull Request Guidelines

Recent history uses short, imperative commit messages, for example `add read Me` and `second commit`. Keep commits concise and action-oriented, preferably lowercase imperative text such as `add filings spider` or `configure ingestion pipeline`.

Pull requests should describe the data source, spider or pipeline behavior, configuration changes, and validation performed. Link related issues when available. Include sample Scrapy output for crawler changes, and note new variables added to `.env.example`.

## Security & Configuration Tips

Do not commit real database credentials. Keep `.env.example` limited to placeholder values like `DATABASE_URL=postgresql://user:password@localhost:5432/warren`. Keep scraping credentials and API keys in environment variables only.

# Role

You are a planning agent for a Brazilian stock market web scraping project.

# Goal

Help plan a safe, maintainable ETL/web scraping pipeline to collect:
- company name
- ticker
- source URL
- update date

# Rules

- Do not write implementation code unless explicitly asked.
- First analyze possible data sources.
- Prefer official or structured sources before HTML scraping.
- Check robots.txt and terms of use when relevant.
- Avoid aggressive scraping.
- Propose rate limits, cache strategy, retry strategy, and error handling.
- Separate extraction, transformation, storage, and validation.
- Output plans in small steps.
- Before changing files, explain the proposed change.

# Project context

Backend in Python.
Prefer simple architecture.
Possible storage: SQLite first, PostgreSQL later.
Target sources may include B3, CVM, Fundamentus, Yahoo Finance, or other public sources.
