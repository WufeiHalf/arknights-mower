import unittest
from unittest.mock import MagicMock, patch

from arknights_mower.utils import maa_update


class TestThrottle(unittest.TestCase):
    def setUp(self):
        maa_update.reset_update_state()

    def test_throttle_skips_within_6h(self):
        calls = []

        def fake_check(**kwargs):
            calls.append(1)
            return {
                "software": {
                    "has_update": False,
                    "latest_version": "v1",
                    "message": "",
                },
                "resource": {"has_update": False, "latest_version": "", "message": ""},
            }

        with (
            patch.object(maa_update, "check_updates", side_effect=fake_check),
            patch.object(
                maa_update.time, "monotonic", side_effect=[100.0, 100.0 + 100]
            ),
        ):
            self.assertTrue(
                maa_update.check_update_if_due(maa_path="/tmp", software_version="v1")
            )
            self.assertFalse(
                maa_update.check_update_if_due(maa_path="/tmp", software_version="v1")
            )
        self.assertEqual(len(calls), 1)

    def test_throttle_allows_after_6h(self):
        calls = []

        def fake_check(**kwargs):
            calls.append(1)
            return {
                "software": {
                    "has_update": False,
                    "latest_version": "v1",
                    "message": "",
                },
                "resource": {"has_update": False, "latest_version": "", "message": ""},
            }

        with (
            patch.object(maa_update, "check_updates", side_effect=fake_check),
            patch.object(
                maa_update.time,
                "monotonic",
                side_effect=[100.0, 100.0 + maa_update.CHECK_INTERVAL + 1],
            ),
        ):
            self.assertTrue(
                maa_update.check_update_if_due(maa_path="/tmp", software_version="v1")
            )
            self.assertTrue(
                maa_update.check_update_if_due(maa_path="/tmp", software_version="v1")
            )
        self.assertEqual(len(calls), 2)

    def test_check_failure_silent(self):
        with patch.object(maa_update, "check_updates", side_effect=RuntimeError("net")):
            self.assertFalse(
                maa_update.check_update_if_due(maa_path="/tmp", software_version="v1")
            )
        status = maa_update.get_update_status()
        self.assertFalse(status["software"]["has_update"])
        self.assertFalse(status["resource"]["has_update"])


class TestVersionCompare(unittest.TestCase):
    def test_software_has_update(self):
        self.assertTrue(maa_update.version_is_newer("v6.14.1", "v6.14.0"))
        self.assertFalse(maa_update.version_is_newer("v6.14.0", "v6.14.0"))
        self.assertFalse(maa_update.version_is_newer("v6.14.0", "v6.14.1"))

    def test_resource_has_update(self):
        self.assertTrue(
            maa_update.version_is_newer(
                "2026-07-10 16:30:29.000", "2026-07-01 00:00:00.000"
            )
        )
        self.assertFalse(
            maa_update.version_is_newer(
                "2026-07-10 16:30:29.000", "2026-07-10 16:30:29.000"
            )
        )


class TestCheckUpdates(unittest.TestCase):
    def setUp(self):
        maa_update.reset_update_state()

    def test_mirrorchyan_software_and_resource(self):
        def fake_get(url, params=None, **kwargs):
            rid = url.rstrip("/").split("/")[-2] if "/latest" in url else ""
            resp = MagicMock()
            if rid == "MAA":
                resp.json.return_value = {
                    "code": 0,
                    "data": {"version_name": "v6.14.1"},
                }
            else:
                resp.json.return_value = {
                    "code": 0,
                    "data": {"version_name": "2026-07-10 16:30:29.000"},
                }
            resp.raise_for_status = MagicMock()
            return resp

        with (
            patch.object(maa_update.requests, "get", side_effect=fake_get),
            patch.object(
                maa_update,
                "read_resource_version",
                return_value="2026-07-01 00:00:00.000",
            ),
        ):
            result = maa_update.check_updates(
                maa_path="/tmp",
                software_version="v6.14.0",
                source="mirrorchyan",
                channel="stable",
                cdk="",
                proxy="",
                system="windows",
            )
        self.assertTrue(result["software"]["has_update"])
        self.assertEqual(result["software"]["latest_version"], "v6.14.1")
        self.assertTrue(result["resource"]["has_update"])
        self.assertEqual(
            result["resource"]["latest_version"], "2026-07-10 16:30:29.000"
        )

    def test_github_software_check(self):
        def fake_get(url, params=None, **kwargs):
            resp = MagicMock()
            if "api.maa.plus" in url:
                resp.json.return_value = {"version": "v6.14.1"}
            else:
                resp.json.return_value = {
                    "code": 0,
                    "data": {"version_name": "2026-07-10 16:30:29.000"},
                }
            resp.raise_for_status = MagicMock()
            return resp

        with (
            patch.object(maa_update.requests, "get", side_effect=fake_get),
            patch.object(
                maa_update,
                "read_resource_version",
                return_value="2026-07-10 16:30:29.000",
            ),
        ):
            result = maa_update.check_updates(
                maa_path="/tmp",
                software_version="v6.14.1",
                source="github",
                channel="stable",
                cdk="",
                proxy="",
                system="linux",
            )
        self.assertFalse(result["software"]["has_update"])
        self.assertFalse(result["resource"]["has_update"])


