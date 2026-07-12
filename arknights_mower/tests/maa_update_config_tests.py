import unittest

from arknights_mower.utils.config.conf import Conf, MaaPart
from arknights_mower.utils.maa_update import available_sources


class TestMaaUpdateConfig(unittest.TestCase):
    def test_maa_part_defaults(self):
        part = MaaPart()
        self.assertEqual(part.maa_update_source, "github")
        self.assertEqual(part.maa_update_channel, "stable")
        self.assertEqual(part.maa_mirrorchyan_cdk, "")
        self.assertEqual(part.maa_update_proxy, "")

    def test_conf_roundtrip(self):
        conf = Conf(
            maa_update_source="mirrorchyan",
            maa_update_channel="beta",
            maa_mirrorchyan_cdk="cdk-test",
            maa_update_proxy="http://127.0.0.1:7890",
        )
        dumped = conf.model_dump()
        self.assertEqual(dumped["maa_update_source"], "mirrorchyan")
        self.assertEqual(dumped["maa_update_channel"], "beta")
        self.assertEqual(dumped["maa_mirrorchyan_cdk"], "cdk-test")
        self.assertEqual(dumped["maa_update_proxy"], "http://127.0.0.1:7890")

        restored = Conf(**dumped)
        self.assertEqual(restored.maa_update_source, "mirrorchyan")
        self.assertEqual(restored.maa_update_channel, "beta")
        self.assertEqual(restored.maa_mirrorchyan_cdk, "cdk-test")
        self.assertEqual(restored.maa_update_proxy, "http://127.0.0.1:7890")

    def test_available_sources_by_platform(self):
        self.assertEqual(
            available_sources("windows"),
            ["github", "mirrorchyan"],
        )
        self.assertEqual(available_sources("linux"), ["github"])
        self.assertEqual(available_sources("darwin"), ["mirrorchyan"])


if __name__ == "__main__":
    unittest.main()
