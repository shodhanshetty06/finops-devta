FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini pytest.ini .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Shell form (not exec-array form) so ${PORT} is actually expanded - Render
# (and most PaaS Docker runners) inject PORT at container start and require
# the process to bind to it; it is not known at image-build time. Falls
# back to 8000 for local `docker run` / docker-compose, which publish that
# port explicitly.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
