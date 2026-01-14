# VARDA Lead Generation Scraper - Dockerfile
# Build: docker build -t varda-scraper .
# Run: docker run -p 8501:8501 -e OPENAI_API_KEY=your_key_here varda-scraper

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    libpango-1.0-0 \
    libcairo2 \
    libxshmfence1 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (this takes a few minutes)
RUN playwright install chromium
RUN playwright install-deps chromium || true

# Copy application code
COPY . .

# Create output directory
RUN mkdir -p output

# Expose Streamlit port (Railway uses PORT env var)
EXPOSE 8080

# Set environment variables
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV HEADLESS_MODE=true
ENV PYTHONUNBUFFERED=1

# Health check (uses PORT env var)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os, requests; port = os.getenv('PORT', '8080'); requests.get(f'http://localhost:{port}/_stcore/health')" || exit 1

# Run Streamlit (Railway provides PORT env var)
CMD sh -c "streamlit run dashboard.py --server.port=\${PORT:-8080} --server.address=0.0.0.0"
