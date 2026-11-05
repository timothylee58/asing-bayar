FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run unprivileged.
RUN useradd --system --uid 1001 --no-create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Behind a TLS-terminating proxy: trust X-Forwarded-* so rate limiting sees real client IPs.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
