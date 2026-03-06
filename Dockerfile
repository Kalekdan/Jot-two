FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY system_prompt.txt ./
COPY src/ ./src/

# Default entrypoint – override the CMD in docker-compose per service.
CMD ["python", "-m", "src.main"]
