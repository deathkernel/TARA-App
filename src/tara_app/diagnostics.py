"""System health, diagnostics, and Windows resource monitoring for TARA-App.

Conforms to Directive Section 9 (System Health and Self-Diagnostics) and
Section 10 (Hardware constraints: Intel Core i5, 16 GB RAM, RTX 2050, 512 GB SSD).
Uses zero external dependencies (pure Python standard library + ctypes on Windows).
"""
from __future__ import annotations

import ctypes
import json
import os
import platform
import shutil
import socket
import sys
import time
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint), ("dwHighDateTime", ctypes.c_uint)]


def _filetime_to_int(ft: _FILETIME) -> int:
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


def get_windows_memory() -> dict[str, Any]:
    """Retrieve physical RAM metrics via Windows GlobalMemoryStatusEx."""
    if sys.platform != "win32":
        return {"supported": False}
    try:
        stat = _MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return {"supported": False, "error": "GlobalMemoryStatusEx failed"}
        total_gb = round(stat.ullTotalPhys / (1024**3), 2)
        avail_gb = round(stat.ullAvailPhys / (1024**3), 2)
        used_gb = round(total_gb - avail_gb, 2)
        return {
            "supported": True,
            "total_gb": total_gb,
            "available_gb": avail_gb,
            "used_gb": used_gb,
            "load_percent": int(stat.dwMemoryLoad),
        }
    except Exception as exc:
        return {"supported": False, "error": str(exc)}


def get_windows_cpu_load(sample_ms: float = 0.05) -> dict[str, Any]:
    """Sample Windows CPU utilization via GetSystemTimes."""
    if sys.platform != "win32":
        return {"supported": False}
    try:
        idle1, kernel1, user1 = _FILETIME(), _FILETIME(), _FILETIME()
        idle2, kernel2, user2 = _FILETIME(), _FILETIME(), _FILETIME()

        k32 = ctypes.windll.kernel32
        if not k32.GetSystemTimes(ctypes.byref(idle1), ctypes.byref(kernel1), ctypes.byref(user1)):
            return {"supported": False, "error": "GetSystemTimes call 1 failed"}
        time.sleep(sample_ms)
        if not k32.GetSystemTimes(ctypes.byref(idle2), ctypes.byref(kernel2), ctypes.byref(user2)):
            return {"supported": False, "error": "GetSystemTimes call 2 failed"}

        idle = _filetime_to_int(idle2) - _filetime_to_int(idle1)
        kernel = _filetime_to_int(kernel2) - _filetime_to_int(kernel1)
        user = _filetime_to_int(user2) - _filetime_to_int(user1)

        total = kernel + user
        if total <= 0:
            return {"supported": True, "cpu_percent": 0.0}
        cpu_percent = max(0.0, min(100.0, round((total - idle) * 100.0 / total, 1)))
        return {"supported": True, "cpu_percent": cpu_percent}
    except Exception as exc:
        return {"supported": False, "error": str(exc)}


def get_disk_metrics(path: str | Path | None = None) -> dict[str, Any]:
    """Retrieve storage metrics for the drive containing path."""
    try:
        target = Path(path or os.getcwd()).resolve()
        usage = shutil.disk_usage(str(target))
        total_gb = round(usage.total / (1024**3), 2)
        free_gb = round(usage.free / (1024**3), 2)
        used_gb = round(usage.used / (1024**3), 2)
        percent_used = round((usage.used / usage.total) * 100.0, 1) if usage.total > 0 else 0.0
        return {
            "supported": True,
            "path": str(target),
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "percent_used": percent_used,
        }
    except Exception as exc:
        return {"supported": False, "error": str(exc)}


