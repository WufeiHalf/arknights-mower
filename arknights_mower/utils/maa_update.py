"""MAA software/resource update helpers."""

from __future__ import annotations

from arknights_mower import __system__

# platform routing: windows both; linux github only; macos mirrorchyan only
_SOURCES = {
    "windows": ["github", "mirrorchyan"],
    "linux": ["github"],
    "darwin": ["mirrorchyan"],
}


def available_sources(system: str | None = None) -> list[str]:
    """Return update sources available on the host platform."""
    return list(_SOURCES.get(system or __system__, ["github"]))
