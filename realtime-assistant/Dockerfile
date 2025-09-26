FROM python:3.11-slim

WORKDIR /realtime-assistant

RUN apt-get update && apt-get install -y \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /realtime-assistant

EXPOSE 9091

ENTRYPOINT ["python", "/realtime-assistant/realtime_assistant.py"]