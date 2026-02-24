# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Chrome and SeleniumBase
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget -q -O /tmp/google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y /tmp/google-chrome-stable_current_amd64.deb \
    && rm /tmp/google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir seleniumbase

# Pre-install chromedriver with proper permissions
RUN seleniumbase install chromedriver

# Create a non-root user for security
RUN useradd -m -u 1000 appuser

# Fix permissions for seleniumbase drivers directory
RUN chmod -R 777 /usr/local/lib/python3.11/site-packages/seleniumbase/drivers/

# Copy application files
COPY main.py .
COPY stations.py .
COPY tdx.py .

# Copy browser extension if it exists
COPY extension/ ./extension/

# Change ownership of app directory
RUN chown -R appuser:appuser /app
USER appuser

# Set display environment for headless mode
ENV DISPLAY=:99

# Set entrypoint to allow command line arguments
ENTRYPOINT ["python", "main.py"]