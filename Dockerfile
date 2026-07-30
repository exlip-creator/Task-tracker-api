# Build stage
FROM python:3.13-slim AS builder
WORKDIR /app

COPY requirements.txt .

RUN python -m pip install --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# Runtime stage
FROM python:3.13-slim AS runtime
WORKDIR /app

COPY requirements.txt .
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt

RUN groupadd --system workgroup && useradd --system --group workgroup workuser

COPY --chown=workuser:workgroup app ./app

USER workuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]