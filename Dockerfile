FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    aria2 \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy bot code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create downloads directory
RUN mkdir -p downloads

CMD ["python3", "-m", "PornHub"]
