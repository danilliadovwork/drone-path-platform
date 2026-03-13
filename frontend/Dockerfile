FROM python:3.11-slim

WORKDIR /app

# 1. Install required system packages for Reflex
RUN apt-get update && apt-get install -y \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy your app code
COPY . .
