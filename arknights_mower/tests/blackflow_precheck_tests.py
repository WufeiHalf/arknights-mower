import json
import os
import tempfile
import unittest

from arknights_mower.utils.config.conf import Conf
from arknights_mower.utils.maa_check import (
    check_blackflow_prereqs,
    check_blackflow_tasks,
    check_blackflow_version,
    parse_maa_version,
)


def make_conf(rg_enable: int, long_task_type: str) -> Conf:
    return Conf.model_construct(
        maa_rg_enable=rg_enable, maa_long_task_type=long_task_type
    )


class TestConfBF(unittest.TestCase):
    def test_enabled_bf_type(self):
        self.assertTrue(make_conf(1, "bf").BF)

    def test_disabled_bf_type(self):
        self.assertFalse(make_conf(0, "bf").BF)

    def test_enabled_other_type(self):
        self.assertFalse(make_conf(1, "rogue").BF)

    def test_bf_does_not_affect_other_long_tasks(self):
        conf = make_conf(1, "bf")

        self.assertTrue(conf.BF)
        self.assertFalse(conf.RG)
        self.assertFalse(conf.SSS)
        self.assertFalse(conf.RA)
        self.assertFalse(conf.SF)
        self.assertFalse(conf.RCL)


class TestParseMaaVersion(unittest.TestCase):
    def test_parses_v_prefixed_version(self):
        self.assertEqual(parse_maa_version("v6.14.2"), (6, 14, 2))

    def test_parses_plain_version(self):
        self.assertEqual(parse_maa_version("6.14.2"), (6, 14, 2))

    def test_parses_alpha_version_with_build_suffix(self):
        self.assertEqual(
            parse_maa_version("v6.16.9-alpha.1.d013.g66018a451f"), (6, 16, 9)
        )

    def test_parses_beta_version(self):
        self.assertEqual(parse_maa_version("v6.13.0-beta.2"), (6, 13, 0))

    def test_parses_version_with_extra_numeric_segments(self):
        # alpha/beta 格式第 4 段起为构建信息，多余数字段应被忽略
        self.assertEqual(parse_maa_version("v6.14.2.1"), (6, 14, 2))

    def test_invalid_version_raises(self):
        for bad in ["", "v6", "6.14", "abc", "6.14.x"]:
            with self.assertRaises(ValueError):
                parse_maa_version(bad)


class TestCheckBlackflowVersion(unittest.TestCase):
    def test_minimum_version_passes(self):
        check_blackflow_version(parse_maa_version("v6.14.0"))

    def test_older_version_raises(self):
        with self.assertRaisesRegex(Exception, "MAA ≥ v6.14.0"):
            check_blackflow_version(parse_maa_version("v6.13.9"))


class TestCheckBlackflowTasks(unittest.TestCase):
    def _write_json_file(self, content: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        self.addCleanup(os.unlink, path)
        return path

    def test_begin_task_present_passes(self):
        path = self._write_json_file(json.dumps({"BlackFlowTemporary@Begin": {}}))

        check_blackflow_tasks(path)

    def test_missing_task_chain_raises_clear_error(self):
        path = self._write_json_file(json.dumps({"SomeOtherTask": {}}))

        with self.assertRaisesRegex(Exception, "更新 MAA 资源"):
            check_blackflow_tasks(path)

    def test_non_json_content_raises_clear_error(self):
        path = self._write_json_file("not a json {{{")

        with self.assertRaisesRegex(Exception, "更新 MAA 资源"):
            check_blackflow_tasks(path)

    def test_empty_file_raises_clear_error(self):
        path = self._write_json_file("")

        with self.assertRaisesRegex(Exception, "更新 MAA 资源"):
            check_blackflow_tasks(path)

    def test_missing_file_raises_clear_error(self):
        missing = "/nonexistent/maa/cache/resource/tasks.json"

        with self.assertRaisesRegex(Exception, "更新 MAA 资源"):
            check_blackflow_tasks(missing)


class TestCheckBlackflowPrereqs(unittest.TestCase):
    def _write_json_file(self, content: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        self.addCleanup(os.unlink, path)
        return path

    def test_insufficient_version_raises(self):
        path = self._write_json_file(json.dumps({"BlackFlowTemporary@Begin": {}}))

        with self.assertRaisesRegex(Exception, "MAA ≥ v6.14.0"):
            check_blackflow_prereqs((6, 13, 9), path)

    def test_missing_task_chain_raises(self):
        path = self._write_json_file(json.dumps({"SomeOtherTask": {}}))

        with self.assertRaisesRegex(Exception, "更新 MAA 资源"):
            check_blackflow_prereqs((6, 14, 0), path)

    def test_all_ok_passes(self):
        path = self._write_json_file(json.dumps({"BlackFlowTemporary@Begin": {}}))

        check_blackflow_prereqs((6, 14, 2), path)


if __name__ == "__main__":
    unittest.main()
