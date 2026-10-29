FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RECRUITMENTGUARD_FEEDBACK_DB=/app/feedback-data/feedback.sqlite3

WORKDIR /app

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY src ./src
COPY artifacts/baseline ./artifacts/baseline

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/feedback-data \
    && chown appuser:appuser /app/feedback-data
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.getenv('PORT', '8000'), timeout=3)"

CMD ["sh", "-c", "uvicorn src.api.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
