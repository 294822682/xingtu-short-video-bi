from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin

import httpx
from openpyxl import Workbook


EXPECTED_VIDEO_COUNT = 1
EXPECTED_EXPOSURE = 120000
EXPECTED_ACCOUNT_NAME = "抖音部署验证账号"
EXPECTED_ACTOR_COUNT = 2
EXPECTED_5S_DISPLAY = "23.0%"
FEISHU_FRAME_ANCESTOR_HINTS = (
    "*",
    "feishu.cn",
    "*.feishu.cn",
    "larksuite.com",
    "*.larksuite.com",
    "larkoffice.com",
    "*.larkoffice.com",
)


def absolute_url(base_url: str, path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def assert_response(response: httpx.Response, label: str) -> None:
    if response.status_code != 200:
        raise AssertionError(f"{label} expected 200, got {response.status_code}: {response.text[:300]}")


def frame_ancestor_sources(content_security_policy: str) -> list[str]:
    for directive in content_security_policy.split(";"):
        parts = directive.strip().split()
        if parts and parts[0].lower() == "frame-ancestors":
            return [part.lower() for part in parts[1:]]
    return []


def allows_feishu_frame_parent(sources: list[str]) -> bool:
    return any(any(hint in source for hint in FEISHU_FRAME_ANCESTOR_HINTS) for source in sources)


def assert_iframe_allowed(response: httpx.Response, label: str) -> None:
    x_frame_options = response.headers.get("x-frame-options", "").strip()
    if x_frame_options:
        raise AssertionError(
            f"{label} sets X-Frame-Options={x_frame_options!r}; Feishu iframe requires no X-Frame-Options blocker"
        )

    content_security_policy = response.headers.get("content-security-policy", "")
    sources = frame_ancestor_sources(content_security_policy)
    if sources and not allows_feishu_frame_parent(sources):
        raise AssertionError(
            f"{label} sets restrictive Content-Security-Policy frame-ancestors={sources}; "
            "allow the Feishu/Lark parent origin or remove the directive"
        )


def build_smoke_workbook() -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = EXPECTED_ACCOUNT_NAME
    sheet.append(["视频名称", "发布时间", "播放量", "5s完播率", "视频演员"])
    sheet.append(["飞书部署验证视频", "2026/6/8", EXPECTED_EXPOSURE, 0.23, "桂婕、曹嘉洋"])

    tmp = NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    path = Path(tmp.name)
    workbook.save(path)
    return path


def verify(base_url: str, upload: bool) -> dict[str, object]:
    results: dict[str, object] = {"base_url": base_url, "upload": upload}
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        health = client.get(absolute_url(base_url, "/api/health"))
        assert_response(health, "health")
        if health.json().get("status") != "ok":
            raise AssertionError(f"health status mismatch: {health.text}")
        results["health"] = "ok"

        for label, path in {
            "home": "/",
            "hub": "/hub",
            "xingtu": "/xingtu",
            "oae": "/oae",
            "admin": "/admin",
            "admin_xingtu": "/admin/xingtu",
            "admin_oae": "/admin/oae",
        }.items():
            page = client.get(absolute_url(base_url, path))
            assert_response(page, label)
            assert_iframe_allowed(page, label)
            if label == "oae":
                if "运营日报 BI" not in page.text or 'data-dashboard-mode="business"' not in page.text:
                    raise AssertionError("oae HTML should serve the original OAE operations daily BI shell")
            elif 'id="root"' not in page.text or "/assets/" not in page.text:
                raise AssertionError(f"{label} HTML missing React root or production asset path")
            results[label] = "ok"
        results["iframe_headers"] = "ok"

        modules = client.get(absolute_url(base_url, "/api/modules"))
        assert_response(modules, "modules")
        module_payload = modules.json()
        module_slugs = {item["slug"] for item in module_payload.get("modules", [])}
        if module_slugs != {"xingtu", "oae"}:
            raise AssertionError(f"module list mismatch: {module_payload}")
        results["modules"] = "ok"

        oae_overview = client.get(absolute_url(base_url, "/api/bi/oae/overview"))
        assert_response(oae_overview, "oae_overview")
        oae_payload = oae_overview.json()
        if oae_payload["overview"].get("module_status") != "ready":
            raise AssertionError("OAE should load dashboard source data")
        if oae_payload["overview"].get("source_contract") != "feishu_dashboard_source_tsv":
            raise AssertionError("OAE source contract mismatch")
        if not oae_payload.get("oae_dashboard", {}).get("lead_accounts"):
            raise AssertionError("OAE dashboard should include lead account rows")
        results["oae_dashboard_source"] = {
            "report_date": oae_payload["overview"].get("report_date"),
            "lead_accounts": len(oae_payload["oae_dashboard"]["lead_accounts"]),
        }

        oae_daily = client.get(absolute_url(base_url, "/dashboard/daily/latest"))
        assert_response(oae_daily, "oae_daily_latest")
        daily_payload = oae_daily.json()
        if daily_payload.get("report_date") != oae_payload["overview"].get("report_date"):
            raise AssertionError("OAE daily report date mismatch between Hub and original dashboard API")
        if "lead_anchors" not in daily_payload or "seed_anchors" not in daily_payload:
            raise AssertionError("OAE original dashboard API missing anchor payloads")

        oae_feishu_link = client.get(absolute_url(base_url, "/dashboard/daily/latest/feishu-link"))
        assert_response(oae_feishu_link, "oae_feishu_link")
        assert_iframe_allowed(oae_feishu_link, "oae_feishu_link")
        if "今日判断" not in oae_feishu_link.text or 'data-dashboard-mode="business"' not in oae_feishu_link.text:
            raise AssertionError("OAE Feishu link should render original business dashboard shell")

        oae_trends = client.get(absolute_url(base_url, "/dashboard/daily/trends"), params={"end_date": daily_payload["report_date"]})
        assert_response(oae_trends, "oae_trends")
        trends_payload = oae_trends.json()
        if not trends_payload.get("daily_trends"):
            raise AssertionError("OAE trends API should include daily_trends")
        results["oae_original_dashboard"] = {
            "report_date": daily_payload.get("report_date"),
            "lead_anchors": len(daily_payload.get("lead_anchors", [])),
            "daily_trends": len(trends_payload.get("daily_trends", [])),
        }

        overview_before = client.get(absolute_url(base_url, "/api/short-video/overview"))
        assert_response(overview_before, "overview_before")
        before_payload = overview_before.json()
        if "video_rankings" not in before_payload or "account_metrics" not in before_payload:
            raise AssertionError("overview payload missing BI contract keys")
        results["overview_contract"] = "ok"

        if upload:
            workbook_path = build_smoke_workbook()
            try:
                with workbook_path.open("rb") as workbook:
                    upload_response = client.post(
                        absolute_url(base_url, "/api/bi/xingtu/admin/upload"),
                        files={
                            "file": (
                                "feishu-deploy-smoke.xlsx",
                                workbook,
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            )
                        },
                    )
                assert_response(upload_response, "upload")
            finally:
                workbook_path.unlink(missing_ok=True)

            overview_after = client.get(absolute_url(base_url, "/api/short-video/overview"))
            assert_response(overview_after, "overview_after")
            payload = overview_after.json()
            overview = payload["overview"]
            account = payload["account_metrics"][0]
            actors = {row["actor_name"]: row for row in payload["actor_metrics"]}

            if overview["total_video_count"] != EXPECTED_VIDEO_COUNT:
                raise AssertionError(f"video count mismatch: {overview['total_video_count']}")
            if overview["total_exposure"] != EXPECTED_EXPOSURE:
                raise AssertionError(f"exposure mismatch: {overview['total_exposure']}")
            if account["account_name"] != EXPECTED_ACCOUNT_NAME:
                raise AssertionError(f"account mismatch: {account['account_name']}")
            if account["completion_5s_display"] != EXPECTED_5S_DISPLAY:
                raise AssertionError(f"5S display mismatch: {account['completion_5s_display']}")
            if len(actors) != EXPECTED_ACTOR_COUNT:
                raise AssertionError(f"actor count mismatch: {len(actors)}")
            for actor_name, actor_row in actors.items():
                if actor_row["contributed_exposure"] != EXPECTED_EXPOSURE:
                    raise AssertionError(f"actor exposure should not be split for {actor_name}: {actor_row}")
            if payload["video_rankings"]["top"]["video_title"] != "飞书部署验证视频":
                raise AssertionError("Top1 video title does not use uploaded video")
            if payload["video_rankings"]["bottom"]["video_title"] != "飞书部署验证视频":
                raise AssertionError("Bot1 video title does not use uploaded video")

            results["upload_refresh"] = "ok"
            results["business_contract"] = {
                "total_video_count": overview["total_video_count"],
                "total_exposure": overview["total_exposure"],
                "completion_5s_display": account["completion_5s_display"],
                "actor_count": len(actors),
                "actor_exposure_not_split": True,
                "video_rankings_are_video_title_level": True,
            }

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a deployed Xingtu BI URL for Feishu iframe acceptance.")
    parser.add_argument("base_url", help="Deployment base URL, for example https://xingtu-short-video-bi.onrender.com")
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload a generated smoke Excel. This changes the deployment's current BI dataset.",
    )
    args = parser.parse_args()

    try:
        results = verify(args.base_url, args.upload)
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    print(json.dumps({"status": "ok", **results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
