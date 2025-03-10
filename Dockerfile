# Stage 1: Build dependencies
FROM python:3.9-slim AS builder

# Install required build dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    python3-dev \
    build-essential \
    portaudio19-dev

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Final lightweight image
FROM python:3.9-slim

# Install only the runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    python3-dev \
    build-essential \
    portaudio19-dev

WORKDIR /app

# Copy installed dependencies from builder stage
COPY --from=builder /install /usr/local

# Copy application files
COPY . .

CMD ["python", "worker_sandbox.py"]
