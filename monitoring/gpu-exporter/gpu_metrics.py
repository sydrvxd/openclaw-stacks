#!/usr/bin/env python3
"""Simple NVIDIA GPU metrics exporter for Prometheus"""

import subprocess
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

def get_gpu_metrics():
    """Query nvidia-smi and return Prometheus-formatted metrics"""
    try:
        result = subprocess.run([
            'nvidia-smi',
            '--query-gpu=index,name,uuid,utilization.gpu,utilization.memory,memory.used,memory.total,memory.free,temperature.gpu,power.draw,power.limit,fan.speed,pstate',
            '--format=csv,noheader,nounits'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            return "# nvidia-smi failed\n"
        
        lines = []
        lines.append("# HELP nvidia_gpu_utilization_percent GPU utilization percentage")
        lines.append("# TYPE nvidia_gpu_utilization_percent gauge")
        lines.append("# HELP nvidia_memory_used_bytes GPU memory used in bytes")
        lines.append("# TYPE nvidia_memory_used_bytes gauge")
        lines.append("# HELP nvidia_memory_total_bytes GPU memory total in bytes")
        lines.append("# TYPE nvidia_memory_total_bytes gauge")
        lines.append("# HELP nvidia_memory_free_bytes GPU memory free in bytes")
        lines.append("# TYPE nvidia_memory_free_bytes gauge")
        lines.append("# HELP nvidia_temperature_celsius GPU temperature in Celsius")
        lines.append("# TYPE nvidia_temperature_celsius gauge")
        lines.append("# HELP nvidia_power_draw_watts GPU power draw in watts")
        lines.append("# TYPE nvidia_power_draw_watts gauge")
        lines.append("# HELP nvidia_power_limit_watts GPU power limit in watts")
        lines.append("# TYPE nvidia_power_limit_watts gauge")
        lines.append("# HELP nvidia_fan_speed_percent GPU fan speed percentage")
        lines.append("# TYPE nvidia_fan_speed_percent gauge")
        
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 13:
                continue
                
            idx, name, uuid = parts[0], parts[1], parts[2]
            gpu_util = parts[3]
            mem_util = parts[4]
            mem_used = parts[5]  # MiB
            mem_total = parts[6]  # MiB
            mem_free = parts[7]  # MiB
            temp = parts[8]
            power_draw = parts[9]
            power_limit = parts[10]
            fan_speed = parts[11]
            pstate = parts[12]
            
            labels = f'gpu="{idx}",name="{name}",uuid="{uuid}"'
            
            # Convert [Not Supported] to empty
            def safe_float(v, default="0"):
                try:
                    return str(float(v))
                except:
                    return default
            
            lines.append(f'nvidia_gpu_utilization_percent{{{labels}}} {safe_float(gpu_util)}')
            lines.append(f'nvidia_memory_used_bytes{{{labels}}} {safe_float(str(float(mem_used) * 1024 * 1024) if mem_used.replace(".", "").isdigit() else "0")}')
            lines.append(f'nvidia_memory_total_bytes{{{labels}}} {safe_float(str(float(mem_total) * 1024 * 1024) if mem_total.replace(".", "").isdigit() else "0")}')
            lines.append(f'nvidia_memory_free_bytes{{{labels}}} {safe_float(str(float(mem_free) * 1024 * 1024) if mem_free.replace(".", "").isdigit() else "0")}')
            lines.append(f'nvidia_temperature_celsius{{{labels}}} {safe_float(temp)}')
            lines.append(f'nvidia_power_draw_watts{{{labels}}} {safe_float(power_draw)}')
            lines.append(f'nvidia_power_limit_watts{{{labels}}} {safe_float(power_limit)}')
            lines.append(f'nvidia_fan_speed_percent{{{labels}}} {safe_float(fan_speed)}')
        
        return '\n'.join(lines) + '\n'
    except Exception as e:
        return f"# Error: {e}\n"

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            metrics = get_gpu_metrics()
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(metrics.encode('utf-8'))
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><a href="/metrics">Metrics</a></body></html>')
    
    def log_message(self, format, *args):
        pass  # Suppress logging

if __name__ == '__main__':
    port = 9835
    print(f"Starting GPU exporter on port {port}")
    server = HTTPServer(('0.0.0.0', port), MetricsHandler)
    server.serve_forever()
