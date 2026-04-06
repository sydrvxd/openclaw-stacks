#!/usr/bin/env python3
"""QNAP SNMP Exporter — parses string values from QNAP SNMP into Prometheus metrics."""

import re
import subprocess
import time
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

NAS_IP = "192.168.1.100"
SNMP_USER = "openclaw"
SNMP_AUTH = "0H*fHpI@Ht05"
GPU_EXPORTER_URL = f"http://{NAS_IP}:9835/metrics"
PORT = 9117

def snmp_get(oid: str) -> str:
    """Get a single SNMP value."""
    try:
        result = subprocess.run(
            ["snmpget", "-v3", "-u", SNMP_USER, "-l", "authNoPriv",
             "-a", "MD5", "-A", SNMP_AUTH, "-Oqv", "-t", "5", NAS_IP, oid],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip().strip('"')
    except Exception:
        return ""

def snmp_walk(oid: str) -> list:
    """Walk an SNMP subtree, return list of (index, value)."""
    try:
        result = subprocess.run(
            ["snmpwalk", "-v3", "-u", SNMP_USER, "-l", "authNoPriv",
             "-a", "MD5", "-A", SNMP_AUTH, "-Oqv", "-t", "10", NAS_IP, oid],
            capture_output=True, text=True, timeout=30
        )
        values = []
        for i, line in enumerate(result.stdout.strip().split("\n"), 1):
            val = line.strip().strip('"')
            if val:
                values.append((str(i), val))
        return values
    except Exception:
        return []

def parse_number(s: str) -> float:
    """Extract first number from a string like '9.1 %' or '55 C/131 F'."""
    m = re.search(r'([0-9.]+)', s)
    return float(m.group(1)) if m else 0

def parse_rpm(s: str) -> float:
    m = re.search(r'(\d+)\s*RPM', s)
    return float(m.group(1)) if m else 0

def parse_celsius(s: str) -> float:
    m = re.search(r'(\d+)\s*C', s)
    return float(m.group(1)) if m else 0

def collect_gpu() -> list:
    """Collect GPU metrics from NAS-local exporter via HTTP (no SSH needed)."""
    try:
        req = urllib.request.urlopen(GPU_EXPORTER_URL, timeout=5)
        # Pass through all metric lines from the GPU exporter
        return [line for line in req.read().decode().strip().split("\n") if line]
    except Exception as e:
        return [f'# GPU collection error: {e}']


def collect_metrics() -> str:
    lines = []

    # System scalars
    cpu_usage = snmp_get(".1.3.6.1.4.1.24681.1.2.1.0")
    mem_total = snmp_get(".1.3.6.1.4.1.24681.1.2.2.0")
    mem_free = snmp_get(".1.3.6.1.4.1.24681.1.2.3.0")
    cpu_temp = snmp_get(".1.3.6.1.4.1.24681.1.2.5.0")
    sys_temp = snmp_get(".1.3.6.1.4.1.24681.1.2.6.0")

    lines.append(f'# HELP qnap_cpu_usage_percent CPU usage percentage')
    lines.append(f'# TYPE qnap_cpu_usage_percent gauge')
    lines.append(f'qnap_cpu_usage_percent {parse_number(cpu_usage)}')

    lines.append(f'# HELP qnap_memory_total_mb Total memory in MB')
    lines.append(f'# TYPE qnap_memory_total_mb gauge')
    lines.append(f'qnap_memory_total_mb {parse_number(mem_total)}')

    lines.append(f'# HELP qnap_memory_free_mb Free memory in MB')
    lines.append(f'# TYPE qnap_memory_free_mb gauge')
    lines.append(f'qnap_memory_free_mb {parse_number(mem_free)}')

    lines.append(f'# HELP qnap_cpu_temp_celsius CPU temperature')
    lines.append(f'# TYPE qnap_cpu_temp_celsius gauge')
    lines.append(f'qnap_cpu_temp_celsius {parse_celsius(cpu_temp)}')

    lines.append(f'# HELP qnap_system_temp_celsius System temperature')
    lines.append(f'# TYPE qnap_system_temp_celsius gauge')
    lines.append(f'qnap_system_temp_celsius {parse_celsius(sys_temp)}')

    # HDD table
    hdd_descs = snmp_walk(".1.3.6.1.4.1.24681.1.2.11.1.2")
    hdd_temps = snmp_walk(".1.3.6.1.4.1.24681.1.2.11.1.3")
    hdd_models = snmp_walk(".1.3.6.1.4.1.24681.1.2.11.1.5")
    hdd_smarts = snmp_walk(".1.3.6.1.4.1.24681.1.2.11.1.7")

    lines.append(f'# HELP qnap_hdd_temp_celsius HDD temperature')
    lines.append(f'# TYPE qnap_hdd_temp_celsius gauge')
    for i, (idx, val) in enumerate(hdd_temps):
        desc = hdd_descs[i][1] if i < len(hdd_descs) else f"HDD{idx}"
        model = hdd_models[i][1] if i < len(hdd_models) else "unknown"
        lines.append(f'qnap_hdd_temp_celsius{{hdd="{desc}",model="{model}"}} {parse_celsius(val)}')

    lines.append(f'# HELP qnap_hdd_smart_ok HDD SMART status (1=GOOD, 0=BAD)')
    lines.append(f'# TYPE qnap_hdd_smart_ok gauge')
    for i, (idx, val) in enumerate(hdd_smarts):
        desc = hdd_descs[i][1] if i < len(hdd_descs) else f"HDD{idx}"
        lines.append(f'qnap_hdd_smart_ok{{hdd="{desc}"}} {1 if val.upper() == "GOOD" else 0}')

    # Fan table
    fan_descs = snmp_walk(".1.3.6.1.4.1.24681.1.2.15.1.2")
    fan_speeds = snmp_walk(".1.3.6.1.4.1.24681.1.2.15.1.3")

    lines.append(f'# HELP qnap_fan_speed_rpm Fan speed in RPM')
    lines.append(f'# TYPE qnap_fan_speed_rpm gauge')
    for i, (idx, val) in enumerate(fan_speeds):
        desc = fan_descs[i][1] if i < len(fan_descs) else f"Fan{idx}"
        lines.append(f'qnap_fan_speed_rpm{{fan="{desc}"}} {parse_rpm(val)}')

    # GPU via SSH
    lines.extend(collect_gpu())

    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            metrics = collect_metrics()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(metrics.encode())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b'<html><body><a href="/metrics">Metrics</a></body></html>')

    def log_message(self, format, *args):
        pass  # suppress access logs


if __name__ == "__main__":
    print(f"QNAP Exporter listening on :{PORT}/metrics")
    server = HTTPServer(("0.0.0.0", PORT), MetricsHandler)
    server.serve_forever()