def check_omniroute_connectivity(base_url: str = "http://127.0.0.1:20128/v1", api_key: str = "", timeout: float = 0.3) -> dict[str, Any]:
    """Inspect OmniRoute gateway reachability via loopback."""
    try:
        parsed = urlsplit(base_url.strip())
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 20128
    except Exception:
        host, port = "127.0.0.1", 20128

    # Fast loopback pre-flight probe
    try:
        with socket.create_connection((host, port), timeout=min(timeout, 0.25)):
            pass
    except (OSError, socket.timeout):
        return {
            "status": "unreachable",
            "base_url": base_url,
            "message": f"OmniRoute gateway is not running on loopback port {port}",
        }

    models_url = f"{base_url.rstrip('/')}/models"
    headers = {"Accept": "application/json"}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"
    request = Request(models_url, headers=headers, method="GET")
    try:
        opener = build_opener(ProxyHandler({}), _NoRedirectHandler())
        with opener.open(request, timeout=timeout) as response:
            status_code = response.status
            raw = response.read(64 * 1024)
            data = json.loads(raw.decode("utf-8")) if raw else {}
            model_count = len(data.get("data", [])) if isinstance(data, dict) else 0
            return {
                "status": "connected",
                "http_status": status_code,
                "base_url": base_url,
                "models_available": model_count,
            }
    except HTTPError as exc:
        return {
            "status": "gateway_reachable",
            "http_status": exc.code,
            "base_url": base_url,
            "message": f"Gateway responded with HTTP {exc.code}",
        }
    except (URLError, TimeoutError, OSError):
        return {
            "status": "unreachable",
            "base_url": base_url,
            "message": f"OmniRoute gateway is not running on loopback port {port}",
        }
    except Exception as exc:
        return {
            "status": "error",
            "base_url": base_url,
            "message": str(exc),
        }


def collect_system_diagnostics(
    *,
    registry=None,
    sessions_store=None,
    audit_log=None,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    """Collect complete diagnostic report classified into GOOD, NORMAL, WARNING, CRITICAL."""
    ws = Path(workspace_root or os.getcwd()).resolve()
    memory = get_windows_memory()
    cpu = get_windows_cpu_load()
    disk = get_disk_metrics(ws)

    base_url = os.environ.get("TARA_OMNIROUTE_BASE_URL", "http://127.0.0.1:20128/v1")
    api_key = os.environ.get("TARA_OMNIROUTE_API_KEY", "")
    omniroute = check_omniroute_connectivity(base_url=base_url, api_key=api_key)

    # Specialist health
    specialists = {}
    if registry is not None:
        try:
            for mod_id in getattr(registry, "modules", ()):
                adapter = registry.adapter(mod_id)
                if adapter is not None:
                    try:
                        h = adapter.health()
                        specialists[mod_id] = {
                            "status": getattr(h, "status", "unknown"),
                            "capabilities": [c.action for c in getattr(adapter, "capabilities", ())],
                        }
                    except Exception as ex:
                        specialists[mod_id] = {"status": "error", "error": str(ex)}
        except Exception:
            pass

    # Storage & audit status
    storage_info: dict[str, Any] = {"workspace": str(ws)}
    if sessions_store is not None:
        db_path = getattr(sessions_store, "_database_path", None)
        if db_path is not None:
            p = Path(db_path)
            storage_info["session_db"] = {
                "path": str(p),
                "exists": p.is_file(),
                "size_bytes": p.stat().st_size if p.is_file() else 0,
            }
    if audit_log is not None:
        a_path = getattr(audit_log, "path", None)
        if a_path is not None:
            p = Path(a_path)
            storage_info["audit_log"] = {
                "path": str(p),
                "exists": p.is_file(),
                "size_bytes": p.stat().st_size if p.is_file() else 0,
            }

    # Evaluate classification
    issues: list[dict[str, str]] = []
    status = "GOOD"

    if omniroute.get("status") == "unreachable":
        issues.append({
            "severity": "WARNING",
            "component": "OmniRoute",
            "message": "OmniRoute gateway is not running on 127.0.0.1:20128.",
            "recommendation": "Start OmniRoute or ensure loopback port 20128 is accessible.",
        })
        status = "NORMAL"

    if memory.get("supported") and memory.get("load_percent", 0) > 90:
        issues.append({
            "severity": "WARNING",
            "component": "RAM",
            "message": f"High memory load ({memory['load_percent']}%).",
            "recommendation": "Close unused applications to keep TARA responsive on 16 GB hardware.",
        })
        if status == "GOOD":
            status = "NORMAL"

    if disk.get("supported") and disk.get("percent_used", 0) > 95:
        issues.append({
            "severity": "CRITICAL",
            "component": "Disk",
            "message": f"Disk space critically low ({disk['percent_used']}% used, {disk['free_gb']} GB free).",
            "recommendation": "Free up disk space immediately.",
        })
        status = "CRITICAL"

    return {
        "timestamp": time.time(),
        "overall_status": status,
        "environment": {
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "pid": os.getpid(),
        },
        "hardware": {
            "memory": memory,
            "cpu": cpu,
            "disk": disk,
        },
        "omniroute": omniroute,
        "specialists": specialists,
        "storage": storage_info,
        "issues": issues,
    }


__all__ = [
    "get_windows_memory",
    "get_windows_cpu_load",
    "get_disk_metrics",
    "check_omniroute_connectivity",
    "collect_system_diagnostics",
]
