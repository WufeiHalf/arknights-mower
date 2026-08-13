import json
import subprocess
import sys

from arknights_mower import __system__
from arknights_mower.utils import config

MAA_CHECK_TIMEOUT = 30

# 黑流树海刷钱（牛杂 OTA 入口）要求的最低 MAA 版本
MAA_BLACKFLOW_MIN_VERSION = (6, 14, 0)
# 黑流树海刷钱任务链入口（OTA 下发，含 Begin/StartExplore/投资等 35 步）
BLACKFLOW_TASK_NAME = "BlackFlowTemporary@Begin"

MAA_CHECK_SCRIPT = r"""
import json
import pathlib
import sys

params = json.loads(sys.argv[1])
try:
    maa_path = pathlib.Path(params["maa_path"])
    asst_path = str(maa_path / "Python")
    # Prefer asst bundled with maa_path. site-packages may ship a shim;
    # append would keep importing the old one and break connect.
    if asst_path in sys.path:
        sys.path.remove(asst_path)
    sys.path.insert(0, asst_path)
    for module_name in list(sys.modules):
        if module_name == "asst" or module_name.startswith("asst."):
            module_file = getattr(sys.modules[module_name], "__file__", "") or ""
            if not module_file.startswith(asst_path):
                del sys.modules[module_name]

    from asst.asst import Asst

    def callback(msg, details, arg):
        pass

    callback_func = Asst.CallBackType(callback)
    Asst.load(path=maa_path, incremental_path=maa_path / "cache")
    asst = Asst(callback=callback_func)
    version = asst.get_version()
    asst.set_instance_option(2, params["maa_touch_option"])
    if asst.connect(params["maa_adb_path"], params["adb"], params["maa_conn_preset"]):
        result = {"status": "success", "message": f"Maa {version} 连接成功"}
    else:
        result = {
            "status": "connection_failed",
            "message": "连接失败，请检查Maa日志！",
        }
except Exception as e:
    result = {"status": "error", "message": "Maa测试异常：" + str(e)}

print(json.dumps(result, ensure_ascii=False))
"""


def maa_check_params(adb: str | None = None) -> dict[str, str]:
    return {
        "maa_path": str(config.conf.maa_path),
        "maa_adb_path": str(config.conf.maa_adb_path),
        "adb": str(config.conf.adb if adb is None else adb),
        "maa_conn_preset": str(config.conf.maa_conn_preset),
        "maa_touch_option": str(config.conf.maa_touch_option),
    }


def maa_check_command(params: dict[str, str] | None = None) -> list[str]:
    return [
        sys.executable,
        "-c",
        MAA_CHECK_SCRIPT,
        json.dumps(params or maa_check_params(), ensure_ascii=False),
    ]


def parse_maa_check_output(
    stdout: str, stderr: str = "", returncode: int | None = None
) -> dict[str, str]:
    for line in reversed(stdout.splitlines()):
        try:
            result = json.loads(line)
            return {
                "status": result.get("status", "error"),
                "message": result.get("message", ""),
            }
        except json.JSONDecodeError:
            pass

    message = "Maa测试进程异常退出"
    if returncode is not None:
        message += f"：{returncode}"
    if stderr.strip():
        message += f"，{stderr.strip().splitlines()[-1]}"
    return {"status": "error", "message": message}


def maa_check_timeout_result(timeout: int = MAA_CHECK_TIMEOUT) -> dict[str, str]:
    return {
        "status": "timeout",
        "message": f"Maa连通性测试超时（{timeout}秒），已终止测试进程",
    }


def run_maa_connectivity_check(
    timeout: int = MAA_CHECK_TIMEOUT,
    adb: str | None = None,
) -> dict[str, str]:
    subprocess_options: dict[str, int | bool]
    if __system__ == "windows":
        # Windows 由 CreateProcess 创建检测器，并隐藏控制台窗口。
        subprocess_options = {"creationflags": subprocess.CREATE_NO_WINDOW}
    else:
        # 长期运行的 Mower 已加载 Maa/OpenCV 等原生库，不应再通过 fork
        # 派生检测器。POSIX 会因此走 posix_spawn；Python 文件描述符默认
        # 不可继承。
        subprocess_options = {"close_fds": False}

    try:
        result = subprocess.run(
            maa_check_command(maa_check_params(adb)),
            capture_output=True,
            text=True,
            timeout=timeout,
            **subprocess_options,
        )
    except subprocess.TimeoutExpired:
        return maa_check_timeout_result(timeout)
    except Exception as e:
        return {"status": "error", "message": "Maa测试启动失败：" + str(e)}

    return parse_maa_check_output(result.stdout, result.stderr, result.returncode)


def is_maa_connectivity_check_enabled() -> bool:
    return bool(config.conf.maa_startup_check)


def parse_maa_version(version_str: str) -> tuple[int, int, int]:
    """解析 "v6.14.2" 风格 MAA 版本号为 (6, 14, 2)。

    alpha/beta 通道版本号形如 "v6.16.9-alpha.1.d013.g66018a451f"（`-` 后缀
    附着在第 3 段），取前 3 段数字，其余构建信息忽略；不足 3 段或前 3 段
    含非数字段抛 ValueError。
    """
    text = version_str.strip()
    if text.startswith("v"):
        text = text[1:]
    parts = text.replace("-", ".").split(".")[:3]
    if len(parts) != 3:
        raise ValueError(f"无法解析 MAA 版本号：{version_str!r}")
    try:
        major, minor, patch = (int(part) for part in parts)
    except ValueError:
        raise ValueError(f"无法解析 MAA 版本号：{version_str!r}") from None
    return major, minor, patch


def check_blackflow_version(version: tuple[int, int, int]) -> None:
    """MAA 版本低于 v6.14.0 时抛异常（黑流树海刷钱依赖该版本引入的牛杂入口）。"""
    if version < MAA_BLACKFLOW_MIN_VERSION:
        current = ".".join(str(part) for part in version)
        raise Exception(f"黑流树海刷钱需要 MAA ≥ v6.14.0，当前 {current}，请升级 MAA")


def check_blackflow_tasks(tasks_json_path) -> None:
    """本地 MAA 资源 tasks.json 缺少 BlackFlowTemporary 任务链时抛异常。"""
    try:
        with open(tasks_json_path, "r", encoding="utf-8") as f:
            tasks = json.load(f)
    except json.JSONDecodeError as e:
        raise Exception(
            f"MAA 资源 tasks.json 解析失败（{tasks_json_path}）：{e}，请更新 MAA 资源"
        ) from e
    except OSError as e:
        raise Exception(
            f"MAA 资源 tasks.json 读取失败（{tasks_json_path}）：{e}，请更新 MAA 资源"
        ) from e
    if not isinstance(tasks, dict) or BLACKFLOW_TASK_NAME not in tasks:
        raise Exception("MAA 资源未包含 BlackFlowTemporary 任务链，请更新 MAA 资源")


def check_blackflow_prereqs(maa_version: tuple[int, int, int], tasks_json_path) -> None:
    """黑流树海刷钱启动前预检：MAA 版本 + 任务链存在性，任一不满足即报错。"""
    check_blackflow_version(maa_version)
    check_blackflow_tasks(tasks_json_path)
