FROM python:3.12.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && adduser --system --uid 10001 appuser

COPY --chown=10001:10001 app.py ui.py .
USER 10001:10001

EXPOSE 8080
CMD ["python", "app.py"]
