"""
Global service availability registry.

Services register their connection status here at startup.
Use the /status endpoint to query which services are available.
"""

from typing import Any, Dict, Optional

_registry: Dict[str, dict] = {}

SERVICE_DESCRIPTIONS: Dict[str, str] = {
    "sport": "Robot sport control (Unitree SDK)",
    "state": "Robot state via Unitree SDK (DDS)",
    "device_watcher": "Device health monitoring and auto-recovery",
}


def register(
    name: str,
    available: bool,
    error: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Register or update a service's availability status."""
    _registry[name] = {
        "available": available,
        "error": error,
        "extra_data": extra_data or {},
    }


def get_all() -> Dict[str, dict]:
    """Return the full status of all known services."""
    result = {}
    for name, description in SERVICE_DESCRIPTIONS.items():
        entry = _registry.get(
            name, {"available": None, "error": None, "extra_data": {}}
        )
        result[name] = {
            "available": entry.get("available"),
            "error": entry.get("error"),
            "description": description,
            "extra_data": entry.get("extra_data") or {},
        }
    return result


def is_available(name: str) -> bool:
    """Return True if the service is registered as available (or not yet registered)."""
    status = _registry.get(name)
    if status is None:
        return True
    return status.get("available") is True


def get_unavailable_reason(name: str) -> Optional[str]:
    """
    Return the error message if the service is registered as unavailable.
    Returns None if the service is available or not yet registered.
    """
    status = _registry.get(name)
    if status is None or status.get("available") is not False:
        return None
    return status.get("error") or f"{name} service not available"
