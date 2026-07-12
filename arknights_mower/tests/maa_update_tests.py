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


if __name__ == "__main__":
    unittest.main()
