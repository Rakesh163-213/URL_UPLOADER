FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Upgrade pip first
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . .

# Check dependencies, skip yt-dlp check if not necessary

# Ensure start.sh is executable (just in case)


# Start the bot using your script
#CMD ["sh", "start.sh"]
CMD ["python3", "bot.py"]