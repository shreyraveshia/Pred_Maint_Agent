"""Loads config/permissions.yaml and enforces the allow-list."""
from pathlib import Path
import yaml

_PATH = Path(__file__).resolve().parent.parent / "config" / "permissions.yaml"


class PermissionDenied(Exception):
    pass


def load_permissions(path: Path = _PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_tool(tool_name: str, perms: dict | None = None) -> str:
    """Return the tool's access level, or raise PermissionDenied."""
    perms = perms or load_permissions()
    if tool_name in perms.get("never_do", []):
        raise PermissionDenied(f"'{tool_name}' is on the never-do list")
    allowed = perms.get("allowed_tools", {})
    if tool_name not in allowed:
        raise PermissionDenied(f"'{tool_name}' is not on the allow-list")
    return allowed[tool_name]
