import unittest

import httpx

from scripts.verify_feishu_deploy import assert_iframe_allowed, frame_ancestor_sources


class VerifyFeishuDeployTest(unittest.TestCase):
    def test_iframe_check_allows_default_response_headers(self):
        response = httpx.Response(200, headers={})

        assert_iframe_allowed(response, "home")

    def test_iframe_check_blocks_x_frame_options(self):
        response = httpx.Response(200, headers={"X-Frame-Options": "SAMEORIGIN"})

        with self.assertRaisesRegex(AssertionError, "X-Frame-Options"):
            assert_iframe_allowed(response, "home")

    def test_iframe_check_blocks_restrictive_frame_ancestors(self):
        response = httpx.Response(200, headers={"Content-Security-Policy": "default-src 'self'; frame-ancestors 'self'"})

        with self.assertRaisesRegex(AssertionError, "frame-ancestors"):
            assert_iframe_allowed(response, "home")

    def test_iframe_check_allows_feishu_frame_ancestor_hint(self):
        response = httpx.Response(200, headers={"Content-Security-Policy": "frame-ancestors https://*.feishu.cn"})

        assert_iframe_allowed(response, "home")

    def test_frame_ancestor_sources_extracts_directive(self):
        sources = frame_ancestor_sources("default-src 'self'; frame-ancestors https://*.feishu.cn https://*.larksuite.com")

        self.assertEqual(sources, ["https://*.feishu.cn", "https://*.larksuite.com"])


if __name__ == "__main__":
    unittest.main()
