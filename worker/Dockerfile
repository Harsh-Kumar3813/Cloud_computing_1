FROM python:3.12.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && adduser --system --uid 10001 appuser

COPY --chown=10001:10001 worker.py .
USER 10001:10001

CMD ["python", "worker.py"]
