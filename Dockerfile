# Use official slim Python image
FROM python:3.10-slim

# Optional: Prevent Python from writing .pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies (for yt-dlp and other tools that need ffmpeg or SSL support)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
        libffi-dev \
        libnss3 \
        libssl-dev \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
        gcc \
        && rm -rf /var/lib/apt/lists/*

# Install pip and upgrade
RUN pip install --upgrade pip

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY . .

# Set environment variable for the bot token (you’ll inject this via Fly secrets)
ENV DISCORD_TOKEN=""

# Run the bot
CMD ["python", "bot.py"]
