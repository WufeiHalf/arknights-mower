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


# --- download / apply ---

CDK_ERROR_MESSAGES = {
    7001: "CDK 已过期",
    7002: "CDK 无效",
    7003: "今日下载次数已达上限",
    7004: "CDK 类型与资源不匹配",
    7005: "CDK 已被封禁",
    8001: "该平台不支持此更新源",
}

PENDING_DIRNAME = ".pending_update"
MAA_UPDATE_TIMEOUT = 3600
GITHUB_RESOURCE_ZIP = (
    "https://github.com/MaaAssistantArknights/MaaResource/archive/refs/heads/main.zip"
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def cdk_error_message(code: int | str) -> str:
    code_i = _safe_int(code, -1)
    if code_i < 0:
        return f"更新失败：{code}"
    return CDK_ERROR_MESSAGES.get(code_i, f"更新失败：code={code_i}")


def pending_update_dir(maa_path: str | Path) -> Path:
    return Path(maa_path) / PENDING_DIRNAME


def has_pending_update(maa_path: str | Path) -> bool:
    """True only when a complete pending package (meta + archive) is present."""
    path = pending_update_dir(maa_path)
    if not path.is_dir():
        return False
    meta = path / "meta.json"
    if not meta.is_file():
        return False
    archives = [
        p
        for p in path.iterdir()
        if p.is_file() and (p.suffix in {".zip", ".gz"} or p.name.endswith(".tar.gz"))
    ]
    return bool(archives)


def download_file(url: str, dest: Path, *, proxy: str = "") -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(
        url, stream=True, proxies=_proxy_dict(proxy), timeout=120
    ) as resp:
        resp.raise_for_status()
        with dest.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)


def _github_software_asset(channel: str, proxy: str = "") -> tuple[str, str, str]:
    """Return (version, download_url, filename) for current host."""
    import platform
    import re

    summary = requests.get(
        f"{MAA_VERSION_API}/summary.json", proxies=_proxy_dict(proxy), timeout=30
    )
    summary.raise_for_status()
    detail_url = summary.json()[channel or "stable"]["detail"]
    detail = requests.get(detail_url, proxies=_proxy_dict(proxy), timeout=30)
    detail.raise_for_status()
    data = detail.json()
    version = str(data.get("version") or "")
    system = platform.system()
    machine = platform.machine()
    if system == "Linux":
        platform_tag = "linux-aarch64" if machine == "aarch64" else "linux-x86_64"
    elif system == "Windows":
        platform_tag = "win-x64" if machine in ("AMD64", "x86_64") else "win-arm64"
    else:
        raise RuntimeError("该平台不支持 GitHub 软件更新源")
    pattern = re.compile(rf"^MAA-.*-{re.escape(platform_tag)}\.(zip|tar\.gz)$")
    for asset in data.get("details", {}).get("assets", []):
        name = asset.get("name") or ""
        if pattern.match(name):
            mirrors = list(asset.get("mirrors") or [])
            mirrors.append(asset.get("browser_download_url") or "")
            for url in mirrors:
                if url:
                    return version, url, name
    raise RuntimeError("未找到适用于当前系统的更新包")


