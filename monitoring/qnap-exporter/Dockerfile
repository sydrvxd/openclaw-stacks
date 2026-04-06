FROM python:3.12-slim
RUN apt-get update && apt-get install -y snmp && rm -rf /var/lib/apt/lists/*
COPY exporter.py /app/exporter.py
WORKDIR /app
CMD ["python3", "exporter.py"]
