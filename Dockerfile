FROM python:3.12-slim AS frontend

WORKDIR /app/frontend
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm && rm -rf /var/lib/apt/lists/*
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

COPY config/ config/
COPY --from=frontend /app/frontend/dist frontend/dist

EXPOSE 8000

CMD ["uvicorn", "cronbox.main:app", "--host", "0.0.0.0", "--port", "8000"]
