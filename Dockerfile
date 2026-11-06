# Runs the Clause Analyser connector online (see src/dispute_clause_analyzer/web.py).
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml LICENSE README.md ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --create-home connector

USER connector
ENV CLAUSE_ANALYSER_MODE=online \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["clause-analyser-web"]
