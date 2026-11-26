FROM python:3.11-slim

# Install system dependencies, ffmpeg, ffprobe, and fonts for Hindi/Urdu/English unicode shaping
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libass-dev \
    fontconfig \
    fonts-noto-core \
    fonts-noto-extra \
    fonts-dejavu-core \
    fonts-liberation \
    fonts-roboto \
    fonts-freefont-ttf \
    curl \
    build-essential \
    libpq-dev \
# Install Montserrat font
RUN mkdir -p /usr/share/fonts/truetype/montserrat && \
    curl -sSL https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf -o /usr/share/fonts/truetype/montserrat/Montserrat.ttf

# Update font cache
RUN fc-cache -fv

WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/

# Environment variables default
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