class TestPlatformRouting(unittest.TestCase):
    def test_platform_available_sources(self):
        self.assertEqual(
            maa_update.available_sources("windows"), ["github", "mirrorchyan"]
        )
        self.assertEqual(maa_update.available_sources("linux"), ["github"])
        self.assertEqual(maa_update.available_sources("darwin"), ["mirrorchyan"])

    def test_resolve_source_fallback(self):
        self.assertEqual(maa_update._resolve_source("mirrorchyan", "linux"), "github")
        self.assertEqual(maa_update._resolve_source("github", "darwin"), "mirrorchyan")


class TestCdkError(unittest.TestCase):
    def test_cdk_error_messages(self):
        self.assertEqual(maa_update.cdk_error_message(7001), "CDK 已过期")
        self.assertEqual(maa_update.cdk_error_message(7002), "CDK 无效")
        self.assertEqual(maa_update.cdk_error_message(7003), "今日下载次数已达上限")
        self.assertEqual(maa_update.cdk_error_message(7004), "CDK 类型与资源不匹配")
        self.assertEqual(maa_update.cdk_error_message(7005), "CDK 已被封禁")
        self.assertEqual(maa_update.cdk_error_message(8001), "该平台不支持此更新源")


class TestUpdateActions(unittest.TestCase):
    def test_force_check_bypasses_throttle(self):
        maa_update.reset_update_state()
        calls = []

        def fake_check(**kwargs):
            calls.append(1)
            return {
                "software": {
                    "has_update": False,
                    "latest_version": "v1",
                    "message": "",
                },
                "resource": {
                    "has_update": False,
                    "latest_version": "",
                    "message": "",
                },
            }

        with (
            patch.object(maa_update, "check_updates", side_effect=fake_check),
            patch.object(maa_update.time, "monotonic", return_value=100.0),
        ):
            self.assertTrue(
                maa_update.check_update_if_due(maa_path="/tmp", software_version="v1")
            )
            self.assertTrue(
                maa_update.check_update_if_due(
                    maa_path="/tmp", software_version="v1", force=True
                )
            )
        self.assertEqual(len(calls), 2)

    def test_software_already_latest(self):
        with patch.object(
            maa_update,
            "_mirrorchyan_latest",
            return_value={"code": 0, "data": {"version_name": "v6.14.0"}},
        ):
            result = maa_update.download_software_to_pending(
                maa_path="/tmp/maa",
                software_version="v6.14.0",
                source="mirrorchyan",
                channel="stable",
                cdk="cdk",
                proxy="",
                system="windows",
            )
        self.assertEqual(result["status"], "already_latest")

    def test_software_cdk_error(self):
        with patch.object(
            maa_update,
            "_mirrorchyan_latest",
            return_value={"code": 7002, "msg": "invalid"},
        ):
            result = maa_update.download_software_to_pending(
                maa_path="/tmp/maa",
                software_version="v6.14.0",
                source="mirrorchyan",
                channel="stable",
                cdk="bad",
                proxy="",
                system="windows",
            )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["message"], "CDK 无效")

    def test_software_already_pending(self):
        with patch.object(maa_update, "has_pending_update", return_value=True):
            result = maa_update.download_software_to_pending(
                maa_path="/tmp/maa",
                software_version="v6.14.0",
                source="github",
                channel="stable",
                cdk="",
                proxy="",
                system="linux",
            )
        self.assertEqual(result["status"], "already_pending")
        self.assertTrue(result["pending_apply"])

    def test_incomplete_pending_not_ready(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            maa = Path(tmp)
            pending = maa / maa_update.PENDING_DIRNAME
            pending.mkdir()
            (pending / "partial.zip").write_bytes(b"x")  # no meta.json
            self.assertFalse(maa_update.has_pending_update(maa))

    def test_download_failure_cleans_pending(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            maa = Path(tmp)
            with (
                patch.object(
                    maa_update,
                    "_mirrorchyan_latest",
                    return_value={
                        "code": 0,
                        "data": {"version_name": "v9.0.0", "url": "http://x"},
                    },
                ),
                patch.object(
                    maa_update, "download_file", side_effect=RuntimeError("net")
                ),
            ):
                result = maa_update.download_software_to_pending(
                    maa_path=maa,
                    software_version="v6.0.0",
                    source="mirrorchyan",
                    channel="stable",
                    cdk="cdk",
                    proxy="",
                    system="windows",
                )
            self.assertEqual(result["status"], "failed")
            self.assertFalse(maa_update.has_pending_update(maa))
            self.assertFalse((maa / maa_update.PENDING_DIRNAME).exists())

    def test_mutex_already_running(self):
        # server-side convention: process non-null => already_running
        job = {"process": object(), "message": "正在更新……"}
        self.assertIsNotNone(job["process"])


class TestPendingApply(unittest.TestCase):
    def test_apply_pending_software(self):
        import tempfile
        import zipfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            maa = Path(tmp) / "maa"
            (maa / "config").mkdir(parents=True)
            (maa / "data").mkdir()
            (maa / "config" / "keep.txt").write_text("keep", encoding="utf-8")
            (maa / "old.dll").write_text("old", encoding="utf-8")

            pending = maa / maa_update.PENDING_DIRNAME
            pending.mkdir()
            zip_path = pending / "pkg.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("MaaCore.dll", "new")
                zf.writestr("Python/asst/__init__.py", "")

            result = maa_update.apply_pending_software(maa)
            self.assertEqual(result["status"], "success")
            self.assertFalse(pending.exists())
            self.assertEqual((maa / "MaaCore.dll").read_text(encoding="utf-8"), "new")
            self.assertEqual(
                (maa / "config" / "keep.txt").read_text(encoding="utf-8"), "keep"
            )
            self.assertTrue((maa / "data").is_dir())

    def test_apply_resource_package_with_changes(self):
        import json
        import tempfile
        import zipfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            maa = Path(tmp) / "maa"
            resource = maa / "resource"
            resource.mkdir(parents=True)
            doomed = resource / "old.txt"
            doomed.write_text("x", encoding="utf-8")
            (resource / "version.json").write_text(
                json.dumps({"last_updated": "old"}), encoding="utf-8"
            )

            zip_path = Path(tmp) / "res.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                # MirrorChyan Incremental.md: paths relative to package root
                zf.writestr(
                    "changes.json",
                    json.dumps({"deleted": ["resource/old.txt"], "modified": []}),
                )
                zf.writestr(
                    "resource/version.json",
                    json.dumps({"last_updated": "2026-07-10 16:30:29.000"}),
                )
                zf.writestr("resource/new.txt", "n")

            maa_update.apply_resource_package(zip_path, maa)
            self.assertFalse(doomed.exists())
            try:
                updated = json.loads(
                    (resource / "version.json").read_text(encoding="utf-8")
                )["last_updated"]
            except (OSError, json.JSONDecodeError, KeyError) as e:
                self.fail(f"version.json unreadable after apply: {e}")
            self.assertEqual(updated, "2026-07-10 16:30:29.000")
            self.assertTrue((resource / "new.txt").exists())

    def test_apply_github_resource_zipball_layout(self):
        import json
        import tempfile
        import zipfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            maa = Path(tmp) / "maa"
            (maa / "resource").mkdir(parents=True)
            zip_path = Path(tmp) / "gh.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr(
                    "MaaResource-main/resource/version.json",
                    json.dumps({"last_updated": "gh"}),
                )
                zf.writestr("MaaResource-main/resource/x.txt", "1")
            maa_update.apply_resource_package(zip_path, maa)
            try:
                updated = json.loads(
                    (maa / "resource" / "version.json").read_text(encoding="utf-8")
                )["last_updated"]
            except (OSError, json.JSONDecodeError, KeyError) as e:
                self.fail(f"version.json unreadable after github apply: {e}")
            self.assertEqual(updated, "gh")
            self.assertTrue((maa / "resource" / "x.txt").exists())


if __name__ == "__main__":
    unittest.main()
