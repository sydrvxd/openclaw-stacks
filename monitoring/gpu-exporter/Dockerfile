FROM nvidia/cuda:12.4.1-base-ubuntu22.04

RUN apt-get update && apt-get install -y python3 && rm -rf /var/lib/apt/lists/*

COPY gpu_metrics.py /app/gpu_metrics.py
RUN chmod +x /app/gpu_metrics.py

EXPOSE 9835
CMD ["python3", "/app/gpu_metrics.py"]
