# -*- coding: utf-8 -*-
import unittest
from unittest import mock

from vehelper import release


class TestProxy(unittest.TestCase):
    def test_proxy_none(self):
        with mock.patch.object(release.socket, "create_connection",
                               side_effect=OSError):
            self.assertEqual(release.detect_proxy(), "")


if __name__ == "__main__":
    unittest.main()
