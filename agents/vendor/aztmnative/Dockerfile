FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-dev.txt

# Copy the rest of the application
COPY . .

# Install the package in editable mode
RUN pip install -e .

# Create non-root user
RUN useradd -m -s /bin/bash aztm && \
    chown -R aztm:aztm /app

USER aztm

# Default command
CMD ["pytest", "-v"]