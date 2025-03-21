# Stage 1: Build dependencies
FROM python:3.9-slim AS builder

# Cài portaudio19-dev chỉ trong builder stage
RUN apt-get update && apt-get install -y \
    libpq-dev \
    python3-dev \
    build-essential \
    portaudio19-dev \   
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements và cài đặt thư viện
COPY requirements.txt . 
RUN pip install --upgrade pip && \
    pip install wheel && \
    pip install --prefix=/install -r requirements.txt

# Stage 2: Final lightweight image
FROM python:3.9-slim

# Chỉ cài thư viện runtime
RUN apt-get update && apt-get install -y \
    libpq-dev \
    python3-dev \
    build-essential \
    portaudio19-dev \   
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy thư viện đã cài từ builder stage
COPY --from=builder /install /usr/local

# Copy code
COPY src/ ./src/
COPY records/ ./records/
COPY worker_sandbox.py pusher.py .env* ./

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Chạy service
ARG SERVICE=worker
ENV SERVICE_TYPE=$SERVICE

CMD if [ "$SERVICE_TYPE" = "worker" ]; then \
        python worker_sandbox.py; \
    else \
        python pusher.py; \
    fi
