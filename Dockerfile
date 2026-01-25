FROM python:3.9-slim

# Install FFmpeg (Crucial for yt-dlp to merge video and audio)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create downloads folder
RUN mkdir -p downloads

EXPOSE 10000

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:server"]
