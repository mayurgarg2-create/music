FROM python:3.11-slim

# Install ffmpeg and nodejs (required for yt-dlp extraction)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all bot files
COPY . .

CMD ["python", "bot.py"]