def download_software_to_pending(
    *,
    maa_path: str | Path,
    software_version: str,
    source: str,
    channel: str,
    cdk: str,
    proxy: str,
    system: str | None = None,
) -> dict[str, Any]:
    system = system or __system__
    source = _resolve_source(source, system)
    pending = pending_update_dir(maa_path)
    if has_pending_update(maa_path):
        return {
            "status": "already_pending",
            "message": "已下载，重启 mower 后生效",
            "pending_apply": True,
        }

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
        code = _safe_int(data.get("code") or 0)
        if code != 0:
            return {"status": "failed", "message": cdk_error_message(code)}
        payload = data.get("data") or {}
        remote = str(payload.get("version_name") or "")
        if not version_is_newer(remote, software_version):
            return {
                "status": "already_latest",
                "message": "已经是最新版本",
                "latest_version": remote or software_version,
            }
        url = payload.get("url") or ""
        if not url:
            return {
                "status": "failed",
                "message": "有更新但未获取到下载地址（请检查 CDK）",
            }
        filename = f"MirrorChyanApp{remote}.zip"
    else:
        remote, url, filename = _github_software_asset(channel or "stable", proxy)
        if not version_is_newer(remote, software_version):
            return {
                "status": "already_latest",
                "message": "已经是最新版本",
                "latest_version": remote or software_version,
            }

    import shutil

    if pending.exists():
        try:
            shutil.rmtree(pending)
        except OSError:
            shutil.rmtree(pending, ignore_errors=True)
    try:
        pending.mkdir(parents=True, exist_ok=True)
        dest = pending / filename
        download_file(url, dest, proxy=proxy)
        (pending / "meta.json").write_text(
            json.dumps(
                {"version": remote, "source": source, "filename": filename},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception as e:
        try:
            shutil.rmtree(pending)
        except OSError:
            shutil.rmtree(pending, ignore_errors=True)
        return {"status": "failed", "message": f"下载失败：{e}"}
    return {
        "status": "success",
        "message": f"软件 {remote} 已下载，重启 mower 后生效",
        "pending_apply": True,
        "latest_version": remote,
    }


def apply_changes_json(resource_root: Path, changes: dict[str, Any]) -> None:
    import shutil

    for key in ("deleted", "deleted_dir"):
        for rel in changes.get(key) or []:
            target = resource_root / str(rel).lstrip("/")
            if target.is_dir():
                try:
                    shutil.rmtree(target)
                except OSError:
                    pass
            elif target.exists():
                try:
                    target.unlink()
                except OSError:
                    pass


def _overlay_tree(src: Path, dst: Path) -> None:
    import shutil

    for path in src.rglob("*"):
        rel = path.relative_to(src)
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def apply_resource_package(zip_path: Path, maa_path: str | Path) -> None:
    import tempfile
    import zipfile

    maa_path = Path(maa_path)
    resource_root = maa_path / "resource"
    with tempfile.TemporaryDirectory(prefix="maa_res_") as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_path)
        # locate resource/ and optional changes.json
        changes_file = next(tmp_path.rglob("changes.json"), None)
        resource_src = next((p for p in tmp_path.rglob("resource") if p.is_dir()), None)
        if changes_file and changes_file.is_file():
            try:
                changes = json.loads(changes_file.read_text(encoding="utf-8"))
            except Exception:
                changes = {}
            apply_changes_json(maa_path, changes)
        if resource_src is None:
            # package root is the resource content itself
            resource_src = tmp_path
            # if single top-level dir like MaaResource-main/resource
            children = [p for p in tmp_path.iterdir() if p.is_dir()]
            if len(children) == 1 and (children[0] / "resource").is_dir():
                resource_src = children[0] / "resource"
            elif len(children) == 1 and not changes_file:
                # MaaResource-main style where resource files live under resource/
                maybe = children[0] / "resource"
                if maybe.is_dir():
                    resource_src = maybe
        if resource_src and resource_src.is_dir():
            resource_root.mkdir(parents=True, exist_ok=True)
            _overlay_tree(resource_src, resource_root)
        elif changes_file is None:
            raise RuntimeError("资源包中未找到 resource 目录")


def download_and_apply_resource(
    *,
    maa_path: str | Path,
    source: str,
    cdk: str,
    proxy: str,
    system: str | None = None,
) -> dict[str, Any]:
    import tempfile
    from pathlib import Path as P

    system = system or __system__
    source = _resolve_source(source, system)
    local = read_resource_version(maa_path)

    if source == "mirrorchyan":
        data = _mirrorchyan_latest(
            "MaaResource",
            current_version=local,
            cdk=cdk,
            proxy=proxy,
        )
        code = _safe_int(data.get("code") or 0)
        if code != 0:
            return {"status": "failed", "message": cdk_error_message(code)}
        payload = data.get("data") or {}
        remote = str(payload.get("version_name") or "")
        if not version_is_newer(remote, local):
            return {
                "status": "already_latest",
                "message": "已经是最新版本",
                "latest_version": remote or local,
            }
        url = payload.get("url") or ""
        if not url:
            return {
                "status": "failed",
                "message": "有更新但未获取到下载地址（请检查 CDK）",
            }
    else:
        # GitHub full resource zip has no version compare; still report success after apply
        remote = "github-main"
        url = GITHUB_RESOURCE_ZIP

    with tempfile.TemporaryDirectory(prefix="maa_res_dl_") as tmp:
        zip_path = P(tmp) / "resource.zip"
        download_file(url, zip_path, proxy=proxy)
        apply_resource_package(zip_path, maa_path)

    return {
        "status": "success",
        "message": f"资源已更新到 {remote}",
        "latest_version": remote,
    }


def apply_pending_software(maa_path: str | Path) -> dict[str, Any]:
    """Extract pending software package over maa_path, keep config/data."""
    import shutil
    import tarfile
    import tempfile
    import zipfile

    maa_path = Path(maa_path)
    pending = pending_update_dir(maa_path)
    if not pending.is_dir():
        return {"status": "skipped", "message": "无待应用的软件更新"}

    archives = [
        p
        for p in pending.iterdir()
        if p.suffix in {".zip", ".gz"} or p.name.endswith(".tar.gz")
    ]
    if not archives:
        return {"status": "failed", "message": "pending 目录中无软件包"}

    archive = archives[0]
    preserve = {"config", "data", PENDING_DIRNAME}
    try:
        with tempfile.TemporaryDirectory(prefix="maa_sw_") as tmp:
            tmp_path = Path(tmp)
            if archive.suffix == ".zip":
                with zipfile.ZipFile(archive, "r") as zf:
                    zf.extractall(tmp_path)
            else:
                with tarfile.open(archive, "r:gz") as tf:
                    tf.extractall(tmp_path)

            # if single top-level folder, use it as package root
            children = list(tmp_path.iterdir())
            root = (
                children[0] if len(children) == 1 and children[0].is_dir() else tmp_path
            )

            for item in root.iterdir():
                if item.name in preserve:
                    continue
                target = maa_path / item.name
                if item.is_dir():
                    if target.exists():
                        shutil.rmtree(target, ignore_errors=True)
                    shutil.copytree(item, target)
                else:
                    shutil.copy2(item, target)

        shutil.rmtree(pending, ignore_errors=True)
        return {"status": "success", "message": "软件更新已应用"}
    except Exception as e:
        logger.exception(f"应用 pending 软件包失败：{e}")
        return {"status": "failed", "message": f"应用失败：{e}"}


def run_update_action(
    kind: str,
    *,
    maa_path: str | Path,
    software_version: str,
    source: str,
    channel: str,
    cdk: str,
    proxy: str,
    system: str | None = None,
) -> dict[str, Any]:
    kind = (kind or "").strip().lower()
    if kind == "software":
        return download_software_to_pending(
            maa_path=maa_path,
            software_version=software_version,
            source=source,
            channel=channel,
            cdk=cdk,
            proxy=proxy,
            system=system,
        )
    if kind == "resource":
        return download_and_apply_resource(
            maa_path=maa_path,
            source=source,
            cdk=cdk,
            proxy=proxy,
            system=system,
        )
    return {"status": "failed", "message": f"未知更新类型：{kind}"}


# subprocess entry (mirrors maa_check pattern)
MAA_UPDATE_SCRIPT = r"""
import json
import pathlib
import sys

params = json.loads(sys.argv[1])
result = {"status": "failed", "message": "unknown"}
try:
    # import from installed mower package if available; else load sibling path
    try:
        from arknights_mower.utils import maa_update as mu
    except Exception:
        sys.path.insert(0, params.get("mower_root", ""))
        from arknights_mower.utils import maa_update as mu

    action = params.get("action", "check")
    maa_path = params["maa_path"]
    source = params.get("source", "github")
    channel = params.get("channel", "stable")
    cdk = params.get("cdk", "")
    proxy = params.get("proxy", "")
    software_version = params.get("software_version", "")

    if not software_version:
        # best-effort version via Asst in this subprocess
        try:
            p = pathlib.Path(maa_path)
            sys.path.append(str(p / "Python"))
            from asst.asst import Asst

            Asst.load(str(p))
            software_version = Asst().get_version()
        except Exception as e:
            software_version = ""
            if action != "resource":
                raise RuntimeError(f"读取 MAA 版本失败：{e}") from e

    if action == "check":
        checked = mu.check_updates(
            maa_path=maa_path,
            software_version=software_version,
            source=source,
            channel=channel,
            cdk=cdk,
            proxy=proxy,
        )
        result = {"status": "success", "message": "检查完成", **checked}
    elif action in ("software", "resource"):
        result = mu.run_update_action(
            action,
            maa_path=maa_path,
            software_version=software_version,
            source=source,
            channel=channel,
            cdk=cdk,
            proxy=proxy,
        )
    else:
        result = {"status": "failed", "message": f"未知 action: {action}"}
except Exception as e:
    result = {"status": "failed", "message": str(e)}

print(json.dumps(result, ensure_ascii=False))
"""


def maa_update_params(
    action: str,
    *,
    software_version: str = "",
) -> dict[str, str]:
    from arknights_mower.utils import config

    return {
        "action": action,
        "maa_path": str(config.conf.maa_path),
        "source": str(getattr(config.conf, "maa_update_source", "github")),
        "channel": str(getattr(config.conf, "maa_update_channel", "stable")),
        "cdk": str(getattr(config.conf, "maa_mirrorchyan_cdk", "")),
        "proxy": str(getattr(config.conf, "maa_update_proxy", "")),
        "software_version": software_version,
        "mower_root": str(Path(__file__).resolve().parents[2]),
    }


def maa_update_command(params: dict[str, str] | None = None) -> list[str]:
    import sys

    return [
        sys.executable,
        "-c",
        MAA_UPDATE_SCRIPT,
        json.dumps(params or maa_update_params("check"), ensure_ascii=False),
    ]


def parse_maa_update_output(
    stdout: str, stderr: str = "", returncode: int | None = None
) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        try:
            result = json.loads(line)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
    message = "MAA更新进程异常退出"
    if returncode is not None:
        message += f"：{returncode}"
    if stderr.strip():
        message += f"，{stderr.strip().splitlines()[-1]}"
    return {"status": "failed", "message": message}
