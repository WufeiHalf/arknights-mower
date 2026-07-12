"""MAA software/resource update helpers."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from arknights_mower import __system__
from arknights_mower.utils.log import logger

# platform routing: windows both; linux github only; macos mirrorchyan only
_SOURCES = {
    "windows": ["github", "mirrorchyan"],
    "linux": ["github"],
    "darwin": ["mirrorchyan"],
}

CHECK_INTERVAL = 6 * 3600
MIRRORCHYAN_BASE = "https://mirrorchyan.com/api/resources"
MAA_VERSION_API = "https://api.maa.plus/MaaAssistantArknights/api/version"
USER_AGENT = "arknights-mower"

_empty_part = {"has_update": False, "latest_version": "", "message": ""}
maa_update_status: dict[str, Any] = {
    "software": dict(_empty_part),
    "resource": dict(_empty_part),
    "checked_at": None,
}
last_maa_update_check_at: float | None = None


def available_sources(system: str | None = None) -> list[str]:
    """Return update sources available on the host platform."""
    return list(_SOURCES.get(system or __system__, ["github"]))


def reset_update_state() -> None:
    global last_maa_update_check_at, maa_update_status
    last_maa_update_check_at = None
    maa_update_status = {
        "software": dict(_empty_part),
        "resource": dict(_empty_part),
        "checked_at": None,
    }


def get_update_status() -> dict[str, Any]:
    return maa_update_status


def _version_key(value: str) -> tuple:
    value = (value or "").strip().lstrip("vV")
    parts: list = []
    for chunk in value.replace("-", ".").replace(" ", ".").replace(":", ".").split("."):
        if not chunk:
            continue
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(chunk)
    return tuple(parts)


def version_is_newer(remote: str, local: str) -> bool:
    """True when remote is non-empty and strictly newer than local."""
    remote = (remote or "").strip()
    local = (local or "").strip()
    if not remote:
        return False
    if not local:
        return True
    if remote == local:
        return False
    try:
        return _version_key(remote) > _version_key(local)
    except TypeError:
        return remote > local


def read_resource_version(maa_path: str | Path) -> str:
    path = Path(maa_path) / "resource" / "version.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return str(data.get("last_updated") or "")
    except Exception:
        return ""


def _proxy_dict(proxy: str) -> dict[str, str] | None:
    proxy = (proxy or "").strip()
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


def _resolve_source(source: str, system: str) -> str:
    sources = available_sources(system)
    if source in sources:
        return source
    return sources[0] if sources else "github"


def _mirrorchyan_latest(
    rid: str,
    *,
    current_version: str = "",
    cdk: str = "",
    channel: str = "",
    os_name: str = "",
    arch: str = "",
    proxy: str = "",
) -> dict[str, Any]:
    params: dict[str, str] = {"user_agent": USER_AGENT}
    if current_version:
        params["current_version"] = current_version
    if cdk:
        params["cdk"] = cdk
    if channel:
        params["channel"] = channel
    if os_name:
        params["os"] = os_name
    if arch:
        params["arch"] = arch
    url = f"{MIRRORCHYAN_BASE}/{rid}/latest"
    resp = requests.get(url, params=params, proxies=_proxy_dict(proxy), timeout=30)
    resp.raise_for_status()
    return resp.json()


def _system_to_mirror_os(system: str) -> str:
    return {"windows": "win", "linux": "linux", "darwin": "macos"}.get(system, "win")


def _host_arch() -> str:
    import platform

    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64"):
        return "arm64"
    return "x64"


def check_software_update(
    *,
    software_version: str,
    source: str,
    channel: str,
    cdk: str,
    proxy: str,
    system: str,
) -> dict[str, Any]:
    result = dict(_empty_part)
    try:
        if source == "mirrorchyan":
            data = _mirrorchyan_latest(
                "MAA",
                current_version=software_version,
                cdk=cdk,
                channel=channel or "stable",
                os_name=_system_to_mirror_os(system),
                arch=_host_arch(),
                proxy=proxy,
            )
            if data.get("code", 0) != 0:
                result["message"] = str(data.get("msg") or f"code={data.get('code')}")
                return result
            remote = str((data.get("data") or {}).get("version_name") or "")
        else:
            url = f"{MAA_VERSION_API}/{channel or 'stable'}.json"
            resp = requests.get(url, proxies=_proxy_dict(proxy), timeout=30)
            resp.raise_for_status()
            remote = str(resp.json().get("version") or "")
        result["latest_version"] = remote
        result["has_update"] = version_is_newer(remote, software_version)
        if result["has_update"]:
            result["message"] = "软件有更新，可点击按钮更新"
    except Exception as e:
        logger.debug(f"MAA software update check failed: {e}")
        result["message"] = str(e)
    return result


def check_resource_update(
    *,
    maa_path: str | Path,
    cdk: str = "",
    proxy: str = "",
) -> dict[str, Any]:
    result = dict(_empty_part)
    local = read_resource_version(maa_path)
    try:
        # resource version check is free on MirrorChyan even without CDK
        data = _mirrorchyan_latest(
            "MaaResource",
            current_version=local,
            cdk=cdk,
            proxy=proxy,
        )
        if data.get("code", 0) != 0:
            result["message"] = str(data.get("msg") or f"code={data.get('code')}")
            return result
        remote = str((data.get("data") or {}).get("version_name") or "")
        result["latest_version"] = remote
        result["has_update"] = version_is_newer(remote, local)
        if result["has_update"]:
            result["message"] = "资源有更新，可点击按钮更新"
    except Exception as e:
        logger.debug(f"MAA resource update check failed: {e}")
        result["message"] = str(e)
    return result


def check_updates(
    *,
    maa_path: str | Path,
    software_version: str,
    source: str = "github",
    channel: str = "stable",
    cdk: str = "",
    proxy: str = "",
    system: str | None = None,
) -> dict[str, Any]:
    system = system or __system__
    source = _resolve_source(source, system)
    software = check_software_update(
        software_version=software_version,
        source=source,
        channel=channel,
        cdk=cdk,
        proxy=proxy,
        system=system,
    )
    resource = check_resource_update(maa_path=maa_path, cdk=cdk, proxy=proxy)
    return {"software": software, "resource": resource}


def check_update_if_due(
    *,
    maa_path: str | Path,
    software_version: str,
    source: str = "github",
    channel: str = "stable",
    cdk: str = "",
    proxy: str = "",
    system: str | None = None,
    force: bool = False,
) -> bool:
    """Run check if due (or force). Returns True if a check ran."""
    global last_maa_update_check_at, maa_update_status
    now = time.monotonic()
    if (
        not force
        and last_maa_update_check_at is not None
        and now - last_maa_update_check_at < CHECK_INTERVAL
    ):
        return False
    try:
        result = check_updates(
            maa_path=maa_path,
            software_version=software_version,
            source=source,
            channel=channel,
            cdk=cdk,
            proxy=proxy,
            system=system,
        )
        maa_update_status = {
            "software": result["software"],
            "resource": result["resource"],
            "checked_at": time.time(),
        }
        last_maa_update_check_at = now
        return True
    except Exception as e:
        logger.debug(f"MAA update check failed silently: {e}")
        last_maa_update_check_at = now
        # keep previous has_update flags false-ish: do not claim update on failure
        maa_update_status = {
            "software": dict(_empty_part),
            "resource": dict(_empty_part),
            "checked_at": time.time(),
        }
        return False


def schedule_async_check(
    *,
    maa_path: str | Path,
    software_version: str,
    source: str = "github",
    channel: str = "stable",
    cdk: str = "",
    proxy: str = "",
) -> None:
    from threading import Thread

    Thread(
        target=check_update_if_due,
        kwargs={
            "maa_path": maa_path,
            "software_version": software_version,
            "source": source,
            "channel": channel,
            "cdk": cdk,
            "proxy": proxy,
        },
        daemon=True,
    ).start()
