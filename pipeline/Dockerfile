FROM python:3.11-slim

WORKDIR /pipeline

RUN apt-get update && apt-get install -y ffmpeg curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY . /pipeline

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["bash", "/pipeline/finalize.sh"]