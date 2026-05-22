FROM python:3.11-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    fonts-liberation libpango-1.0-0 libpangocairo-1.0-0 \
    wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (cached layer — only re-runs if requirements.txt changes)
RUN playwright install chromium

# Copy application code (changes frequently — separate layer)
COPY . .

EXPOSE 3000

RUN chmod +x start.sh
CMD ["bash", "start.sh"]
