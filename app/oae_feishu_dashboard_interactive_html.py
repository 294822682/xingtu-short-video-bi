"""Build a local interactive HTML prototype for the daily Feishu dashboard."""

from __future__ import annotations

import argparse
import csv
from datetime import date
import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit


DEFAULT_SOURCE_TSV = Path("output/sql_reports/feishu_dashboard_source_latest_2026-05-14.tsv")


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    actual: float
    target: float | None
    rate: float | None
    unit: str
    note: str


class DashboardSource:
    """Read dashboard metrics from the stable long-form TSV export."""

    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows
        self.report_date = rows[0].get("report_date", "") if rows else ""

    @classmethod
    def from_tsv(cls, path: str | Path) -> "DashboardSource":
        source_path = Path(path)
        with source_path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        return cls(rows)

    def metric(self, scope_type: str, scope_name: str, metric_key: str) -> Metric:
        row = self._row(scope_type, scope_name, metric_key)
        return Metric(
            key=metric_key,
            label=row.get("metric_name") or metric_key,
            actual=_num(row.get("actual")),
            target=_optional_num(row.get("target")),
            rate=_optional_num(row.get("attain_rate")),
            unit=row.get("unit", ""),
            note=row.get("source_column", ""),
        )

    def anchor_rows(self, source_table: str, metric_keys: list[str]) -> list[dict[str, Any]]:
        rows = [row for row in self.rows if row.get("source_table") == source_table]
        names = list(dict.fromkeys(row.get("scope_name", "") for row in rows if row.get("scope_name")))
        out: list[dict[str, Any]] = []
        for name in names:
            item: dict[str, Any] = {
                "name": name,
                "parent_scope": next((row.get("parent_scope", "") for row in rows if row.get("scope_name") == name), ""),
            }
            for key in metric_keys:
                metric = self.metric("anchor", name, key)
                item[f"{key}_actual"] = metric.actual
                item[f"{key}_target"] = metric.target
                item[f"{key}_rate"] = metric.rate
                item[f"{key}_unit"] = metric.unit
            out.append(item)
        return out

    def _row(self, scope_type: str, scope_name: str, metric_key: str) -> dict[str, str]:
        for row in self.rows:
            if (
                row.get("scope_type") == scope_type
                and row.get("scope_name") == scope_name
                and row.get("metric_key") == metric_key
            ):
                return row
        return {}


@dataclass(frozen=True)
class SegmentMetrics:
    label: str
    leads: float
    deals: float
    spend: float
    cpl: float
    cps: float


def render_interactive_dashboard_html(source: DashboardSource, *, source_label: str = "") -> str:
    """Render a self-contained local HTML prototype from dashboard source rows."""

    topline = {
        "impressions": source.metric("department", "全量", "impressions"),
        "unique": source.metric("department", "全量", "mtd_unique_leads"),
        "deals": source.metric("department", "全量", "mtd_deals"),
        "orders": source.metric("department", "全量", "mtd_douyin_laike_orders"),
        "spend": source.metric("department", "全量", "mtd_spend"),
        "cpl": source.metric("department", "全量", "mtd_cpl"),
        "cps": source.metric("department", "全量", "mtd_cps"),
        "pending_day": source.metric("department", "全量", "pending_day"),
        "pending_cumulative": source.metric("department", "全量", "pending_cumulative"),
        "raw_leads": source.metric("department", "全量", "raw_leads"),
        "unique_rate": source.metric("department", "全量", "unique_rate"),
        "unowned_leads": source.metric("department", "全量", "unowned_leads"),
        "manual_overrides": source.metric("department", "全量", "manual_overrides"),
    }
    if not topline["raw_leads"].actual:
        topline["raw_leads"] = source.metric("department", "全量", "lead_quality_unique_leads")

    lead_anchors = source.anchor_rows(
        "lead_anchor",
        ["daily_leads", "mtd_unique_leads", "mtd_deals", "mtd_douyin_laike_orders", "mtd_cpl", "mtd_cps"],
    )
    seed_anchors = source.anchor_rows("seed_anchor", ["daily_impressions", "mtd_impressions"])
    seed_account = source.metric("account", "EXEED星途", "mtd_impressions")

    source_label = source_label or f"feishu_dashboard_source_latest_{source.report_date}.tsv"
    title = f"日报可交互 BI 原型 · {source.report_date}"
    nav_items = [
        ("overview", "总览 KPI"),
        ("funnel", "全链路转化"),
        ("lead-anchors", "线索主播"),
        ("seed-exposure", "种草曝光"),
    ]
    nav = _nav_html(nav_items)
    cards = _overview_cards(topline)
    funnel = _funnel_html(topline)
    lead_table = _lead_anchor_table(lead_anchors)
    seed_table = _seed_anchor_table(seed_anchors, seed_account)
    raw_payload = json.dumps(
        {
            "report_date": source.report_date,
            "source_rows": len(source.rows),
            "source_label": source_label,
            "prototype_only": True,
        },
        ensure_ascii=False,
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>{_escape(title)}</title>
  <style>{_CSS}</style>
</head>
<body>
  <header class="topbar">
    <div>
      <div class="eyebrow">LOCAL HTML PROTOTYPE</div>
      <h1>{_escape(title)}</h1>
      <p class="subtitle">基于指定 TSV 的本地交互原型；不改日报业务口径，不改 daily_pipeline，不覆盖正式 output/sql_reports 产物。</p>
    </div>
    <div class="source-pill" title="{_escape(source_label)}">
      <span>数据源</span>
      <strong>{_escape(Path(source_label).name)}</strong>
    </div>
  </header>
  {nav}
  <main>
    <section id="overview" class="section band-plain">
      <div class="section-head">
        <div>
          <p class="kicker">01 · OVERVIEW</p>
          <h2>总览 KPI</h2>
        </div>
        <p class="section-note">指标卡保留 TSV 里的 actual / target / attain_rate；悬停查看字段来源和说明。</p>
      </div>
      {cards}
    </section>
    <section id="funnel" class="section">
      <div class="section-head">
        <div>
          <p class="kicker">02 · FUNNEL</p>
          <h2>全链路转化</h2>
        </div>
        <p class="section-note">曝光、原始线索、风车线索（去重）、抖音来客订单（去重）、实销按同一源表展示；条形宽度使用对数比例，仅用于视觉阅读。</p>
      </div>
      {funnel}
    </section>
    <section id="lead-anchors" class="section">
      <div class="section-head">
        <div>
          <p class="kicker">04 · LIVE ANCHORS</p>
          <h2>线索组主播风车线索与抖音来客订单 KPI</h2>
        </div>
        <div class="sort-controls" aria-label="线索主播排序">
          <button type="button" data-sort-table="lead-anchor-table" data-sort-key="mtd_unique_leads_actual" data-sort-dir="desc">按风车线索排序</button>
          <button type="button" data-sort-table="lead-anchor-table" data-sort-key="mtd_douyin_laike_orders_actual" data-sort-dir="desc">按抖音来客订单排序</button>
          <button type="button" data-sort-table="lead-anchor-table" data-sort-key="mtd_cpl_actual" data-sort-dir="asc">按 CPL 排序</button>
        </div>
      </div>
      {lead_table}
    </section>
    <section id="seed-exposure" class="section">
      <div class="section-head">
        <div>
          <p class="kicker">05 · SEED EXPOSURE</p>
          <h2>种草曝光累计达成</h2>
        </div>
        <div class="sort-controls" aria-label="种草曝光排序">
          <button type="button" data-sort-table="seed-anchor-table" data-sort-key="mtd_impressions_actual" data-sort-dir="desc">按累计曝光排序</button>
          <button type="button" data-sort-table="seed-anchor-table" data-sort-key="mtd_impressions_rate" data-sort-dir="desc">按达成率排序</button>
        </div>
      </div>
      {seed_table}
    </section>
  </main>
  <script type="application/json" id="dashboard-meta">{_script_json(raw_payload)}</script>
  <script>{_JS}</script>
</body>
</html>
"""


def render_api_connected_dashboard_html(
    report_date: str,
    *,
    api_path: str | None = None,
    carrier_label: str = "N7 V0 READ-ONLY BI",
    carrier_note: str | None = None,
    business_view: bool = False,
) -> str:
    """Render the API-connected dashboard shell."""

    api_path = api_path or f"/dashboard/daily/{report_date}"
    title_prefix = "运营日报 BI" if business_view else "日报可交互 BI 原型"
    title = f"{title_prefix} · {report_date}"
    carrier_note = carrier_note or (
        "启动 FastAPI 后打开本页；页面只调用 <code>GET /dashboard/daily/latest</code> "
        "或 <code>GET /dashboard/daily/{report_date}</code> 读取只读 BI JSON。"
    )
    nav_items = (
        [
            ("decision", "经营首页"),
            ("funnel", "经营链路"),
            ("workbench", "维度工作台"),
            ("overview", "总览"),
            ("lead-anchors", "主播"),
            ("seed-exposure", "种草"),
            ("daily-bi-trends", "历史趋势"),
        ]
        if business_view
        else [
            ("overview", "总览 KPI"),
            ("funnel", "全链路转化"),
            ("lead-anchors", "线索主播"),
            ("seed-exposure", "种草曝光"),
        ]
    )
    nav = _nav_html(nav_items)
    api_js = _api_js(api_path, business_view=business_view, title_prefix=title_prefix)
    topbar_inner = (
        f"""
    <div>
      <div class="eyebrow">经营链路 + 维度工作台</div>
      <h1>{_escape(title)}</h1>
      <p class="subtitle">以曝光、风车线索（去重）、抖音来客订单（去重）、实销、费用、CPL、CPS 串起经营链路，并保留主播、账号渠道、种草曝光、历史趋势和月度对比。</p>
      <div class="dashboard-meta business-meta" aria-label="日报看板信息">
        <div>
          <span>报表日期</span>
          <strong id="report-date-value">{_escape(report_date)}</strong>
        </div>
        <div>
          <span>只读状态</span>
          <strong id="readonly-status">只读查看</strong>
        </div>
        <div>
          <span>数据新鲜度</span>
          <strong id="freshness-value">等待日报数据</strong>
        </div>
        <div>
          <span>BI 数据口径</span>
          <strong id="preview-boundary-value">日报详细版</strong>
        </div>
      </div>
    </div>
    <div class="topbar-tools">
      <label class="date-switch" for="report-date-select">
        <span>日期</span>
        <select id="report-date-select" aria-label="切换日报日期">
          <option value="latest">latest</option>
        </select>
      </label>
      <form class="business-range-query" id="business-range-query" action="/dashboard/daily/trends/prototype" method="get" aria-label="范围查询">
        <div class="business-range-fields">
          <label for="business-start-date">
            <span>开始日期</span>
            <input id="business-start-date" name="start_date" type="date" required>
          </label>
          <label for="business-end-date">
            <span>结束日期</span>
            <input id="business-end-date" name="end_date" type="date" required>
          </label>
          <button type="submit">查询范围</button>
        </div>
        <p id="business-range-summary">三个月内任意时间段，单次查看上限 92 天。</p>
      </form>
    </div>
        """
        if business_view
        else f"""
    <div>
      <div class="eyebrow">{_escape(carrier_label)}</div>
      <h1>{_escape(title)}</h1>
      <p class="subtitle">{carrier_note}</p>
      <div class="dashboard-meta" aria-label="日报 BI 元信息">
        <div>
          <span>报表日期</span>
          <strong id="report-date-value">{_escape(report_date)}</strong>
        </div>
        <div>
          <span>Source path</span>
          <strong id="source-path-value">{_escape(api_path)}</strong>
        </div>
        <div>
          <span>Source rows</span>
          <strong id="source-rows-value">等待 API</strong>
        </div>
        <div>
          <span>只读状态</span>
          <strong id="readonly-status">只读 API · GET only</strong>
        </div>
      </div>
    </div>
    <div class="topbar-tools">
      <label class="date-switch" for="report-date-select">
        <span>日期</span>
        <select id="report-date-select" aria-label="切换日报日期">
          <option value="latest">latest</option>
        </select>
      </label>
      <div class="source-pill" title="{_escape(api_path)}">
        <span>API</span>
        <strong>{_escape(api_path)}</strong>
      </div>
    </div>
        """
    )
    overview_note = "总览保留核心指标卡，便于和经营链路交叉核对。" if business_view else "指标卡从 API payload 渲染；悬停查看字段来源和说明。"
    funnel_note = "从曝光到线索、订单、实销和成本效率的主要经营链路。" if business_view else "曝光、原始线索、风车线索（去重）、抖音来客订单（去重）、实销按后端只读 JSON 展示。"
    decision_section = (
        """
    <section id="decision" class="section decision-section business-home band-plain" data-module="decision">
      <div class="section-head decision-head">
        <div>
          <p class="kicker">01 · OPERATING STATE</p>
          <h2>今日判断</h2>
        </div>
        <p class="section-note">第一屏呈现每日经营结果、只读边界和需要优先查看的维度。</p>
      </div>
      <div class="decision-board">
        <div class="decision-main">
          <div class="decision-title-row">
            <div>
              <span>每日经营结果</span>
              <strong id="decision-date">等待数据</strong>
            </div>
            <span class="readonly-badge">只读看板</span>
          </div>
          <div class="decision-block-label">核心 KPI · 经营链路</div>
          <div class="decision-kpi-grid" id="decision-core">
            <div class="loading">正在读取日报数据...</div>
          </div>
          <div class="dimension-rail" aria-label="多维工作台入口">
            <a href="#overview">总览</a>
            <a href="#lead-anchors">主播贡献</a>
            <a href="#workbench">账号 / 渠道</a>
            <a href="#seed-exposure">种草</a>
            <a href="#daily-bi-trends">历史趋势</a>
            <a href="#daily-bi-monthly-comparison">月度对比</a>
            <a href="#workbench">成本效率</a>
          </div>
        </div>
        <aside class="decision-side" aria-label="达成状态和重点关注">
          <div>
            <h3>达成状态</h3>
            <div class="decision-status-list" id="decision-status">
              <div class="loading">等待日报数据...</div>
            </div>
          </div>
          <div>
            <h3>重点关注</h3>
            <div class="attention-list" id="decision-attention">
              <div class="loading">等待日报数据...</div>
            </div>
          </div>
        </aside>
      </div>
    </section>
        """
        if business_view
        else ""
    )
    workbench_section = (
        """
    <section id="workbench" class="section workbench-section" data-module="workbench">
      <div class="section-head">
        <div>
          <p class="kicker">04 · DIMENSION WORKBENCH</p>
          <h2>维度工作台</h2>
        </div>
        <p class="section-note">多维入口先复用现有日报 payload，不新增 KPI 口径；下方明细表继续保留搜索和排序。</p>
      </div>
      <div class="dimension-tabs" aria-label="维度工作台标签">
        <span>总览</span>
        <span>主播贡献</span>
        <span>账号 / 渠道</span>
        <span>种草</span>
        <span>历史趋势</span>
        <span>月度对比</span>
        <span>成本效率</span>
      </div>
      <div class="workbench-grid">
        <article class="workbench-panel">
          <span>总览</span>
          <strong id="wb-overview-primary">等待数据</strong>
          <small>曝光、线索、订单、实销合并扫描</small>
        </article>
        <article class="workbench-panel">
          <span>历史趋势</span>
          <strong id="wb-trend-primary">等待数据</strong>
          <small id="wb-trend-secondary">日报源表历史文件</small>
        </article>
        <article class="workbench-panel">
          <span>主播贡献</span>
          <strong id="wb-anchor-primary">等待数据</strong>
          <small>线索主播贡献排序</small>
        </article>
        <article class="workbench-panel">
          <span>账号 / 渠道</span>
          <strong id="wb-account-primary">EXEED星途</strong>
          <small id="wb-account-secondary">种草账号与渠道口径</small>
        </article>
        <article class="workbench-panel">
          <span>种草</span>
          <strong id="wb-seed-primary">等待数据</strong>
          <small id="wb-seed-secondary">累计曝光与达成</small>
        </article>
        <article class="workbench-panel">
          <span>成本效率</span>
          <strong id="wb-cost-primary">等待数据</strong>
          <small id="wb-cost-secondary">CPL / CPS 复核入口</small>
        </article>
      </div>
    </section>
        """
        if business_view
        else ""
    )
    overview_kicker = "02 · KPI" if business_view else "01 · OVERVIEW"
    funnel_kicker = "03 · FUNNEL" if business_view else "02 · FUNNEL"
    lead_kicker = "05 · LIVE ANCHORS" if business_view else "04 · LIVE ANCHORS"
    seed_kicker = "06 · SEED EXPOSURE" if business_view else "05 · SEED EXPOSURE"
    trend_kicker = "07 · 历史经营趋势"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>{_escape(title)}</title>
  <style>{_CSS}</style>
</head>
<body data-api-path="{_escape(api_path)}" data-dashboard-mode="{'business' if business_view else 'technical'}">
  <header class="topbar">
    {topbar_inner}
  </header>
  {nav}
  <main>
    {decision_section}
    <section id="overview" class="section band-plain" data-module="overview">
      <div class="section-head">
        <div>
          <p class="kicker">{_escape(overview_kicker)}</p>
          <h2>总览 KPI</h2>
        </div>
        <p class="section-note">{_escape(overview_note)}</p>
      </div>
      <div class="metric-grid" id="overview-cards"><div class="loading">正在读取 API 数据...</div></div>
    </section>
    <section id="funnel" class="section" data-module="funnel">
      <div class="section-head">
        <div>
          <p class="kicker">{_escape(funnel_kicker)}</p>
          <h2>全链路转化</h2>
        </div>
        <p class="section-note">{_escape(funnel_note)}</p>
      </div>
      <div id="funnel-content"><div class="loading">等待 API 数据...</div></div>
    </section>
    {workbench_section}
    <section id="lead-anchors" class="section" data-module="lead-anchors">
      <div class="section-head">
        <div>
          <p class="kicker">{_escape(lead_kicker)}</p>
          <h2>线索组主播风车线索与抖音来客订单 KPI</h2>
        </div>
        <div class="table-actions">
          <label class="table-search" for="lead-anchor-search">
            <span>搜索</span>
            <input id="lead-anchor-search" type="search" data-filter-table="lead-anchor-table" placeholder="主播 / 直播间">
          </label>
          <div class="sort-controls" id="lead-anchor-sort-controls" aria-label="线索主播排序"></div>
        </div>
      </div>
      <div id="lead-anchor-content"><div class="loading">等待 API 数据...</div></div>
    </section>
    <section id="seed-exposure" class="section" data-module="seed-exposure">
      <div class="section-head">
        <div>
          <p class="kicker">{_escape(seed_kicker)}</p>
          <h2>种草曝光累计达成</h2>
        </div>
        <div class="table-actions">
          <label class="table-search" for="seed-anchor-search">
            <span>搜索</span>
            <input id="seed-anchor-search" type="search" data-filter-table="seed-anchor-table" placeholder="主播 / 账号">
          </label>
          <div class="sort-controls" id="seed-anchor-sort-controls" aria-label="种草曝光排序"></div>
        </div>
      </div>
      <div id="seed-anchor-content"><div class="loading">等待 API 数据...</div></div>
    </section>
    {f'''
    <section id="daily-bi-trends" class="section" data-module="daily-bi-trends">
      <div class="section-head">
        <div>
          <p class="kicker">{_escape(trend_kicker)}</p>
          <h2>历史趋势与月度对比</h2>
        </div>
        <p class="section-note">仅基于日报源表历史文件派生，不混入线索明细或其他口径。</p>
      </div>
      <div class="source-contract-strip">
        <span>数据源</span>
        <strong>feishu_dashboard_source_latest_*.tsv</strong>
      </div>
      <div id="daily-bi-trend-core" class="daily-bi-trend-core"><div class="loading">等待趋势数据...</div></div>
      <div id="daily-bi-history" class="daily-bi-history"><div class="loading">等待历史趋势...</div></div>
      <div id="daily-bi-monthly-comparison" class="daily-bi-monthly-comparison"><div class="loading">等待月度对比...</div></div>
    </section>
    ''' if business_view else ""}
  </main>
  <script>{api_js}</script>
</body>
</html>
"""


def render_feishu_link_trial_dashboard_html(report_date: str, *, api_path: str | None = None) -> str:
    """Render the Feishu BI acceptance shell."""

    return render_api_connected_dashboard_html(
        report_date,
        api_path=api_path,
        business_view=True,
    )


def render_trend_dashboard_html(*, api_path: str = "/dashboard/daily/trends") -> str:
    """Render the business-facing trend presentation shell."""

    title = "经营趋势看板"
    initial_start_date, initial_end_date = _trend_initial_dates_from_api_path(api_path)
    initial_range_days = _trend_range_days(initial_start_date, initial_end_date)
    initial_range_label = (
        f"当前范围：{initial_start_date} 至 {initial_end_date}"
        if initial_start_date and initial_end_date
        else "当前范围：等待日期"
    )
    initial_days_label = f"查看天数：{initial_range_days} / 92" if initial_range_days else "查看天数：等待日期"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>{_escape(title)}</title>
  <style>{_CSS}</style>
</head>
<body data-data-url="{_escape(api_path)}" data-dashboard-mode="trend">
  <header class="topbar">
    <div>
      <h1>{_escape(title)}</h1>
      <p class="subtitle">查看近期核心经营指标变化、账号表现、主播表现与种草曝光情况，辅助日常经营复盘。</p>
      <form class="date-filter-panel trend-filter-toolbar" id="trend-date-filter" aria-label="日期筛选">
        <div class="date-input-group" aria-label="日期输入">
          <label>
            <span>开始日期</span>
            <input id="trend-start-date" name="start_date" type="date" required value="{_escape(initial_start_date)}">
          </label>
          <label>
            <span>结束日期</span>
            <input id="trend-end-date" name="end_date" type="date" required value="{_escape(initial_end_date)}">
          </label>
          <button type="submit">应用范围</button>
        </div>
        <div class="quick-range-groups" aria-label="快捷范围">
          <div class="quick-range-section">
            <span>常用范围</span>
            <div class="quick-range-group">
              <button type="button" data-range-shortcut="last-7" aria-pressed="false">近7天</button>
              <button type="button" data-range-shortcut="last-15" aria-pressed="false">近15天</button>
              <button type="button" data-range-shortcut="last-30" aria-pressed="false">近30天</button>
            </div>
          </div>
          <div class="quick-range-section">
            <span>自然周期</span>
            <div class="quick-range-group">
              <button type="button" data-range-shortcut="this-month" aria-pressed="false">本月</button>
              <button type="button" data-range-shortcut="last-month" aria-pressed="false">上月</button>
              <button type="button" data-range-shortcut="this-quarter" aria-pressed="false">本季度</button>
              <button type="button" data-range-shortcut="last-quarter" aria-pressed="false">上季度</button>
            </div>
          </div>
          <div class="quick-range-section">
            <span>扩展范围</span>
            <div class="quick-range-group">
              <button type="button" data-range-shortcut="last-3-months" aria-pressed="false">近三个月</button>
            </div>
          </div>
        </div>
        <div class="range-summary" aria-label="当前筛选范围">
          <span id="trend-active-range">{_escape(initial_range_label)}</span>
          <span id="trend-range-days">{_escape(initial_days_label)}</span>
          <span id="trend-range-state" class="range-state-pill" data-range-state="custom">自定义范围</span>
        </div>
        <p class="range-message" id="trend-range-message"></p>
      </form>
    </div>
  </header>
  <nav class="nav" aria-label="经营趋势板块导航">
    <a href="#core-trends">核心经营表现</a>
    <a href="#history-trends">历史趋势</a>
    <a href="#account-trends">账号表现</a>
    <a href="#anchor-trends">主播表现</a>
    <a href="#seed-trends">种草曝光</a>
  </nav>
  <main>
    <section id="core-trends" class="section band-plain">
      <div class="section-head">
        <div>
          <p class="kicker">核心复盘</p>
          <h2>核心经营表现</h2>
        </div>
        <p class="section-note">快速查看曝光、线索、实销、费用、CPL、CPS 的近期表现。</p>
      </div>
      <div class="kpi-card-grid" id="trend-core-cards"><div class="loading">正在读取经营数据...</div></div>
    </section>
    <section id="history-trends" class="section">
      <div class="section-head">
        <div>
          <p class="kicker">历史趋势</p>
          <h2>历史趋势</h2>
        </div>
        <p class="section-note">按日期查看曝光、线索、实销趋势、费用、CPL、CPS 的实际变化。</p>
      </div>
      <div id="trend-history"><div class="loading">等待历史趋势...</div></div>
      <div id="trend-monthly-comparison" class="monthly-comparison-slot"><div class="loading">月度对比等待数据...</div></div>
    </section>
    <section id="account-trends" class="section">
      <div class="section-head">
        <div>
          <p class="kicker">账号贡献</p>
          <h2>账号表现</h2>
        </div>
        <p class="section-note">单独查看线索组汇总，并横向对比主要账号的目标参考与实际数值。</p>
      </div>
      <div id="account-toolbar" class="account-toolbar" aria-label="账号表现筛选工具栏">
        <label class="account-search-control">
          <span>账号搜索</span>
          <input id="account-search-input" class="account-search-input" type="search" placeholder="搜索账号名称" autocomplete="off">
        </label>
        <label class="account-sort-control">
          <span>排序</span>
          <select id="account-sort-select" class="account-sort-select">
            <option value="default">默认排序</option>
            <option value="leads">风车线索（去重）</option>
            <option value="deals">成交数</option>
            <option value="spend">费用</option>
            <option value="cpl">CPL</option>
            <option value="cps">CPS</option>
            <option value="target_rate">当前 / 目标</option>
          </select>
        </label>
        <div class="account-filter-control" role="group" aria-label="账号筛选">
          <button type="button" class="account-filter-chip is-active" data-account-filter="all" aria-pressed="true">全部账号</button>
          <button type="button" class="account-filter-chip" data-account-filter="has_target" aria-pressed="false">有目标参考</button>
          <span class="account-filter-separator" aria-hidden="true">·</span>
          <button type="button" class="account-filter-chip" data-account-filter="target_missing" aria-pressed="false">目标未提供</button>
          <button type="button" class="account-filter-chip" data-account-filter="has_deals" aria-pressed="false">有成交</button>
          <button type="button" class="account-filter-chip" data-account-filter="has_spend" aria-pressed="false">有费用</button>
          <button type="button" class="account-filter-chip" data-account-filter="over_100" aria-pressed="false">比率超过 100%</button>
        </div>
        <button type="button" id="account-clear-filters" class="account-clear-filters">清除条件</button>
        <p id="account-filter-summary" class="account-filter-summary" aria-live="polite">当前条件：全部账号</p>
      </div>
      <div id="trend-account-summary" class="account-summary-slot"><div class="loading">等待账号汇总...</div></div>
      <div id="trend-accounts" class="business-card-list account-list"><div class="loading">等待账号数据...</div></div>
      <p class="account-visibility-note">部分已取消或非当前经营复盘范围账号未在主列表展示；当前账号列表不因高比例数据进行隐藏。</p>
    </section>
    <section id="anchor-trends" class="section">
      <div class="section-head">
        <div>
          <p class="kicker">主播贡献</p>
          <h2>主播表现</h2>
        </div>
        <p class="section-note">查看主播风车线索、成交、成本和趋势明细。</p>
      </div>
      <div id="anchor-toolbar" class="anchor-toolbar" aria-label="主播表现筛选工具栏">
        <label class="anchor-search-control">
          <span>主播搜索</span>
          <input id="anchor-search-input" class="anchor-search-input" type="search" placeholder="搜索主播姓名或所属账号" autocomplete="off">
        </label>
        <label class="anchor-sort-control">
          <span>排序</span>
          <select id="anchor-sort-select" class="anchor-sort-select">
            <option value="default">默认排序</option>
            <option value="leads">风车线索（去重）</option>
            <option value="deals">成交数</option>
            <option value="spend">费用</option>
            <option value="cpl">CPL</option>
            <option value="cps">CPS</option>
            <option value="target_rate">当前 / 目标</option>
          </select>
        </label>
        <div class="anchor-filter-control" role="group" aria-label="主播筛选">
          <button type="button" class="anchor-filter-chip is-active" data-anchor-filter="all" aria-pressed="true">全部主播</button>
          <button type="button" class="anchor-filter-chip" data-anchor-filter="has_target" aria-pressed="false">有目标参考</button>
          <span class="anchor-filter-separator" aria-hidden="true">·</span>
          <button type="button" class="anchor-filter-chip" data-anchor-filter="target_missing" aria-pressed="false">目标未提供</button>
          <button type="button" class="anchor-filter-chip" data-anchor-filter="has_deals" aria-pressed="false">有成交</button>
          <button type="button" class="anchor-filter-chip" data-anchor-filter="has_spend" aria-pressed="false">有费用</button>
          <button type="button" class="anchor-filter-chip" data-anchor-filter="over_100" aria-pressed="false">比率超过 100%</button>
        </div>
        <button type="button" id="anchor-clear-filters" class="anchor-clear-filters">清除条件</button>
        <p id="anchor-filter-summary" class="anchor-filter-summary" aria-live="polite">当前条件：全部主播</p>
      </div>
      <div id="trend-anchors" class="business-card-list anchor-list"><div class="loading">等待主播数据...</div></div>
    </section>
    <section id="seed-trends" class="section">
      <div class="section-head">
        <div>
          <p class="kicker">曝光完成</p>
          <h2>种草曝光表现</h2>
        </div>
        <p class="section-note">查看 EXEED 星途账号总曝光，以及种草主播曝光完成情况。</p>
      </div>
      <div id="seed-toolbar" class="seed-toolbar" aria-label="种草曝光筛选工具栏">
        <label class="seed-search-control">
          <span>种草搜索</span>
          <input id="seed-search-input" class="seed-search-input" type="search" placeholder="搜索种草账号或主播" autocomplete="off">
        </label>
        <label class="seed-sort-control">
          <span>排序</span>
          <select id="seed-sort-select" class="seed-sort-select">
            <option value="default">默认排序</option>
            <option value="impressions">曝光</option>
            <option value="target">目标参考</option>
            <option value="target_rate">当前 / 目标</option>
            <option value="latest">范围日曝光合计</option>
            <option value="name">名称</option>
          </select>
        </label>
        <div class="seed-filter-control" role="group" aria-label="种草筛选">
          <button type="button" class="seed-filter-chip is-active" data-seed-filter="all" aria-pressed="true">全部种草</button>
          <button type="button" class="seed-filter-chip" data-seed-filter="account_total" aria-pressed="false">账号总曝光</button>
          <button type="button" class="seed-filter-chip" data-seed-filter="anchor_exposure" aria-pressed="false">主播曝光</button>
          <span class="seed-filter-separator" aria-hidden="true">·</span>
          <button type="button" class="seed-filter-chip" data-seed-filter="has_target" aria-pressed="false">有目标参考</button>
          <span class="seed-filter-separator" aria-hidden="true">·</span>
          <button type="button" class="seed-filter-chip" data-seed-filter="target_missing" aria-pressed="false">目标未提供</button>
          <button type="button" class="seed-filter-chip" data-seed-filter="positive_exposure" aria-pressed="false">曝光大于 0</button>
          <button type="button" class="seed-filter-chip" data-seed-filter="over_100" aria-pressed="false">当前 / 目标超过 100%</button>
        </div>
        <button type="button" id="seed-clear-filters" class="seed-clear-filters">清除条件</button>
        <p id="seed-filter-summary" class="seed-filter-summary" aria-live="polite">当前条件：全部种草</p>
      </div>
      <div id="trend-seed"><div class="loading">等待种草曝光数据...</div></div>
    </section>
  </main>
  <footer class="business-footnote">
    <details>
      <summary>指标说明</summary>
      <div>
        <p>本页仅供内部经营复盘参考，最终以原始日报与人工确认为准。</p>
        <p>转化率按日报源表中的线索、成交和目标参考计算；因历史线索延续、跨期成交、账号调整或停播后继续转化，部分比例可能超过 100%，页面按原始数据如实展示。</p>
        <p>真实 0 保持 0；缺失值显示未提供；缺失趋势点不补 0。</p>
      </div>
    </details>
  </footer>
  <script>{_trend_js(api_path)}</script>
</body>
</html>
"""


def write_interactive_dashboard_html(
    *,
    source_tsv: str | Path = DEFAULT_SOURCE_TSV,
    output_html: str | Path | None = None,
) -> Path:
    """Write the local prototype HTML. Defaults to a non-formal /tmp preview."""

    source_path = Path(source_tsv)
    source = DashboardSource.from_tsv(source_path)
    if output_html is None:
        report_date = source.report_date or "preview"
        output_path = Path("/tmp") / f"oae_daily_bi_interactive_{report_date}.html"
    else:
        output_path = Path(output_html)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_interactive_dashboard_html(source, source_label=str(source_path)),
        encoding="utf-8",
    )
    return output_path


def write_api_connected_dashboard_html(
    *,
    report_date: str,
    output_html: str | Path | None = None,
    api_path: str | None = None,
) -> Path:
    """Write the API-connected local prototype HTML shell."""

    output_path = Path(output_html) if output_html is not None else Path("/tmp") / f"oae_daily_bi_interactive_api_{report_date}.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_api_connected_dashboard_html(report_date, api_path=api_path),
        encoding="utf-8",
    )
    return output_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成日报可交互 BI 本地 HTML 原型")
    parser.add_argument("--source-tsv", default=str(DEFAULT_SOURCE_TSV), help="驾驶舱 TSV 数据源")
    parser.add_argument("--report-date", default="2026-05-14", help="API 版原型的日报日期")
    parser.add_argument("--api-connected", action="store_true", help="生成通过 /dashboard/daily/{report_date} 取数的 API 版原型")
    parser.add_argument("--api-path", default="", help="API 版原型的 fetch 路径；留空自动使用 /dashboard/daily/{report_date}")
    parser.add_argument("--output-html", default="", help="HTML 输出路径；留空则写入 /tmp")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.api_connected:
        output_path = write_api_connected_dashboard_html(
            report_date=args.report_date,
            output_html=args.output_html or None,
            api_path=args.api_path or None,
        )
    else:
        output_path = write_interactive_dashboard_html(
            source_tsv=args.source_tsv,
            output_html=args.output_html or None,
        )
    print(f"[OK] interactive dashboard html: {output_path}")
    return 0


def _overview_cards(topline: dict[str, Metric]) -> str:
    cards = [
        ("曝光", _fmt_wan(topline["impressions"].actual), topline["impressions"], "teal"),
        ("风车线索（去重）", _fmt_int(topline["unique"].actual), topline["unique"], "green"),
        ("抖音来客订单（去重）", _fmt_int(topline["orders"].actual), topline["orders"], "amber"),
        ("实销", _fmt_int(topline["deals"].actual), topline["deals"], "red"),
        ("费用", _fmt_money_wan(topline["spend"].actual), topline["spend"], "ink"),
        ("CPL", _fmt_money(topline["cpl"].actual), topline["cpl"], "blue"),
        ("CPS", _fmt_money(topline["cps"].actual), topline["cps"], "red"),
        (
            "待交车",
            f"{_fmt_int(topline['pending_day'].actual)} / {_fmt_int(topline['pending_cumulative'].actual)}",
            topline["pending_cumulative"],
            "green",
        ),
    ]
    return "<div class=\"metric-grid\">" + "".join(_metric_card(*card) for card in cards) + "</div>"


def _metric_card(title: str, display: str, metric: Metric, tone: str) -> str:
    target = _fmt_metric_target(metric)
    rate = _fmt_metric_rate(metric)
    note = metric.note or "TSV actual 字段"
    tooltip = f"{metric.label}；actual={_fmt_float(metric.actual)}；{target}；达成={rate}；来源={note}"
    return f"""
      <article class="metric-card tone-{tone}" data-tooltip="{_escape(tooltip)}" tabindex="0">
        <div class="metric-label">{_escape(title)}</div>
        <div class="metric-value">{_escape(display)}</div>
        <div class="metric-sub">{_escape(target)} · {_escape(rate)}</div>
        <div class="metric-help">{_escape(tooltip)}</div>
      </article>
    """


def _funnel_html(topline: dict[str, Metric]) -> str:
    steps = [
        ("曝光", topline["impressions"].actual, _fmt_wan(topline["impressions"].actual), "曝光口径"),
        ("原始线索", topline["raw_leads"].actual, _fmt_int(topline["raw_leads"].actual), "lead_quality.raw_leads"),
        ("风车线索（去重）", topline["unique"].actual, _fmt_int(topline["unique"].actual), "mtd_unique_leads"),
        ("抖音来客订单（去重）", topline["orders"].actual, _fmt_int(topline["orders"].actual), "mtd_douyin_laike_orders"),
        ("实销", topline["deals"].actual, _fmt_int(topline["deals"].actual), "mtd_deals"),
    ]
    max_value = max([value for _, value, _, _ in steps] + [1])
    rows = []
    last_value = 0.0
    for index, (label, value, display, note) in enumerate(steps, start=1):
        width = max(2.0, _log_ratio(value, max_value) * 100)
        conversion = _fmt_pct(value / last_value) if last_value else "基准"
        last_value = value
        rows.append(
            f"""
            <div class="funnel-row">
              <div class="funnel-index">{index:02d}</div>
              <div class="funnel-main">
                <div class="funnel-label"><strong>{_escape(label)}</strong><span>{_escape(note)}</span></div>
                <div class="funnel-track"><div class="funnel-fill" style="width:{width:.2f}%"></div></div>
              </div>
              <div class="funnel-value">{_escape(display)}</div>
              <div class="funnel-conversion">{_escape(conversion)}</div>
            </div>
            """
        )
    chips = [
        ("唯一率", _fmt_pct(topline["unique_rate"].actual or _safe_div(topline["unique"].actual, topline["raw_leads"].actual))),
        ("无主线索", _fmt_int(topline["unowned_leads"].actual)),
        ("人工归属", _fmt_int(topline["manual_overrides"].actual)),
    ]
    chip_html = "".join(f"<span>{_escape(label)} <strong>{_escape(value)}</strong></span>" for label, value in chips)
    return f"<div class=\"funnel-panel\">{''.join(rows)}</div><div class=\"quality-strip\">{chip_html}</div>"


def _segment_html(ex7: SegmentMetrics, non_ex7: SegmentMetrics) -> str:
    total_leads = ex7.leads + non_ex7.leads
    total_deals = ex7.deals + non_ex7.deals
    cps_delta = ex7.cps - non_ex7.cps
    cpl_delta = ex7.cpl - non_ex7.cpl
    insight = [
        ("EX7 线索占比", _fmt_pct(_safe_div(ex7.leads, total_leads)), "EX7 专项风车线索 / 总风车线索"),
        ("不含 EX7 实销占比", _fmt_pct(_safe_div(non_ex7.deals, total_deals)), "不含 EX7 实销 / 总实销"),
        ("CPL 差异", _fmt_money(cpl_delta), "EX7 CPL - 不含 EX7 CPL"),
        ("CPS 差异", _fmt_money(cps_delta), "EX7 CPS - 不含 EX7 CPS"),
    ]
    insight_html = "".join(
        f"""
        <div class="delta-card">
          <span>{_escape(label)}</span>
          <strong>{_escape(value)}</strong>
          <small>{_escape(note)}</small>
        </div>
        """
        for label, value, note in insight
    )
    return f"""
      <div class="segment-layout">
        {_segment_panel(ex7, "ex7")}
        {_segment_panel(non_ex7, "non-ex7")}
      </div>
      <div class="delta-grid">{insight_html}</div>
    """


def _segment_panel(segment: SegmentMetrics, tone: str) -> str:
    values = [
        ("风车线索（去重）", _fmt_int(segment.leads)),
        ("实销", _fmt_int(segment.deals)),
        ("消耗", _fmt_money_wan(segment.spend)),
        ("CPL", _fmt_money(segment.cpl)),
        ("CPS", _fmt_money(segment.cps)),
    ]
    body = "".join(f"<li><span>{_escape(label)}</span><strong>{_escape(value)}</strong></li>" for label, value in values)
    return f"""
      <article class="segment-panel {tone}">
        <h3>{_escape(segment.label)}</h3>
        <ul>{body}</ul>
      </article>
    """


def _lead_anchor_table(anchors: list[dict[str, Any]]) -> str:
    max_leads = max([float(item.get("mtd_unique_leads_actual", 0.0)) for item in anchors] + [1.0])
    rows = []
    for item in anchors:
        leads = float(item.get("mtd_unique_leads_actual", 0.0))
        orders = float(item.get("mtd_douyin_laike_orders_actual", 0.0))
        order_rate = item.get("mtd_douyin_laike_orders_rate")
        deals = float(item.get("mtd_deals_actual", 0.0))
        cpl = float(item.get("mtd_cpl_actual", 0.0))
        cps = float(item.get("mtd_cps_actual", 0.0))
        rows.append(
            f"""
            <tr
              data-mtd_unique_leads_actual="{leads:.6f}"
              data-mtd_douyin_laike_orders_actual="{orders:.6f}"
              data-mtd_cpl_actual="{cpl:.6f}"
            >
              <th scope="row">
                <span class="anchor-name">{_escape(item['name'])}</span>
                <small>{_escape(item.get('parent_scope', ''))}</small>
              </th>
              <td><div class="bar-cell"><span style="width:{_safe_div(leads, max_leads) * 100:.2f}%"></span></div>{_fmt_int(leads)}</td>
              <td>{_fmt_int(orders)} <small>{_fmt_optional_pct(order_rate)}</small></td>
              <td>{_fmt_float(deals)}</td>
              <td>{_fmt_money(cpl)}</td>
              <td>{_fmt_money(cps)}</td>
            </tr>
            """
        )
    return f"""
      <div class="table-wrap">
        <table id="lead-anchor-table">
          <thead>
            <tr>
              <th>主播</th>
              <th>风车线索（去重）</th>
              <th>抖音来客订单（去重） / 达成</th>
              <th>累计实销</th>
              <th>CPL</th>
              <th>CPS</th>
            </tr>
          </thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    """


def _seed_anchor_table(anchors: list[dict[str, Any]], account: Metric) -> str:
    max_mtd = max([float(item.get("mtd_impressions_actual", 0.0)) for item in anchors] + [1.0])
    rows = []
    for item in anchors:
        daily = float(item.get("daily_impressions_actual", 0.0))
        mtd = float(item.get("mtd_impressions_actual", 0.0))
        target = item.get("mtd_impressions_target")
        rate = item.get("mtd_impressions_rate")
        rows.append(
            f"""
            <tr data-mtd_impressions_actual="{mtd:.6f}" data-mtd_impressions_rate="{_num_or_zero(rate):.6f}">
              <th scope="row"><span class="anchor-name">{_escape(item['name'])}</span></th>
              <td><div class="bar-cell seed"><span style="width:{_safe_div(mtd, max_mtd) * 100:.2f}%"></span></div>{_fmt_wan(mtd)}</td>
              <td>{_fmt_optional_wan(target)}</td>
              <td>{_fmt_optional_pct(rate)}</td>
              <td>{_fmt_wan(daily)}</td>
            </tr>
            """
        )
    summary = f"""
      <div class="seed-summary">
        <span>EXEED星途累计曝光</span>
        <strong>{_fmt_wan(account.actual)}</strong>
        <span>目标 {_fmt_optional_wan(account.target)}</span>
        <span>达成 {_fmt_metric_rate(account)}</span>
      </div>
    """
    return f"""
      {summary}
      <div class="table-wrap">
        <table id="seed-anchor-table">
          <thead>
            <tr>
              <th>种草主播</th>
              <th>累计曝光</th>
              <th>累计目标</th>
              <th>达成率</th>
              <th>当日曝光</th>
            </tr>
          </thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    """


def _nav_html(items: list[tuple[str, str]]) -> str:
    links = "".join(f"<a href=\"#{_escape(anchor)}\">{_escape(label)}</a>" for anchor, label in items)
    return f"<nav class=\"nav\" aria-label=\"日报 BI 模块导航\">{links}</nav>"


def _api_js(api_path: str, *, business_view: bool = False, title_prefix: str = "日报可交互 BI 原型") -> str:
    readonly_label = "只读查看" if business_view else "只读 API · GET only"
    failure_prefix = "数据读取失败" if business_view else "API 读取失败"
    source_fallback = "日报数据" if business_view else "API payload"
    expose_source_column = "false" if business_view else "true"
    return f"""
const API_PATH = "{_script_string(api_path)}";
const TREND_API_PATH = "/dashboard/daily/trends";
const PAGE_TITLE_PREFIX = "{_script_string(title_prefix)}";
const READONLY_STATUS_TEXT = "{_script_string(readonly_label)}";
const FAILURE_PREFIX = "{_script_string(failure_prefix)}";
const SOURCE_FALLBACK_TEXT = "{_script_string(source_fallback)}";
const EXPOSE_SOURCE_COLUMN = {expose_source_column};
const IS_BUSINESS_MODE = {"true" if business_view else "false"};
let currentApiPath = API_PATH;

function escapeHtml(value) {{
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({{
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\\"": "&quot;",
    "'": "&#39;"
  }}[char]));
}}

function metricValue(metric) {{
  return Number(metric?.actual || 0);
}}

function fmtInt(value) {{
  return Number(value || 0).toLocaleString("zh-CN", {{ maximumFractionDigits: 0 }});
}}

function fmtFloat(value) {{
  return Number(value || 0).toLocaleString("zh-CN", {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
}}

function fmtWan(value) {{
  return `${{fmtFloat(Number(value || 0) / 10000)}}万`;
}}

function fmtMoney(value) {{
  return `¥${{fmtFloat(value)}}`;
}}

function fmtMoneyWan(value) {{
  const numeric = Number(value || 0);
  return Math.abs(numeric) >= 10000 ? `¥${{fmtFloat(numeric / 10000)}}万` : fmtMoney(numeric);
}}

function isUnitCost(unit) {{
  return String(unit || "").includes("/");
}}

function fmtPct(value) {{
  return `${{fmtFloat(Number(value || 0) * 100)}}%`;
}}

function hasValue(value) {{
  return value !== null && value !== undefined;
}}

function fmtMetric(metric) {{
  if (metric?.display) return metric.display;
  const unit = metric?.unit || "";
  const value = metricValue(metric);
  if (unit.includes("元")) return isUnitCost(unit) ? fmtMoney(value) : fmtMoneyWan(value);
  if (unit.includes("人次")) return fmtWan(value);
  if (metric?.key === "unique_rate") return fmtPct(value);
  return fmtInt(value);
}}

function targetText(metric) {{
  if (!hasValue(metric?.target)) return "未提供";
  const target = Number(metric.target);
  const unit = metric?.unit || "";
  if (unit.includes("元")) return `目标 ${{fmtMoney(target)}}`;
  if (unit.includes("人次")) return `目标 ${{fmtWan(target)}}`;
  return `目标 ${{fmtInt(target)}}`;
}}

function targetValueText(metric) {{
  if (!hasValue(metric?.target)) return "未提供";
  const target = Number(metric.target);
  const unit = metric?.unit || "";
  if (unit.includes("元")) return fmtMoney(target);
  if (unit.includes("人次")) return fmtWan(target);
  return fmtInt(target);
}}

function isCostMetric(metric) {{
  const key = String(metric?.key || "").toLowerCase();
  const label = String(metric?.label || "").toLowerCase();
  return key.includes("cpl") || key.includes("cps") || label.includes("cpl") || label.includes("cps");
}}

function metricProgressRate(metric) {{
  if (hasValue(metric?.attain_rate)) return Number(metric.attain_rate);
  if (!hasValue(metric?.actual) || !hasValue(metric?.target)) return null;
  if (Number(metric.actual) <= 0 || Number(metric.target) <= 0) return null;
  if (isCostMetric(metric)) return Number(metric.target) / Number(metric.actual);
  return null;
}}

function rateText(metric) {{
  const progressRate = metricProgressRate(metric);
  if (!hasValue(progressRate)) return "未提供";
  return fmtPct(progressRate);
}}

function sourceText(metric) {{
  return EXPOSE_SOURCE_COLUMN ? (metric?.source_column || SOURCE_FALLBACK_TEXT) : SOURCE_FALLBACK_TEXT;
}}

function statusForMetric(metric, watchThreshold = 0.7) {{
  if (!hasValue(metric?.target) || !hasValue(metric?.attain_rate)) {{
    return {{ label: "目标未提供", className: "neutral", detail: "仅展示实际值" }};
  }}
  const rate = Number(metric.attain_rate || 0);
  if (rate >= 1) return {{ label: "达成率 ≥ 100%", className: "neutral", detail: `达成率 ${{fmtPct(rate)}}` }};
  if (rate >= watchThreshold) return {{ label: `达成率 ≥ ${{fmtPct(watchThreshold)}}`, className: "neutral", detail: `达成率 ${{fmtPct(rate)}}` }};
  return {{ label: `达成率 < ${{fmtPct(watchThreshold)}}`, className: "neutral", detail: `达成率 ${{fmtPct(rate)}}` }};
}}

function decisionKpiCard(title, metric, tone, displayOverride = "") {{
  const status = statusForMetric(metric);
  const display = displayOverride || fmtMetric(metric);
  return `
    <article class="decision-kpi tone-${{tone}}">
      <div>
        <span>${{escapeHtml(title)}}</span>
        <strong>${{escapeHtml(display)}}</strong>
      </div>
      <div class="decision-kpi-foot">
        <small>${{escapeHtml(targetText(metric))}}</small>
        <em class="${{status.className}}">${{escapeHtml(status.label)}}</em>
      </div>
    </article>`;
}}

function statusRow(label, metric) {{
  const status = statusForMetric(metric);
  return `
    <div class="status-row">
      <span>${{escapeHtml(label)}}</span>
      <strong class="${{status.className}}">${{escapeHtml(status.label)}}</strong>
      <small>${{escapeHtml(status.detail)}}</small>
    </div>`;
}}

function topAnchorByMetric(anchors, metricKey) {{
  return [...(anchors || [])].sort((a, b) => {{
    return metricValue(anchorMetric(b, metricKey)) - metricValue(anchorMetric(a, metricKey));
  }})[0] || null;
}}

function attentionItem(label, value, note, tone) {{
  return `
    <div class="attention-item tone-${{tone}}">
      <span>${{escapeHtml(label)}}</span>
      <strong>${{escapeHtml(value)}}</strong>
      <small>${{escapeHtml(note)}}</small>
    </div>`;
}}

function setText(id, value) {{
  const node = document.getElementById(id);
  if (node) node.textContent = value;
}}

function renderDecision(payload) {{
  const section = document.getElementById("decision");
  if (!section) return;
  const overview = payload.overview || {{}};
  const decisionDate = document.getElementById("decision-date");
  if (decisionDate) decisionDate.textContent = `${{payload.report_date || "未提供"}} 日报`;

  const pendingDisplay = `${{fmtInt(metricValue(overview.pending_day))}} / ${{fmtInt(metricValue(overview.pending_cumulative))}}`;
  document.getElementById("decision-core").innerHTML = [
    decisionKpiCard("曝光", overview.impressions, "teal"),
    decisionKpiCard("线索", overview.raw_leads, "blue"),
    decisionKpiCard("风车线索（去重）", overview.mtd_unique_leads, "green"),
    decisionKpiCard("抖音来客订单（去重）", overview.mtd_douyin_laike_orders, "amber"),
    decisionKpiCard("实销", overview.mtd_deals, "red"),
    decisionKpiCard("CPL", overview.mtd_cpl, "blue"),
    decisionKpiCard("CPS", overview.mtd_cps, "red"),
    decisionKpiCard("待交车", overview.pending_cumulative, "ink", pendingDisplay),
  ].join("");

  document.getElementById("decision-status").innerHTML = [
    statusRow("线索达成", overview.mtd_unique_leads),
    statusRow("抖音来客订单达成", overview.mtd_douyin_laike_orders),
    statusRow("实销达成", overview.mtd_deals),
    statusRow("种草曝光达成", payload.seed_account),
  ].join("");

  const cpl = metricValue(overview.mtd_cpl);
  const cps = metricValue(overview.mtd_cps);
  const topLead = topAnchorByMetric(payload.lead_anchors, "mtd_unique_leads");
  const topSeed = topAnchorByMetric(payload.seed_anchors, "mtd_impressions");
  document.getElementById("decision-attention").innerHTML = [
    attentionItem(
      "主播线索",
      topLead ? `${{topLead.name}} · ${{fmtInt(metricValue(anchorMetric(topLead, "mtd_unique_leads")))}} 条` : "未提供",
      "线索组主播风车线索最高",
      "green"
    ),
    attentionItem(
      "种草曝光",
      topSeed ? `${{topSeed.name}} · ${{fmtWan(metricValue(anchorMetric(topSeed, "mtd_impressions")))}}` : fmtWan(metricValue(payload.seed_account)),
      `账号累计达成 ${{rateText(payload.seed_account)}}`,
      "teal"
    ),
    attentionItem("成本效率", `CPL ${{fmtMoney(cpl)}} / CPS ${{fmtMoney(cps)}}`, "跟踪线索成本和实销成本", "amber"),
  ].join("");
}}

function renderWorkbench(payload) {{
  const section = document.getElementById("workbench");
  if (!section) return;
  const overview = payload.overview || {{}};
  const topLead = topAnchorByMetric(payload.lead_anchors, "mtd_unique_leads");
  const topSeed = topAnchorByMetric(payload.seed_anchors, "mtd_impressions");
  setText(
    "wb-overview-primary",
    `${{fmtWan(metricValue(overview.impressions))}}曝光 · ${{fmtInt(metricValue(overview.mtd_unique_leads))}}风车线索`
  );
  setText("wb-trend-primary", "历史趋势 / 月度对比");
  setText("wb-trend-secondary", "日报源表历史文件");
  setText(
    "wb-anchor-primary",
    topLead ? `${{topLead.name}} · ${{fmtInt(metricValue(anchorMetric(topLead, "mtd_unique_leads")))}}条` : "未提供"
  );
  setText("wb-account-primary", `EXEED星途 · ${{fmtWan(metricValue(payload.seed_account))}}`);
  setText("wb-account-secondary", `账号累计达成 ${{rateText(payload.seed_account)}}`);
  setText(
    "wb-seed-primary",
    topSeed ? `${{topSeed.name}} · ${{fmtWan(metricValue(anchorMetric(topSeed, "mtd_impressions")))}}` : fmtWan(metricValue(payload.seed_account))
  );
  setText("wb-seed-secondary", `种草曝光达成 ${{rateText(payload.seed_account)}}`);
  setText("wb-cost-primary", `CPL ${{fmtMoney(metricValue(overview.mtd_cpl))}}`);
  setText("wb-cost-secondary", `CPS ${{fmtMoney(metricValue(overview.mtd_cps))}}`);
}}

const LEAD_SORT_CONTROLS = {{
  mtd_unique_leads: {{ label: "按风车线索排序", direction: "desc" }},
  mtd_douyin_laike_orders: {{ label: "按抖音来客订单排序", direction: "desc" }},
  mtd_cpl: {{ label: "按 CPL 排序", direction: "asc" }},
}};

const SEED_SORT_CONTROLS = {{
  mtd_impressions: {{ label: "按累计曝光排序", direction: "desc" }},
  mtd_impressions_attain_rate: {{ label: "按达成率排序", direction: "desc" }},
}};

function metricCard(title, metric, tone) {{
  const tooltip = `${{metric.label}}；actual=${{metricValue(metric)}}；${{targetText(metric)}}；达成=${{rateText(metric)}}；来源=${{sourceText(metric)}}`;
  return `
    <article class="metric-card tone-${{tone}}" data-tooltip="${{escapeHtml(tooltip)}}" tabindex="0">
      <div class="metric-label">${{escapeHtml(title)}}</div>
      <div class="metric-value">${{escapeHtml(fmtMetric(metric))}}</div>
      <div class="metric-sub">${{escapeHtml(targetText(metric))}} · ${{escapeHtml(rateText(metric))}}</div>
      <div class="metric-help">${{escapeHtml(tooltip)}}</div>
    </article>
  `;
}}

function renderOverview(payload) {{
  const overview = payload.overview;
  const cards = [
    ["曝光", overview.impressions, "teal"],
    ["风车线索（去重）", overview.mtd_unique_leads, "green"],
    ["抖音来客订单（去重）", overview.mtd_douyin_laike_orders, "amber"],
    ["实销", overview.mtd_deals, "red"],
    ["费用", overview.mtd_spend, "ink"],
    ["CPL", overview.mtd_cpl, "blue"],
    ["CPS", overview.mtd_cps, "red"],
    ["待交车", {{ ...overview.pending_cumulative, display: `${{fmtInt(metricValue(overview.pending_day))}} / ${{fmtInt(metricValue(overview.pending_cumulative))}}`, unit: "" }}, "green"],
  ];
  document.getElementById("overview-cards").innerHTML = cards.map(([title, metric, tone]) => metricCard(title, metric, tone)).join("");
}}

function renderFunnel(payload) {{
  const maxValue = Math.max(...payload.funnel.map((step) => Number(step.actual || 0)), 1);
  const rows = payload.funnel.map((step, index) => {{
    const value = Number(step.actual || 0);
    const width = Math.max(2, (Math.log10(value + 1) / Math.log10(maxValue + 1)) * 100);
    const display = step.unit === "人次" ? fmtWan(value) : fmtInt(value);
    const conversion = step.conversion_from_previous === null ? "基准" : fmtPct(step.conversion_from_previous);
    const funnelConversion = IS_BUSINESS_MODE ? "" : `<div class="funnel-conversion">${{escapeHtml(conversion)}}</div>`;
    return `
      <div class="funnel-row">
        <div class="funnel-index">${{String(index + 1).padStart(2, "0")}}</div>
        <div class="funnel-main">
          <div class="funnel-label"><strong>${{escapeHtml(step.label)}}</strong>${{IS_BUSINESS_MODE ? "" : `<span>${{escapeHtml(step.key)}}</span>`}}</div>
          <div class="funnel-track"><div class="funnel-fill" style="width:${{width.toFixed(2)}}%"></div></div>
        </div>
        <div class="funnel-value">${{escapeHtml(display)}}</div>
        ${{funnelConversion}}
      </div>`;
  }}).join("");
  const quality = payload.overview;
  const qualityStrip = IS_BUSINESS_MODE ? "" : `
    <div class="quality-strip">
      <span>唯一率 <strong>${{fmtPct(metricValue(quality.unique_rate))}}</strong></span>
      <span>无主线索 <strong>${{fmtInt(metricValue(quality.unowned_leads))}}</strong></span>
      <span>人工归属 <strong>${{fmtInt(metricValue(quality.manual_overrides))}}</strong></span>
    </div>`;
  document.getElementById("funnel-content").innerHTML = `
    <div class="funnel-panel">${{rows}}</div>
    ${{qualityStrip}}`;
}}

function anchorMetric(anchor, key) {{
  return anchor.metrics?.[key] || {{ actual: null, target: null, attain_rate: null, unit: "" }};
}}

function anchorOptionalMetric(anchor, key, label, unit = "") {{
  return anchor.metrics?.[key] || {{ key, label, actual: null, target: null, attain_rate: null, unit }};
}}

function fmtNullableMetric(metric) {{
  if (!hasValue(metric?.actual) || Number.isNaN(Number(metric.actual))) return "未提供";
  const value = Number(metric.actual);
  const unit = metric?.unit || "";
  if (unit.includes("元")) return isUnitCost(unit) ? fmtMoney(value) : fmtMoneyWan(value);
  if (unit.includes("人次")) return fmtWan(value);
  if (unit.includes("比例")) return fmtPct(value);
  return Number.isInteger(value) ? fmtInt(value) : fmtFloat(value);
}}

function rowSearchText(anchor) {{
  return `${{anchor?.name || ""}} ${{anchor?.parent_scope || ""}}`.toLowerCase();
}}

function barMetricCells(fillWidth, display, tone = "") {{
  const safeWidth = Math.max(0, Math.min(Number(fillWidth) || 0, 100));
  if (!IS_BUSINESS_MODE) {{
    return `<td class="bar-metric-cell"><div class="bar-cell${{tone ? ` ${{tone}}` : ""}}"><span style="width:${{safeWidth}}%"></span></div>${{escapeHtml(display)}}</td>`;
  }}
  return `
    <td class="bar-metric-cell bar-track-cell">
      <div class="bar-metric">
        <div class="bar-cell${{tone ? ` ${{tone}}` : ""}}"><span style="width:${{safeWidth}}%"></span></div>
      </div>
    </td>
    <td class="metric-value-cell"><strong class="bar-value">${{escapeHtml(display)}}</strong></td>`;
}}

function leadMetricTableClass() {{
  return IS_BUSINESS_MODE ? ` class="metric-table lead-metric-table"` : "";
}}

function seedMetricTableClass() {{
  return IS_BUSINESS_MODE ? ` class="metric-table seed-metric-table"` : "";
}}

function leadColgroup() {{
  if (!IS_BUSINESS_MODE) return "";
  return `
        <colgroup>
          <col class="col-label">
          <col class="col-parent">
          <col class="col-bar">
          <col class="col-value">
          <col class="col-orders">
          <col class="col-visits">
          <col class="col-visit-rate">
          <col class="col-visit-deal-rate">
          <col class="col-number">
          <col class="col-spend">
          <col class="col-money">
          <col class="col-money">
        </colgroup>`;
}}

function seedColgroup() {{
  if (!IS_BUSINESS_MODE) return "";
  return `
        <colgroup>
          <col class="col-label">
          <col class="col-bar">
          <col class="col-value">
          <col class="col-target">
          <col class="col-rate">
          <col class="col-number">
        </colgroup>`;
}}

function leadTableHeader() {{
  if (!IS_BUSINESS_MODE) {{
    return `<thead><tr><th>主播</th><th>所属账号 / 直播间</th><th>风车线索进度</th><th>风车线索（去重）</th><th>抖音来客订单（去重） / 达成</th><th>到店数</th><th>到店率</th><th>到店成交率</th><th>累计实销</th><th>费用</th><th>CPL</th><th>CPS</th></tr></thead>`;
  }}
  return `<thead><tr><th>主播</th><th>所属账号 / 直播间</th><th class="bar-header">风车线索进度</th><th class="metric-value-header">风车线索（去重）</th><th>抖音来客订单（去重） / 达成</th><th>到店数</th><th>到店率</th><th>到店成交率</th><th>累计实销</th><th>费用</th><th>CPL</th><th>CPS</th></tr></thead>`;
}}

function seedTableHeader() {{
  if (!IS_BUSINESS_MODE) {{
    return `<thead><tr><th>种草主播</th><th>累计曝光</th><th>累计目标</th><th>达成率</th><th>当日曝光</th></tr></thead>`;
  }}
  return `<thead><tr><th>种草主播</th><th class="bar-header">曝光进度</th><th class="metric-value-header">累计曝光</th><th>累计目标</th><th>达成率</th><th>当日曝光</th></tr></thead>`;
}}

function renderLeadAnchors(payload) {{
  const maxLeads = Math.max(...payload.lead_anchors.map((anchor) => metricValue(anchorMetric(anchor, "mtd_unique_leads"))), 1);
  const rows = payload.lead_anchors.map((anchor) => {{
    const leads = anchorMetric(anchor, "mtd_unique_leads");
    const orders = anchorMetric(anchor, "mtd_douyin_laike_orders");
    const visits = anchorOptionalMetric(anchor, "visits", "到店数", "条");
    const visitRate = anchorOptionalMetric(anchor, "visit_rate", "到店率", "比例");
    const visitDealRate = anchorOptionalMetric(anchor, "visit_deal_rate", "到店成交率", "比例");
    const deals = anchorMetric(anchor, "mtd_deals");
    const spend = anchorMetric(anchor, "mtd_spend");
    const cpl = anchorMetric(anchor, "mtd_cpl");
    const cps = anchorMetric(anchor, "mtd_cps");
    const parentScope = anchor.parent_scope || "未提供";
    return `
      <tr data-search-text="${{escapeHtml(rowSearchText(anchor))}}" data-mtd_unique_leads="${{metricValue(leads)}}" data-mtd_douyin_laike_orders="${{metricValue(orders)}}" data-visits="${{metricValue(visits)}}" data-mtd_spend="${{metricValue(spend)}}" data-mtd_cpl="${{metricValue(cpl)}}">
        <th scope="row"><span class="anchor-name">${{escapeHtml(anchor.name)}}</span></th>
        <td class="anchor-parent-cell" title="${{escapeHtml(parentScope)}}">${{escapeHtml(parentScope)}}</td>
        ${{barMetricCells((metricValue(leads) / maxLeads) * 100, fmtInt(metricValue(leads)))}}
        <td class="metric-number-cell"><span class="metric-rate-pair"><span class="number-main">${{fmtInt(metricValue(orders))}}</span><small class="rate-chip">${{rateText(orders)}}</small></span></td>
        <td class="metric-number-cell">${{escapeHtml(fmtNullableMetric(visits))}}</td>
        <td class="metric-rate-cell">${{escapeHtml(fmtNullableMetric(visitRate))}}</td>
        <td class="metric-rate-cell">${{escapeHtml(fmtNullableMetric(visitDealRate))}}</td>
        <td class="metric-number-cell">${{fmtFloat(metricValue(deals))}}</td>
        <td class="metric-money-cell">${{fmtMoney(metricValue(spend))}}</td>
        <td class="metric-money-cell">${{fmtMoney(metricValue(cpl))}}</td>
        <td class="metric-money-cell">${{fmtMoney(metricValue(cps))}}</td>
      </tr>`;
  }}).join("");
  document.getElementById("lead-anchor-content").innerHTML = `
    <div class="table-wrap">
      <table id="lead-anchor-table"${{leadMetricTableClass()}}>
        ${{leadColgroup()}}
        ${{leadTableHeader()}}
        <tbody>${{rows}}</tbody>
      </table>
    </div>`;
}}

function renderSeedAnchors(payload) {{
  const maxImpressions = Math.max(...payload.seed_anchors.map((anchor) => metricValue(anchorMetric(anchor, "mtd_impressions"))), 1);
  const rows = payload.seed_anchors.map((anchor) => {{
    const mtd = anchorMetric(anchor, "mtd_impressions");
    const daily = anchorMetric(anchor, "daily_impressions");
    return `
      <tr data-search-text="${{escapeHtml(rowSearchText(anchor))}}" data-mtd_impressions="${{metricValue(mtd)}}" data-mtd_impressions_attain_rate="${{Number(mtd.attain_rate ?? 0)}}">
        <th scope="row"><span class="anchor-name">${{escapeHtml(anchor.name)}}</span></th>
        ${{barMetricCells((metricValue(mtd) / maxImpressions) * 100, fmtWan(metricValue(mtd)), "seed")}}
        <td class="metric-number-cell">${{targetValueText(mtd)}}</td>
        <td class="metric-rate-cell">${{rateText(mtd)}}</td>
        <td class="metric-number-cell">${{fmtWan(metricValue(daily))}}</td>
      </tr>`;
  }}).join("");
  document.getElementById("seed-anchor-content").innerHTML = `
    <div class="seed-summary">
      <span>EXEED星途累计曝光</span>
      <strong>${{fmtWan(metricValue(payload.seed_account))}}</strong>
      <span>目标 ${{targetValueText(payload.seed_account)}}</span>
      <span>达成 ${{rateText(payload.seed_account)}}</span>
    </div>
    <div class="table-wrap">
      <table id="seed-anchor-table"${{seedMetricTableClass()}}>
        ${{seedColgroup()}}
        ${{seedTableHeader()}}
        <tbody>${{rows}}</tbody>
      </table>
    </div>`;
}}

function renderSortControlGroup(containerId, tableId, keys, controls) {{
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = keys
    .filter((key) => controls[key])
    .map((key) => {{
      const control = controls[key];
      return `<button type="button" data-sort-table="${{tableId}}" data-sort-key="${{key}}" data-sort-dir="${{control.direction}}">${{escapeHtml(control.label)}}</button>`;
    }})
    .join("");
}}

function renderSortControls(payload) {{
  const leadKeys = payload.interactions?.lead_anchor_sort_keys || [];
  const seedKeys = payload.interactions?.seed_anchor_sort_keys || [];
  renderSortControlGroup("lead-anchor-sort-controls", "lead-anchor-table", leadKeys, LEAD_SORT_CONTROLS);
  renderSortControlGroup("seed-anchor-sort-controls", "seed-anchor-table", seedKeys, SEED_SORT_CONTROLS);
}}

function sortTable(tableId, key, direction) {{
  const table = document.getElementById(tableId);
  if (!table) return;
  const tbody = table.querySelector("tbody");
  const rows = Array.from(tbody.querySelectorAll("tr"));
  const multiplier = direction === "asc" ? 1 : -1;
  rows.sort((a, b) => {{
    const av = Number(a.getAttribute(`data-${{key}}`) || 0);
    const bv = Number(b.getAttribute(`data-${{key}}`) || 0);
    return (av - bv) * multiplier;
  }});
  rows.forEach((row) => tbody.appendChild(row));
}}

function bindSortControls() {{
  document.querySelectorAll("[data-sort-table]").forEach((button) => {{
    if (button.dataset.bound) return;
    button.addEventListener("click", () => {{
      sortTable(button.dataset.sortTable, button.dataset.sortKey, button.dataset.sortDir || "desc");
      document.querySelectorAll(`[data-sort-table="${{button.dataset.sortTable}}"]`).forEach((peer) => {{
        peer.classList.toggle("active-sort", peer === button);
      }});
    }});
    button.dataset.bound = "true";
  }});
}}

function filterTableRows(tableId, query) {{
  const table = document.getElementById(tableId);
  if (!table) return;
  const normalized = String(query || "").trim().toLowerCase();
  table.querySelectorAll("tbody tr").forEach((row) => {{
    const haystack = row.dataset.searchText || row.textContent.toLowerCase();
    row.hidden = normalized ? !haystack.includes(normalized) : false;
  }});
}}

function bindSearchControls() {{
  document.querySelectorAll("[data-filter-table]").forEach((input) => {{
    if (input.dataset.bound) return;
    input.addEventListener("input", () => filterTableRows(input.dataset.filterTable, input.value));
    input.dataset.bound = "true";
  }});
}}

function applySearchFilters() {{
  document.querySelectorAll("[data-filter-table]").forEach((input) => {{
    filterTableRows(input.dataset.filterTable, input.value);
  }});
}}

function populateDateSelect(payload) {{
  const select = document.getElementById("report-date-select");
  if (!select) return;
  const dates = payload.available_report_dates || [];
  const latestLabel = payload.report_date ? `latest (${{payload.report_date}})` : "latest";
  const options = [`<option value="latest">${{escapeHtml(latestLabel)}}</option>`]
    .concat(dates.map((date) => `<option value="${{escapeHtml(date)}}">${{escapeHtml(date)}}</option>`));
  select.innerHTML = options.join("");
  select.value = currentApiPath.endsWith("/latest") ? "latest" : payload.report_date;
  if (!select.dataset.bound) {{
    select.addEventListener("change", () => {{
      const selected = select.value;
      loadDashboard(dashboardPathForSelection(selected));
    }});
    select.dataset.bound = "true";
  }}
}}

function dashboardPathForSelection(value) {{
  return value === "latest" ? "/dashboard/daily/latest" : `/dashboard/daily/${{value}}`;
}}

function businessPadDate(value) {{
  return value.toISOString().slice(0, 10);
}}

function businessQuarterWindowStart(endDate) {{
  const end = new Date(`${{endDate}}T00:00:00`);
  if (Number.isNaN(end.getTime())) return "";
  return businessPadDate(new Date(end.getFullYear(), end.getMonth() - 2, 1));
}}

function businessRangeDays(startDate, endDate) {{
  if (!startDate || !endDate) return 0;
  const start = new Date(`${{startDate}}T00:00:00`);
  const end = new Date(`${{endDate}}T00:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 0;
  return Math.floor((end - start) / 86400000) + 1;
}}

function businessTrendPrototypePath(startDate, endDate) {{
  const url = new URL("/dashboard/daily/trends/prototype", window.location.origin);
  url.searchParams.set("start_date", startDate);
  url.searchParams.set("end_date", endDate);
  return `${{url.pathname}}${{url.search}}`;
}}

function bindBusinessRangeQuery(payload) {{
  const form = document.getElementById("business-range-query");
  if (!form) return;
  const startInput = document.getElementById("business-start-date");
  const endInput = document.getElementById("business-end-date");
  const summary = document.getElementById("business-range-summary");
  const reportDate = payload?.report_date || "";
  if (reportDate && !endInput.value) endInput.value = reportDate;
  if (reportDate && !startInput.value) startInput.value = businessQuarterWindowStart(reportDate);
  if (reportDate) {{
    startInput.max = reportDate;
    endInput.max = reportDate;
  }}
  const updateSummary = () => {{
    const days = businessRangeDays(startInput.value, endInput.value);
    summary.textContent = days > 0 ? `当前范围：${{startInput.value}} 至 ${{endInput.value}}；查看天数：${{days}} / 92` : "三个月内任意时间段，单次查看上限 92 天。";
  }};
  updateSummary();
  if (form.dataset.bound) return;
  form.addEventListener("submit", (event) => {{
    event.preventDefault();
    const days = businessRangeDays(startInput.value, endInput.value);
    if (days <= 0) {{
      summary.textContent = "请选择有效的开始日期和结束日期。";
      return;
    }}
    if (days > 92) {{
      summary.textContent = "单次查看范围建议不超过一个季度，请缩小日期范围。";
      return;
    }}
    window.location.href = businessTrendPrototypePath(startInput.value, endInput.value);
  }});
  startInput.addEventListener("change", updateSummary);
  endInput.addEventListener("change", updateSummary);
  form.dataset.bound = "true";
}}

function isDashboardReadOnlyPath(path) {{
  return path === "/dashboard/daily/latest" || /^\\/dashboard\\/daily\\/\\d{{4}}-\\d{{2}}-\\d{{2}}$/.test(path);
}}

function renderMetadata(payload) {{
  const sourcePath = payload.source?.path || "未提供";
  const reportDateNode = document.getElementById("report-date-value");
  if (reportDateNode) reportDateNode.textContent = payload.report_date || "未提供";
  const sourcePathNode = document.getElementById("source-path-value");
  if (sourcePathNode) {{
    sourcePathNode.textContent = sourcePath;
    sourcePathNode.title = sourcePath;
  }}
  const sourceRowsNode = document.getElementById("source-rows-value");
  if (sourceRowsNode) sourceRowsNode.textContent = fmtInt(payload.source?.rows || 0);
  const readonlyNode = document.getElementById("readonly-status");
  if (readonlyNode) readonlyNode.textContent = READONLY_STATUS_TEXT;
  const freshnessNode = document.getElementById("freshness-value");
  if (freshnessNode) freshnessNode.textContent = payload.report_date ? `${{payload.report_date}} 最新可用日报` : "等待日报数据";
  const previewBoundaryNode = document.getElementById("preview-boundary-value");
  if (previewBoundaryNode) previewBoundaryNode.textContent = "日报详细版";
  const sourcePill = document.querySelector(".source-pill");
  const sourcePillStrong = document.querySelector(".source-pill strong");
  if (sourcePillStrong) sourcePillStrong.textContent = sourcePath;
  if (sourcePill) sourcePill.title = sourcePath;
}}

function trendMetricDisplay(metric) {{
  const value = hasValue(metric?.value) ? metric.value : metric?.actual;
  return fmtMetric({{ ...metric, actual: value }});
}}

function trendMetricCard(metric) {{
  return `
    <article class="metric-card tone-teal">
      <div class="metric-label">${{escapeHtml(metric?.label || metric?.key || "未提供")}}</div>
      <div class="metric-value">${{escapeHtml(trendMetricDisplay(metric || {{}}))}}</div>
      <div class="metric-sub">最新日报</div>
    </article>`;
}}

function renderDailyBiTrendCore(trendPayload) {{
  const container = document.getElementById("daily-bi-trend-core");
  if (!container) return;
  const summary = trendPayload.core_kpi_summary || [];
  container.innerHTML = summary.length
    ? `<div class="metric-grid">${{summary.map(trendMetricCard).join("")}}</div>`
    : `<div class="loading">未提供趋势核心指标</div>`;
}}

function latestPointText(series) {{
  const points = series?.points || [];
  const point = [...points].reverse().find((item) => item?.value !== null && item?.value !== undefined);
  if (!point) return "未提供";
  return `${{point.date || "未提供"}} · ${{fmtMetric({{ key: series?.key || "", unit: series?.unit || "", actual: point.value }})}}`;
}}

function dailyBiSeriesMap(seriesList) {{
  return Object.fromEntries((seriesList || []).map((series) => [series.key, series]));
}}

function dailyBiNormalizePoint(point) {{
  const rawValue = point?.value;
  const value = rawValue === null || rawValue === undefined || rawValue === "" ? null : Number(rawValue);
  return {{
    date: point?.date || "",
    value: Number.isFinite(value) ? value : null,
  }};
}}

function dailyBiRangeLabel(points) {{
  const normalized = (points || []).map(dailyBiNormalizePoint);
  const first = normalized[0]?.date || "未提供";
  const last = normalized[normalized.length - 1]?.date || first;
  return first === last ? first : `${{first}} 至 ${{last}}`;
}}

function dailyBiChartScale(values) {{
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  if (rawMin >= 0) {{
    return {{ min: 0, max: rawMax > 0 ? rawMax * 1.12 : 1 }};
  }}
  const min = rawMin;
  const max = rawMax;
  if (min === max) {{
    const baseline = Math.max(Math.abs(min), 1);
    return {{ min: min - baseline * 0.2, max: max + baseline * 0.2 }};
  }}
  const padding = (max - min) * 0.12;
  return {{ min: min - padding, max: max + padding }};
}}

function dailyBiPointPath(points, scale, dims) {{
  const drawable = points.filter((point) => point.value !== null);
  if (!drawable.length) return "";
  const step = points.length > 1 ? dims.plotWidth / (points.length - 1) : 0;
  return drawable.map((point) => {{
    const index = points.indexOf(point);
    const x = dims.left + step * index;
    const y = dims.top + dims.plotHeight - ((point.value - scale.min) / (scale.max - scale.min)) * dims.plotHeight;
    return `${{x.toFixed(2)}},${{y.toFixed(2)}}`;
  }}).join(" ");
}}

function dailyBiLineChart(series, previousSeries = null) {{
  const points = (series?.points || []).map(dailyBiNormalizePoint);
  const previousPoints = (previousSeries?.points || []).map(dailyBiNormalizePoint);
  const values = [...points, ...previousPoints].map((point) => point.value).filter((value) => value !== null);
  if (!values.length) return `<div class="trend-chart empty-chart">未提供</div>`;
  const width = 720;
  const height = 230;
  const dims = {{ left: 84, right: 18, top: 18, bottom: 42 }};
  dims.plotWidth = width - dims.left - dims.right;
  dims.plotHeight = height - dims.top - dims.bottom;
  const scale = dailyBiChartScale(values);
  const grid = [0, 0.5, 1].map((ratio) => {{
    const y = dims.top + dims.plotHeight * ratio;
    return `<line x1="${{dims.left}}" x2="${{width - dims.right}}" y1="${{y.toFixed(2)}}" y2="${{y.toFixed(2)}}"></line>`;
  }}).join("");
  const yLabels = [scale.max, (scale.max + scale.min) / 2, scale.min].map((value, index) => {{
    const y = dims.top + dims.plotHeight * (index / 2);
    return `<text x="${{dims.left - 10}}" y="${{(y + 4).toFixed(2)}}" text-anchor="end">${{escapeHtml(fmtMetric({{ key: series?.key || "", unit: series?.unit || "", actual: value }}))}}</text>`;
  }}).join("");
  const step = points.length > 1 ? dims.plotWidth / (points.length - 1) : 0;
  const circles = points.map((point, index) => {{
    if (point.value === null) return "";
    const x = dims.left + step * index;
    const y = dims.top + dims.plotHeight - ((point.value - scale.min) / (scale.max - scale.min)) * dims.plotHeight;
    return `<circle class="chart-point current-point" data-index="${{index}}" cx="${{x.toFixed(2)}}" cy="${{y.toFixed(2)}}" r="4" style="animation-delay:${{(index * 24).toFixed(0)}}ms"></circle>`;
  }}).join("");
  const targets = points.map((point, index) => {{
    const x = dims.left + step * index;
    const previous = previousPoints[index] || {{}};
    const valueLabel = point.value === null ? "未提供" : fmtMetric({{ key: series?.key || "", unit: series?.unit || "", actual: point.value }});
    const previousLabel = previous.value === null || previous.value === undefined
      ? "未提供"
      : fmtMetric({{ key: series?.key || "", unit: series?.unit || "", actual: previous.value }});
    const pointLabel = `${{series?.label || series?.key || "指标"}} ${{point.date || "未提供"}} ${{valueLabel}}`;
    return `<rect class="chart-hover-target" tabindex="0" role="img" aria-label="${{escapeHtml(pointLabel)}}" data-index="${{index}}" data-x="${{x.toFixed(2)}}" data-date="${{escapeHtml(point.date || "")}}" data-value-label="${{escapeHtml(valueLabel)}}" data-previous-date="${{escapeHtml(previous.date || "")}}" data-previous-value-label="${{escapeHtml(previousLabel)}}" x="${{(x - Math.max(step / 2, 10)).toFixed(2)}}" y="${{dims.top}}" width="${{Math.max(step, 20).toFixed(2)}}" height="${{dims.plotHeight}}"></rect>`;
  }}).join("");
  const xLabels = points.length
    ? `<text x="${{dims.left}}" y="${{height - 10}}" text-anchor="start">${{escapeHtml(points[0].date)}}</text><text x="${{width - dims.right}}" y="${{height - 10}}" text-anchor="end">${{escapeHtml(points[points.length - 1].date)}}</text>`
    : "";
  const currentPath = dailyBiPointPath(points, scale, dims);
  const previousPath = dailyBiPointPath(previousPoints, scale, dims);
  return `
    <div class="trend-chart daily-bi-chart" data-unit="${{escapeHtml(series?.unit || "")}}" data-metric-label="${{escapeHtml(series?.label || series?.key || "")}}">
      <svg viewBox="0 0 ${{width}} ${{height}}" role="img" aria-label="${{escapeHtml(series?.label || series?.key || "历史趋势")}}">
        <g class="chart-grid">${{grid}}</g>
        <line class="chart-axis axis-line" x1="${{dims.left}}" x2="${{dims.left}}" y1="${{dims.top}}" y2="${{dims.top + dims.plotHeight}}"></line>
        <line class="chart-axis axis-line" x1="${{dims.left}}" x2="${{width - dims.right}}" y1="${{dims.top + dims.plotHeight}}" y2="${{dims.top + dims.plotHeight}}"></line>
        <g class="chart-axis axis-labels">${{yLabels}}${{xLabels}}</g>
        ${{previousPath ? `<polyline class="chart-line previous-line chart-line-draw" points="${{previousPath}}" fill="none"></polyline>` : ""}}
        <polyline class="chart-line current-line chart-line-draw" points="${{currentPath}}" fill="none"></polyline>
        <g class="trend-points">${{circles}}</g>
        <line class="chart-hover-line" x1="${{dims.left}}" x2="${{dims.left}}" y1="${{dims.top}}" y2="${{dims.top + dims.plotHeight}}"></line>
        <g class="chart-hit-area">${{targets}}</g>
      </svg>
      <div class="chart-tooltip" role="status"></div>
    </div>`;
}}

function dailyBiTooltipRows(target, chart) {{
  const label = chart.dataset.metricLabel || "指标";
  const previousDate = target.dataset.previousDate || "";
  return [
    `<strong>${{escapeHtml(target.dataset.date || "未提供")}}</strong>`,
    `<span>${{escapeHtml(label)}}：${{escapeHtml(target.dataset.valueLabel || "未提供")}}</span>`,
    previousDate ? `<span>上一周期 ${{escapeHtml(previousDate)}}：${{escapeHtml(target.dataset.previousValueLabel || "未提供")}}</span>` : "",
  ].filter(Boolean).join("");
}}

function bindDailyBiChartInteractions(root = document) {{
  root.querySelectorAll(".daily-bi-chart").forEach((chart) => {{
    if (chart.dataset.bound === "1") return;
    chart.dataset.bound = "1";
    const tooltip = chart.querySelector(".chart-tooltip");
    const hoverLine = chart.querySelector(".chart-hover-line");
    const points = chart.querySelectorAll(".chart-point");
    const clear = () => {{
      if (tooltip) tooltip.classList.remove("is-visible");
      if (hoverLine) hoverLine.classList.remove("is-visible");
      points.forEach((point) => point.classList.remove("is-active"));
    }};
    chart.querySelectorAll(".chart-hover-target").forEach((target) => {{
      const show = () => {{
        const x = Number(target.dataset.x || 0);
        if (hoverLine) {{
          hoverLine.setAttribute("x1", String(x));
          hoverLine.setAttribute("x2", String(x));
          hoverLine.classList.add("is-visible");
        }}
        points.forEach((point) => point.classList.toggle("is-active", point.dataset.index === target.dataset.index));
        if (tooltip) {{
          tooltip.innerHTML = dailyBiTooltipRows(target, chart);
          tooltip.classList.add("is-visible");
          const scaledX = chart.clientWidth > 0 ? (x / 720) * chart.clientWidth : x;
          const left = Math.min(Math.max(scaledX + 12, 12), Math.max(12, chart.clientWidth - 220));
          tooltip.style.left = `${{left}}px`;
          tooltip.style.top = "18px";
        }}
      }};
      target.addEventListener("mouseenter", show);
      target.addEventListener("focus", show);
    }});
    chart.addEventListener("mouseleave", clear);
    chart.addEventListener("focusout", clear);
  }});
}}

function dailyBiHistoryPanel(series, previousByKey) {{
  const previousSeries = previousByKey?.[series?.key] || null;
  return `
    <article class="trend-panel history-chart-card daily-bi-history-card">
      <div class="trend-panel-header history-card-head">
        <div class="trend-panel-title">
          <h3>${{escapeHtml(series?.label || series?.key || "未提供")}}</h3>
          <span>范围：${{escapeHtml(dailyBiRangeLabel(series?.points || []))}}</span>
        </div>
        <div class="trend-panel-value">
          <small>最新值</small>
          <strong>${{escapeHtml(latestPointText(series))}}</strong>
        </div>
        <div class="trend-panel-meta">
          <span>可悬停查看日期值</span>
        </div>
      </div>
      ${{dailyBiLineChart(series, previousSeries)}}
    </article>`;
}}

function renderDailyBiHistory(trendPayload) {{
  const container = document.getElementById("daily-bi-history");
  if (!container) return;
  const trends = trendPayload.daily_trends || [];
  const previousByKey = dailyBiSeriesMap(trendPayload.previous_period_trends || []);
  container.innerHTML = trends.length
    ? `<div class="daily-bi-history-grid history-chart-grid">${{trends.map((series) => dailyBiHistoryPanel(series, previousByKey)).join("")}}</div>`
    : `<div class="loading">未提供历史趋势</div>`;
  bindDailyBiChartInteractions(container);
}}

function monthlyMetricRow(row) {{
  const metrics = row?.metrics || {{}};
  const keys = ["impressions", "leads", "douyin_laike_orders", "deals", "spend", "cpl", "cps"];
  return `
    <article class="monthly-card daily-bi-month-card">
      <header class="daily-bi-month-head">
        <span>月度</span>
        <h3>${{escapeHtml(row?.label || row?.month || "未提供")}}</h3>
        <small>日报源表</small>
      </header>
      <div class="daily-bi-month-metrics">
        ${{keys.map((key) => {{
          const metric = metrics[key] || {{ key, label: key, value: null, unit: "" }};
          return `<span data-month-metric="${{escapeHtml(key)}}"><small>${{escapeHtml(metric.label || key)}}</small><strong>${{escapeHtml(trendMetricDisplay(metric))}}</strong></span>`;
        }}).join("")}}
      </div>
    </article>`;
}}

function renderDailyBiMonthlyComparison(trendPayload) {{
  const container = document.getElementById("daily-bi-monthly-comparison");
  if (!container) return;
  const rows = trendPayload.monthly_comparison || [];
  container.innerHTML = rows.length
    ? `<div class="section-subhead"><h3>月度对比</h3><p>仅使用日报源表历史文件。</p></div><div class="monthly-grid">${{rows.map(monthlyMetricRow).join("")}}</div>`
    : `<div class="loading">未提供月度对比</div>`;
}}

function dailyBiTrendPath(payload) {{
  const url = new URL(TREND_API_PATH, window.location.origin);
  if (payload?.report_date) url.searchParams.set("end_date", payload.report_date);
  return `${{url.pathname}}${{url.search}}`;
}}

function isTrendReadOnlyPath(path) {{
  try {{
    const url = new URL(path, window.location.origin);
    return url.pathname === TREND_API_PATH;
  }} catch (error) {{
    return path === TREND_API_PATH;
  }}
}}

async function fetchDashboardTrend(path) {{
  if (!isTrendReadOnlyPath(path)) throw new Error("禁止访问非只读趋势 API");
  return fetch(path, {{ method: "GET" }});
}}

async function loadDailyBiTrends(payload) {{
  if (!document.getElementById("daily-bi-trends")) return;
  const path = dailyBiTrendPath(payload);
  try {{
    const response = await fetchDashboardTrend(path);
    if (!response.ok) throw new Error(`API ${{response.status}}`);
    const trendPayload = await response.json();
    renderDailyBiTrendCore(trendPayload);
    renderDailyBiHistory(trendPayload);
    renderDailyBiMonthlyComparison(trendPayload);
  }} catch (error) {{
    ["daily-bi-trend-core", "daily-bi-history", "daily-bi-monthly-comparison"].forEach((id) => {{
      const node = document.getElementById(id);
      if (node) node.innerHTML = `<div class="loading">未提供：${{escapeHtml(error.message)}}</div>`;
    }});
  }}
}}

function renderDashboard(payload) {{
  document.querySelector("h1").textContent = `${{PAGE_TITLE_PREFIX}} · ${{payload.report_date}}`;
  renderMetadata(payload);
  populateDateSelect(payload);
  bindBusinessRangeQuery(payload);
  renderDecision(payload);
  renderOverview(payload);
  renderFunnel(payload);
  renderWorkbench(payload);
  renderLeadAnchors(payload);
  renderSeedAnchors(payload);
  loadDailyBiTrends(payload);
  renderSortControls(payload);
  bindSortControls();
  bindSearchControls();
  applySearchFilters();
}}

async function fetchDashboard(path) {{
  if (!isDashboardReadOnlyPath(path)) {{
    throw new Error("禁止访问非只读 Dashboard API");
  }}
  return fetch(path, {{ method: "GET" }});
}}

async function loadDashboard(path = API_PATH) {{
  currentApiPath = path;
  try {{
    const response = await fetchDashboard(path);
    if (!response.ok) throw new Error(`API ${{response.status}}`);
    const payload = await response.json();
    renderDashboard(payload);
  }} catch (error) {{
    document.querySelectorAll(".loading").forEach((node) => {{
      node.textContent = `${{FAILURE_PREFIX}}：${{error.message}}`;
    }});
  }}
}}

loadDashboard();
"""


def _trend_js(api_path: str) -> str:
    return f"""
const DATA_URL = "{_script_string(api_path)}";
const CORE_KPI_KEYS = ["impressions", "leads", "douyin_laike_orders", "deals", "spend", "cpl", "cps"];
let currentRangeMode = "custom";
let latestAvailableDate = "";

function escapeHtml(value) {{
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({{
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\\"": "&quot;",
    "'": "&#39;"
  }}[char]));
}}

function hasValue(value) {{
  return value !== null && value !== undefined;
}}

function fmtFloat(value) {{
  return Number(value || 0).toLocaleString("zh-CN", {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
}}

function fmtInt(value) {{
  return Number(value || 0).toLocaleString("zh-CN", {{ maximumFractionDigits: 0 }});
}}

function fmtWan(value) {{
  return `${{fmtFloat(Number(value || 0) / 10000)}}万`;
}}

function fmtMoney(value) {{
  return `¥${{fmtFloat(value)}}`;
}}

function fmtMoneyWan(value) {{
  const numeric = Number(value || 0);
  return Math.abs(numeric) >= 10000 ? `¥${{fmtFloat(numeric / 10000)}}万` : fmtMoney(numeric);
}}

function isUnitCost(unit) {{
  return String(unit || "").includes("/");
}}

function fmtPct(value) {{
  return `${{fmtFloat(Number(value || 0) * 100)}}%`;
}}

function normalizePoint(point) {{
  const date = point?.date || point?.report_date || "";
  if (!point) return {{ date, value: null }};
  if (Object.prototype.hasOwnProperty.call(point, "value")) {{
    if (point.value === null || point.value === undefined || Number.isNaN(Number(point.value))) return {{ date, value: null }};
    return {{ date, value: Number(point.value) }};
  }}
  if (point.is_missing) return {{ date, value: null }};
  if (point.actual === null || point.actual === undefined || Number.isNaN(Number(point.actual))) return {{ date, value: null }};
  return {{ date, value: Number(point.actual) }};
}}

function metricPointValue(point) {{
  const normalized = normalizePoint(point);
  if (normalized.value === null) return null;
  return Number(normalized.value);
}}

function latestTrendPoint(points) {{
  const normalized = (points || []).map(normalizePoint).filter((point) => point.value !== null);
  return normalized[normalized.length - 1] || {{ date: "", value: null }};
}}

function rangeLabelFromPoints(points) {{
  const normalized = (points || []).map(normalizePoint);
  const first = normalized[0]?.date || "";
  const last = normalized[normalized.length - 1]?.date || "";
  return first && last ? `${{first}} 至 ${{last}}` : "未提供";
}}

function fmtMetricValue(value, unit = "") {{
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "未提供";
  const numeric = Number(value);
  if (unit.includes("元")) return isUnitCost(unit) ? fmtMoney(numeric) : fmtMoneyWan(numeric);
  if (unit.includes("人次")) return fmtWan(value);
  if (unit.includes("比例")) return fmtPct(numeric);
  return fmtInt(value);
}}

function fmtPoint(point, unit = "") {{
  return fmtMetricValue(metricPointValue(point), unit || point?.unit || "");
}}

function targetText(metric) {{
  if (!hasValue(metric?.target)) return "未提供";
  return fmtMetricValue(metric.target, metric.unit || "");
}}

function rateText(metric) {{
  if (!hasValue(metric?.attain_rate)) return "未提供";
  return fmtPct(metric.attain_rate);
}}

function isCostMetric(metric) {{
  const key = String(metric?.key || "").toLowerCase();
  const label = String(metric?.label || "").toLowerCase();
  return key.includes("cpl") || key.includes("cps") || label.includes("cpl") || label.includes("cps");
}}

function isSpendMetric(metric) {{
  const key = String(metric?.key || "").toLowerCase();
  const label = String(metric?.label || "").toLowerCase();
  return key === "spend" || key === "mtd_spend" || label === "费用";
}}

function metricProgressRate(metric) {{
  if (hasValue(metric?.attain_rate)) return Number(metric.attain_rate);
  if (!hasValue(metric?.actual) || !hasValue(metric?.target)) return null;
  if (Number(metric.actual) <= 0 || Number(metric.target) <= 0) return null;
  if (isCostMetric(metric)) return Number(metric.target) / Number(metric.actual);
  return null;
}}

function metricLine(metric) {{
  const lines = [];
  if (hasValue(metric?.target)) lines.push(`<span>目标参考：${{escapeHtml(targetText(metric))}}</span>`);
  if (isSpendMetric(metric)) {{
    return lines.join("");
  }}
  if (isCostMetric(metric)) {{
    if (hasValue(metricProgressRate(metric))) lines.push(`<span>成本比值：${{escapeHtml(rateText(metric))}}</span>`);
    return lines.join("");
  }}
  if (hasValue(metricProgressRate(metric))) lines.push(`<span>当前 / 目标：${{escapeHtml(rateText(metric))}}</span>`);
  return lines.join("");
}}

function progressBar(metric) {{
  const progressRate = metricProgressRate(metric);
  if (!hasValue(progressRate)) {{
    return "";
  }}
  const width = Math.max(0, Math.min(progressRate * 100, 100));
  const label = isCostMetric(metric) ? "成本比值" : "当前 / 目标";
  return `<div class="progress-bar" aria-label="${{escapeHtml(label)}} ${{escapeHtml(rateText(metric))}}"><span class="progress-fill" style="width:${{width.toFixed(2)}}%"></span></div>`;
}}

function pointsFromMetric(metric) {{
  return metric?.trend || metric?.points || [];
}}

function metricToneClass(tone) {{
  return tone ? ` tone-${{tone}}` : "";
}}

function seriesMap(seriesList) {{
  return Object.fromEntries((seriesList || []).map((series) => [series.key, series]));
}}

function lastDayOfMonth(dateText) {{
  const [year, month] = String(dateText).split("-").map(Number);
  return new Date(year, month, 0).getDate();
}}

function dateLabel(dateText) {{
  const parts = String(dateText || "").split("-");
  return parts.length === 3 ? `${{parts[1]}}-${{parts[2]}}` : dateText;
}}

function dateAxisLabel(dateText) {{
  const label = dateLabel(dateText);
  return label ? `${{label}} ·` : "";
}}

function selectDateTicks(points) {{
  const normalized = (points || []).map(normalizePoint);
  if (!normalized.length) return [];
  const selected = new Set([0, normalized.length - 1]);
  if (normalized.length <= 31) {{
    const target = Math.min(5, normalized.length);
    for (let i = 0; i < target; i += 1) {{
      selected.add(Math.round((i * (normalized.length - 1)) / Math.max(target - 1, 1)));
    }}
  }} else {{
    normalized.forEach((point, index) => {{
      const day = Number(String(point.date).slice(-2));
      if (day === 1 || day === 15 || day === lastDayOfMonth(point.date) || index % 14 === 0) selected.add(index);
    }});
    const ordered = Array.from(selected).sort((a, b) => a - b);
    if (ordered.length > 6) {{
      selected.clear();
      selected.add(0);
      selected.add(normalized.length - 1);
      for (let i = 1; i < 4; i += 1) selected.add(Math.round((i * (normalized.length - 1)) / 4));
    }}
  }}
  return Array.from(selected).sort((a, b) => a - b);
}}

function chartScale(values) {{
  if (!values.length) return {{ min: 0, max: 1, span: 1 }};
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (min >= 0) min = 0;
  if (min === max) {{
    const pad = Math.max(Math.abs(max) * 0.15, 1);
    min = min >= 0 ? 0 : min - pad;
    max += pad;
  }}
  const span = max - min || 1;
  return {{ min, max, span }};
}}

function chartY(value, scale, top, plotHeight) {{
  return top + plotHeight - ((Number(value) - scale.min) / scale.span) * plotHeight;
}}

function lineSegments(points, scale, dims, className, seriesName) {{
  const normalized = (points || []).map(normalizePoint);
  const step = normalized.length > 1 ? dims.plotWidth / (normalized.length - 1) : dims.plotWidth;
  const segments = [];
  let current = [];
  normalized.forEach((point, index) => {{
    if (point.value === null) {{
      if (current.length) segments.push(current);
      current = [];
      return;
    }}
    const x = dims.left + index * step;
    const y = chartY(point.value, scale, dims.top, dims.plotHeight);
    current.push(`${{x.toFixed(2)}},${{y.toFixed(2)}}`);
  }});
  if (current.length) segments.push(current);
  return segments.map((segment) => `<polyline class="${{className}} chart-line-draw" data-series="${{escapeHtml(seriesName)}}" points="${{segment.join(" ")}}" fill="none"></polyline>`).join("");
}}

function chartPoints(points, scale, dims, className, seriesName) {{
  const normalized = (points || []).map(normalizePoint);
  const step = normalized.length > 1 ? dims.plotWidth / (normalized.length - 1) : dims.plotWidth;
  return normalized.map((point, index) => {{
    if (point.value === null) return "";
    const x = dims.left + index * step;
    const y = chartY(point.value, scale, dims.top, dims.plotHeight);
    return `<circle class="${{className}} chart-point" data-series="${{escapeHtml(seriesName)}}" data-index="${{index}}" data-date="${{escapeHtml(point.date)}}" data-value="${{escapeHtml(point.value)}}" cx="${{x.toFixed(2)}}" cy="${{y.toFixed(2)}}" r="3.4"></circle>`;
  }}).join("");
}}

function trendLineChart(series, previousSeries = null, options = {{}}) {{
  const points = (series?.points || []).map(normalizePoint);
  const previousPoints = (previousSeries?.points || []).map(normalizePoint);
  const hasPreviousValues = previousPoints.some((point) => point.value !== null);
  const values = [
    ...points.map((point) => point.value),
    ...previousPoints.map((point) => point.value),
  ].filter((value) => value !== null);
  if (!values.length) return `<div class="trend-chart empty-chart">未提供</div>`;
  const compact = options.compact === true;
  const featured = options.featured === true;
  const width = compact ? 560 : featured ? 700 : 760;
  const height = compact ? 180 : featured ? 260 : 340;
  const dims = compact
    ? {{ left: 84, right: 18, top: 18, bottom: 42, width, height }}
    : featured
      ? {{ left: 92, right: 22, top: 28, bottom: 48, width, height }}
      : {{ left: 102, right: 22, top: 28, bottom: 52, width, height }};
  dims.plotWidth = width - dims.left - dims.right;
  dims.plotHeight = height - dims.top - dims.bottom;
  const scale = chartScale(values);
  const yTicks = [0, 0.5, 1].map((ratio) => scale.min + scale.span * ratio);
  const xTicks = selectDateTicks(points);
  const step = points.length > 1 ? dims.plotWidth / (points.length - 1) : dims.plotWidth;
  const grid = yTicks.map((tick) => {{
    const y = chartY(tick, scale, dims.top, dims.plotHeight);
    return `<line x1="${{dims.left}}" x2="${{width - dims.right}}" y1="${{y.toFixed(2)}}" y2="${{y.toFixed(2)}}"></line>`;
  }}).join("");
  const yAxis = yTicks.map((tick) => {{
    const y = chartY(tick, scale, dims.top, dims.plotHeight);
    return `<text x="${{dims.left - 8}}" y="${{(y + 4).toFixed(2)}}">${{escapeHtml(fmtMetricValue(tick, series?.unit || ""))}}</text>`;
  }}).join("\\n");
  const xAxis = xTicks.map((index) => {{
    const x = dims.left + index * step;
    const point = points[index] || {{}};
    return `<text x="${{x.toFixed(2)}}" y="${{height - 16}}" data-date="${{escapeHtml(point.date || "")}}">${{escapeHtml(dateAxisLabel(point.date || ""))}}</text>`;
  }}).join("\\n");
  const currentLine = lineSegments(points, scale, dims, "chart-line current-line", "current");
  const previousLine = hasPreviousValues ? lineSegments(previousPoints, scale, dims, "chart-line previous-line", "previous") : "";
  const currentPoints = chartPoints(points, scale, dims, "current-point", "current");
  const previousCircles = hasPreviousValues ? chartPoints(previousPoints, scale, dims, "previous-point", "previous") : "";
  const targets = points.map((point, index) => {{
    const x = dims.left + index * step;
    const previous = previousPoints[index] || {{ date: "", value: null }};
    const pointLabel = `${{series?.label || series?.key || "指标"}} ${{point.date || ""}}`;
    return `<rect class="chart-hover-target" tabindex="0" role="img" aria-label="${{escapeHtml(pointLabel)}}" data-index="${{index}}" data-x="${{x.toFixed(2)}}" data-date="${{escapeHtml(point.date || "")}}" data-value="${{escapeHtml(point.value ?? "")}}" data-previous-date="${{escapeHtml(previous.date || "")}}" data-previous-value="${{escapeHtml(previous.value ?? "")}}" x="${{(x - step / 2).toFixed(2)}}" y="${{dims.top}}" width="${{Math.max(step, 12).toFixed(2)}}" height="${{dims.plotHeight}}"></rect>`;
  }}).join("");
  const legend = hasPreviousValues
    ? `<div class="chart-legend"><span><i class="legend-current"></i>本期</span>
        <span><i class="legend-previous"></i>上一周期</span></div>`
    : `<div class="chart-legend"><span><i class="legend-current"></i>当前范围</span></div>`;
  return `
    <div class="trend-chart${{compact ? " compact-chart" : ""}}${{featured ? " featured-chart" : ""}}" data-unit="${{escapeHtml(series?.unit || "")}}" data-metric-label="${{escapeHtml(series?.label || series?.key || "")}}">
      ${{legend}}
      <svg viewBox="0 0 ${{width}} ${{height}}" role="img" aria-label="${{escapeHtml(series?.label || series?.key || "趋势图")}}">
        <g class="chart-grid">${{grid}}</g>
        <line class="y-axis axis-line chart-axis" x1="${{dims.left}}" x2="${{dims.left}}" y1="${{dims.top}}" y2="${{dims.top + dims.plotHeight}}"></line>
        <line class="x-axis axis-line chart-axis" x1="${{dims.left}}" x2="${{width - dims.right}}" y1="${{dims.top + dims.plotHeight}}" y2="${{dims.top + dims.plotHeight}}"></line>
        <g class="y-axis axis-labels chart-axis">${{yAxis}}</g>
        <g class="x-axis axis-labels chart-axis">${{xAxis}}</g>
        ${{previousLine}}
        ${{currentLine}}
        ${{previousCircles}}
        ${{currentPoints}}
        <line class="chart-hover-line" x1="${{dims.left}}" x2="${{dims.left}}" y1="${{dims.top}}" y2="${{dims.top + dims.plotHeight}}"></line>
        <g class="chart-hit-area">${{targets}}</g>
      </svg>
      <div class="chart-tooltip" role="status"></div>
    </div>`;
}}

function compactTrendChart(label, points, unit = "") {{
  const series = {{ key: label, label, unit, points }};
  const normalized = (points || []).map(normalizePoint);
  const first = normalized[0]?.date || "";
  const last = normalized[normalized.length - 1]?.date || "";
  return `
    <div class="mini-trend-block">
      <div class="mini-trend-head"><span>${{escapeHtml(label)}}</span>
        <small>范围：${{escapeHtml(first)}} 至 ${{escapeHtml(last)}}</small></div>
      ${{trendLineChart(series, null, {{ compact: true }})}}
    </div>`;
}}

function featuredTrendChart(label, points, unit = "") {{
  const series = {{ key: label, label, unit, points }};
  const normalized = (points || []).map(normalizePoint);
  const first = normalized[0]?.date || "";
  const last = normalized[normalized.length - 1]?.date || "";
  return `
    <div class="featured-trend-block">
      <div class="mini-trend-head"><span>${{escapeHtml(label)}}</span>
        <small>范围：${{escapeHtml(first)}} 至 ${{escapeHtml(last)}}</small></div>
      ${{trendLineChart(series, null, {{ featured: true }})}}
    </div>`;
}}

function kpiTooltip(metric) {{
  const label = metric?.label || metric?.key || "未提供";
  const unit = metric?.unit || "未提供";
  const parts = [`指标：${{label}}`, `单位：${{unit || "未提供"}}`];
  if (hasValue(metric?.target)) parts.push(`目标参考：${{targetText(metric)}}`);
  if (isSpendMetric(metric)) {{
    parts.push("当前范围内费用汇总");
  }} else if (isCostMetric(metric)) {{
    parts.push("成本效率");
    if (hasValue(metricProgressRate(metric))) parts.push(`成本比值：${{rateText(metric)}}`);
  }} else {{
    if (hasValue(metricProgressRate(metric))) parts.push(`当前 / 目标：${{rateText(metric)}}`);
  }}
  return parts.join("；");
}}

function trendCard(metric, tone) {{
  const tooltip = kpiTooltip(metric || {{}});
  return `
    <article class="kpi-card" tabindex="0" data-kpi-key="${{escapeHtml(metric?.key || "")}}" aria-label="${{escapeHtml(metric?.label || metric?.key || "核心指标")}}">
      <div class="business-label">${{escapeHtml(metric?.label || metric?.key || "未提供")}}</div>
      <div class="business-value">${{escapeHtml(fmtMetricValue(metric?.actual, metric?.unit || ""))}}</div>
      ${{metricLine(metric || {{}}) ? `<div class="business-sub">${{metricLine(metric || {{}})}}</div>` : ""}}
      ${{progressBar(metric || {{}})}}
      <div class="kpi-card-help" role="tooltip">${{escapeHtml(tooltip)}}</div>
    </article>`;
}}

function historyPanel(series, previousByKey) {{
  const previousSeries = previousByKey?.[series?.key] || null;
  const latest = latestTrendPoint(series?.points || []);
  const currentRange = rangeLabelFromPoints(series?.points || []);
  const previousHasValues = (previousSeries?.points || []).map(normalizePoint).some((point) => point.value !== null);
  const periodState = previousHasValues ? "本期 / 上一周期" : "当前范围";
  return `
    <article class="trend-panel history-chart-card">
      <div class="trend-panel-header history-card-head">
        <div class="trend-panel-title">
          <h3>${{escapeHtml(series.label || series.key)}}</h3>
          <span>范围：${{escapeHtml(currentRange)}}</span>
        </div>
        <div class="trend-panel-value">
          <small>最新值</small>
          <strong>${{escapeHtml(fmtMetricValue(latest.value, series.unit || ""))}}</strong>
        </div>
        <div class="trend-panel-meta">
          <span>${{escapeHtml(periodState)}}</span>
        </div>
      </div>
      ${{trendLineChart(series, previousSeries)}}
    </article>`;
}}

function metric(entity, key) {{
  return entity?.metrics?.[key] || {{ key, label: key, actual: null, target: null, attain_rate: null, unit: "" }};
}}

function miniMetric(label, item) {{
  return `<span><small>${{escapeHtml(label)}}</small><strong>${{escapeHtml(fmtMetricValue(item?.actual, item?.unit || ""))}}</strong></span>`;
}}

function metricGroup(title, metrics) {{
  const items = Object.values(metrics || {{}}).map((item) => `
    <span>
      <small>${{escapeHtml(item.label || item.key)}}</small>
      <strong>${{escapeHtml(metricDisplayText(item))}}</strong>
      ${{metricStatusNote(item)}}
    </span>`).join("");
  return `<div class="metric-group"><h4>${{escapeHtml(title)}}</h4><div>${{items}}</div></div>`;
}}

function metricDisplayText(item) {{
  if (item?.source_status === "not_applicable") return "不可计算";
  if (item?.source_status === "not_connected") return "未提供";
  return fmtMetricValue(item?.actual, item?.unit || "");
}}

function metricStatusNote(item) {{
  if (item?.source_status !== "not_applicable" || !item?.note) return "";
  return `<em class="metric-status-note">${{escapeHtml(item.note)}}</em>`;
}}

function detailCard(entity, className) {{
  const primary = metric(entity, "leads");
  const sub = entity?.parent_scope || "当日未开播";
  return `
    <article class="${{className}}">
      <div class="card-title-row">
        <div>
          <h3>${{escapeHtml(entity?.name || "未提供")}}</h3>
          <p>${{escapeHtml(sub)}}</p>
        </div>
      </div>
      <div class="card-measure">
        <span>风车线索（去重）</span>
        <strong>${{escapeHtml(fmtMetricValue(primary.actual, primary.unit || ""))}}</strong>
      </div>
      <div class="business-sub">
        ${{metricLine(primary)}}
      </div>
      ${{progressBar(primary)}}
      ${{compactTrendChart("线索趋势", entity?.daily_trends?.leads || [], primary.unit || "")}}
      ${{Object.entries(entity?.metric_groups || {{}}).map(([title, items]) => metricGroup(title, items)).join("")}}
    </article>`;
}}

const HIDDEN_ACCOUNT_NAMES = new Set([
  "视频号-星途星纪元",
  "星途星纪元",
  "星途星纪元直播营销中心+",
  "抖音",
  "快手-星途星纪元",
  "抖店",
]);

const ACCOUNT_SORT_OPTIONS = {{
  default: {{ label: "默认排序" }},
  leads: {{ label: "风车线索（去重）" }},
  deals: {{ label: "成交数" }},
  spend: {{ label: "费用" }},
  cpl: {{ label: "CPL" }},
  cps: {{ label: "CPS" }},
  target_rate: {{ label: "当前 / 目标" }},
}};

const ACCOUNT_FILTERS = {{
  all: {{ label: "全部账号" }},
  has_target: {{ label: "有目标参考" }},
  target_missing: {{ label: "目标未提供" }},
  has_deals: {{ label: "有成交" }},
  has_spend: {{ label: "有费用" }},
  over_100: {{ label: "比率超过 100%" }},
}};

const accountListState = {{ search: "", sort: "default", filter: "all" }};
let accountListSource = [];
const expandedAccountNames = new Set();

function shouldShowAccount(entity) {{
  return !HIDDEN_ACCOUNT_NAMES.has(String(entity?.name || "").trim());
}}

function encodedTrendPayload(label, points, unit = "") {{
  return escapeHtml(JSON.stringify({{ label, points: points || [], unit }}));
}}

function accountTrendSwitcher(entity) {{
  const leads = metric(entity, "leads");
  const deals = metric(entity, "deals");
  const leadsPayload = encodedTrendPayload("线索趋势", entity?.daily_trends?.leads || [], leads.unit || "条");
  const dealsPayload = encodedTrendPayload("成交趋势", entity?.daily_trends?.deals || [], deals.unit || "台");
  return `
    <div class="account-trend-switcher" data-account-trend data-active-trend="leads" data-trend-leads="${{leadsPayload}}" data-trend-deals="${{dealsPayload}}">
      <div class="account-trend-toolbar">
        <span>账号趋势</span>
        <div class="account-trend-buttons" role="group" aria-label="账号趋势指标">
          <button type="button" class="is-active" data-account-trend-key="leads" aria-pressed="true">线索</button>
          <button type="button" data-account-trend-key="deals" aria-pressed="false">成交</button>
        </div>
      </div>
      <div class="account-trend-pane is-active" data-account-trend-panel>
        ${{compactTrendChart("线索趋势", entity?.daily_trends?.leads || [], leads.unit || "条")}}
	      </div>
	    </div>`;
}}

function accountDisplayName(entity) {{
  return String(entity?.name || "未提供").trim();
}}

function accountMetricCell(label, item) {{
  return `
    <span>
      <small>${{escapeHtml(label)}}</small>
      <strong>${{escapeHtml(metricDisplayText(item))}}</strong>
      ${{metricStatusNote(item)}}
    </span>`;
}}

function accountTargetSummary(metricItem) {{
  if (!hasValue(metricItem?.target) || !hasValue(metricItem?.attain_rate)) return "";
  return accountMetricCell("当前 / 目标", {{ ...metricItem, actual: metricItem.attain_rate, unit: "比例" }});
}}

function accountOver100Summary(entity) {{
  return accountMetrics(entity)
    .filter((item) => item?.source_status !== "not_connected")
    .filter((item) => item?.unit?.includes("比例") && accountMetricNumber(item) !== null && accountMetricNumber(item) > 1)
    .map((item) => accountMetricCell(item.label || item.key || "比率超过 100%", item))
    .join("");
}}

function accountNotApplicableSummary(entity) {{
  return [["到店率", "visit_rate"], ["到店成交率", "visit_deal_rate"]]
    .map(([label, key]) => {{
      const item = metric(entity, key);
      return item?.source_status === "not_applicable" ? accountMetricCell(label, item) : "";
    }})
    .join("");
}}

function accountSummaryGrid(entity) {{
  const leads = metric(entity, "leads");
  const deals = metric(entity, "deals");
  const spend = metric(entity, "spend");
  const cpl = metric(entity, "cpl");
  const cps = metric(entity, "cps");
  return `
    <div class="account-summary-grid">
      ${{accountMetricCell("风车线索（去重）", leads)}}
      ${{accountMetricCell("成交数", deals)}}
      ${{accountMetricCell("费用", spend)}}
      ${{accountMetricCell("CPL", cpl)}}
      ${{accountMetricCell("CPS", cps)}}
      ${{accountTargetSummary(leads)}}
      ${{accountOver100Summary(entity)}}
      ${{accountNotApplicableSummary(entity)}}
    </div>`;
}}

function accountMetricGroup(title, pairs, entity) {{
  const items = pairs.map(([label, key]) => accountMetricCell(label, metric(entity, key))).join("");
  return `<div class="metric-group account-metric-group"><h4>${{escapeHtml(title)}}</h4><div>${{items}}</div></div>`;
}}

function accountDetailPanel(entity, expanded) {{
  const panelClass = expanded ? "account-detail-panel is-expanded" : "account-detail-panel";
  return `
    <div class="${{panelClass}}"${{expanded ? "" : " hidden"}} aria-hidden="${{expanded ? "false" : "true"}}">
      ${{accountMetricGroup("线索组", [["风车线索（去重）", "leads"]], entity)}}
      ${{accountMetricGroup("抖音来客订单", [["抖音来客订单（去重）", "douyin_laike_orders"]], entity)}}
      ${{accountMetricGroup("到店组", [["到店数", "visits"], ["到店率", "visit_rate"], ["到店成交率", "visit_deal_rate"]], entity)}}
      ${{accountMetricGroup("成交组", [["成交数", "deals"], ["线索成交率", "lead_deal_rate"]], entity)}}
      ${{accountMetricGroup("成本组", [["费用", "spend"], ["CPL", "cpl"], ["CPS", "cps"]], entity)}}
    </div>`;
}}

function accountDetailCard(entity, className) {{
  const primary = metric(entity, "leads");
  const sub = entity?.parent_scope || "账号汇总";
  const name = accountDisplayName(entity);
  const expanded = expandedAccountNames.has(name);
  return `
    <article class="${{className}}" data-account-name="${{escapeHtml(name)}}">
      <div class="card-title-row">
        <div>
          <h3>${{escapeHtml(name)}}</h3>
          <p>${{escapeHtml(sub)}}</p>
        </div>
        <button type="button" class="account-detail-toggle" data-account-detail-toggle aria-expanded="${{expanded ? "true" : "false"}}">${{expanded ? "收起详情" : "展开详情"}}</button>
      </div>
      ${{accountSummaryGrid(entity)}}
      ${{accountTrendSwitcher(entity)}}
      ${{accountDetailPanel(entity, expanded)}}
    </article>`;
}}

function featuredAccountCard(entity) {{
  const primary = metric(entity, "leads");
  const deals = metric(entity, "deals");
  return `
    <article class="account-card featured-account-card">
      <div class="card-title-row">
        <div>
          <h3>快手-EXEED星途趋势</h3>
          <p>${{escapeHtml(entity?.name || "快手-EXEED星途")}}</p>
        </div>
      </div>
      <div class="account-card-topline featured-topline">
        <div class="card-measure">
          <span>风车线索（去重）</span>
          <strong>${{escapeHtml(fmtMetricValue(primary.actual, primary.unit || ""))}}</strong>
        </div>
        <div class="card-measure secondary">
          <span>成交数</span>
          <strong>${{escapeHtml(fmtMetricValue(deals.actual, deals.unit || ""))}}</strong>
        </div>
      </div>
      <div class="business-sub">
        ${{metricLine(primary)}}
      </div>
      ${{progressBar(primary)}}
      ${{accountSummaryGrid(entity)}}
      <div class="account-featured-trend-grid">
        ${{featuredTrendChart("线索趋势", entity?.daily_trends?.leads || [], primary.unit || "条")}}
        ${{featuredTrendChart("成交趋势", entity?.daily_trends?.deals || [], deals.unit || "台")}}
      </div>
    </article>`;
}}

function accountMetricNumber(item) {{
  if (!item || item?.source_status === "not_connected") return null;
  if (item.actual === null || item.actual === undefined || Number.isNaN(Number(item.actual))) return null;
  return Number(item.actual);
}}

function accountMetrics(entity) {{
  return Object.values(entity?.metrics || {{}});
}}

function accountHasTarget(entity) {{
  return accountMetrics(entity).some((item) => hasValue(item?.target));
}}

function accountHasNotConnectedField(entity) {{
  return accountMetrics(entity).some((item) => item?.source_status === "not_connected");
}}

function accountHasOver100Ratio(entity) {{
  return accountMetrics(entity).some((item) => {{
    const actual = accountMetricNumber(item);
    const unit = item?.unit || "";
    if (unit.includes("比例") && actual !== null && actual > 1) return true;
    return hasValue(item?.attain_rate) && Number(item.attain_rate) > 1;
  }});
}}

function accountSortValue(entity, key) {{
  if (key === "target_rate") {{
    const rates = accountMetrics(entity)
      .map((item) => hasValue(item?.attain_rate) ? Number(item.attain_rate) : null)
      .filter((value) => value !== null && Number.isFinite(value));
    return rates.length ? Math.max(...rates) : null;
  }}
  const metricKey = {{
    leads: "leads",
    deals: "deals",
    spend: "spend",
    cpl: "cpl",
    cps: "cps",
  }}[key] || "leads";
  return accountMetricNumber(metric(entity, metricKey));
}}

function compareAccountsByState(a, b, accountOrder) {{
  if (accountListState.sort === "default") return (accountOrder.get(a) || 0) - (accountOrder.get(b) || 0);
  const av = accountSortValue(a, accountListState.sort);
  const bv = accountSortValue(b, accountListState.sort);
  if (av === null && bv === null) return (accountOrder.get(a) || 0) - (accountOrder.get(b) || 0);
  if (av === null) return 1;
  if (bv === null) return -1;
  return (bv - av) || ((accountOrder.get(a) || 0) - (accountOrder.get(b) || 0));
}}

function accountMatchesSearch(entity) {{
  const query = accountListState.search.trim().toLowerCase();
  if (!query) return true;
  return accountDisplayName(entity).toLowerCase().includes(query);
}}

function accountMatchesFilter(entity, filterKey = accountListState.filter) {{
  if (filterKey === "all") return true;
  if (filterKey === "has_target") return accountHasTarget(entity);
  if (filterKey === "target_missing") return !accountHasTarget(entity);
  if (filterKey === "has_deals") return (accountMetricNumber(metric(entity, "deals")) || 0) > 0;
  if (filterKey === "has_spend") return (accountMetricNumber(metric(entity, "spend")) || 0) !== 0;
  if (filterKey === "over_100") return accountHasOver100Ratio(entity);
  return true;
}}

function accountMatchesAccountState(entity) {{
  return accountMatchesSearch(entity) && accountMatchesFilter(entity);
}}

function featuredMatchesAccountState(entity) {{
  return accountMatchesAccountState(entity);
}}

function accountConditionSummaryText() {{
  const parts = [];
  const search = accountListState.search.trim();
  if (search) parts.push(`搜索“${{search}}”`);
  if (accountListState.sort !== "default") parts.push(`排序：${{ACCOUNT_SORT_OPTIONS[accountListState.sort]?.label || "默认排序"}}`);
  if (accountListState.filter !== "all") parts.push(`筛选：${{ACCOUNT_FILTERS[accountListState.filter]?.label || "全部账号"}}`);
  return parts.length ? `当前条件：${{parts.join(" · ")}}` : "当前条件：全部账号";
}}

function renderAccountToolbar() {{
  const search = document.getElementById("account-search-input");
  const sort = document.getElementById("account-sort-select");
  const clear = document.getElementById("account-clear-filters");
  if (search) {{
    search.value = accountListState.search;
    if (search.dataset.bound !== "1") {{
      search.addEventListener("input", () => {{
        accountListState.search = search.value;
        applyAccountListState();
      }});
      search.dataset.bound = "1";
    }}
  }}
  if (sort) {{
    sort.value = accountListState.sort;
    if (sort.dataset.bound !== "1") {{
      sort.addEventListener("change", () => {{
        accountListState.sort = sort.value || "default";
        applyAccountListState();
      }});
      sort.dataset.bound = "1";
    }}
  }}
  document.querySelectorAll("[data-account-filter]").forEach((button) => {{
    const active = (button.dataset.accountFilter || "all") === accountListState.filter;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
    if (button.dataset.bound !== "1") {{
      button.addEventListener("click", () => {{
        accountListState.filter = button.dataset.accountFilter || "all";
        applyAccountListState();
      }});
      button.dataset.bound = "1";
    }}
  }});
  if (clear && clear.dataset.bound !== "1") {{
    clear.addEventListener("click", () => {{
      accountListState.search = "";
      accountListState.sort = "default";
      accountListState.filter = "all";
      applyAccountListState();
    }});
    clear.dataset.bound = "1";
  }}
  const summary = document.getElementById("account-filter-summary");
  if (summary) summary.textContent = accountConditionSummaryText();
}}

function applyAccountListState() {{
  renderAccountToolbar();
  const accounts = accountListSource.filter(shouldShowAccount);
  const summary = accounts.find((entity) => entity.name === "线索组汇总") || null;
  const featured = accounts.find((entity) => entity.name === "快手-EXEED星途") || null;
  const accountOrder = new Map(accounts.map((entity, index) => [entity, index]));
  const businessAccounts = accounts
    .filter((entity) => entity !== summary && entity !== featured)
    .filter(accountMatchesAccountState);
  businessAccounts.sort((a, b) => compareAccountsByState(a, b, accountOrder));
  const featuredBlock = featured && featuredMatchesAccountState(featured) ? featuredAccountCard(featured) : "";
  const summaryBlocks = [
    featuredBlock,
    summary ? accountDetailCard(summary, "account-card account-summary-card") : "",
  ].filter(Boolean).join("");
  const listBlocks = businessAccounts.length
    ? businessAccounts.map((entity) => accountDetailCard(entity, "account-card")).join("")
    : featuredBlock
      ? ""
      : `<div class="account-empty-state"><strong>无匹配账号</strong><span>可尝试清除搜索词或筛选条件。</span></div>`;
  document.getElementById("trend-account-summary").innerHTML = summaryBlocks || `<div class="loading">未提供账号汇总</div>`;
  document.getElementById("trend-accounts").innerHTML = listBlocks;
  const accountRoot = document.getElementById("account-trends");
  bindAccountTrendSwitchers(accountRoot || document);
  bindChartInteractions(accountRoot || document);
  bindAccountDetailToggles(accountRoot || document);
}}

function renderAccounts(payload) {{
  accountListSource = payload.account_summary || [];
  applyAccountListState();
}}

const ANCHOR_SORT_OPTIONS = {{
  default: {{ label: "默认排序" }},
  leads: {{ label: "风车线索（去重）" }},
  deals: {{ label: "成交数" }},
  spend: {{ label: "费用" }},
  cpl: {{ label: "CPL" }},
  cps: {{ label: "CPS" }},
  target_rate: {{ label: "当前 / 目标" }},
}};

const ANCHOR_FILTERS = {{
  all: {{ label: "全部主播" }},
  has_target: {{ label: "有目标参考" }},
  target_missing: {{ label: "目标未提供" }},
  has_deals: {{ label: "有成交" }},
  has_spend: {{ label: "有费用" }},
  over_100: {{ label: "比率超过 100%" }},
}};

const anchorListState = {{ search: "", sort: "default", filter: "all" }};
let anchorListSource = [];
const expandedAnchorNames = new Set();

function anchorDisplayName(entity) {{
  return String(entity?.name || "未提供").trim();
}}

function anchorParentScope(entity) {{
  return String(entity?.parent_scope || "未提供").trim();
}}

function anchorMetricCell(label, item) {{
  return `
    <span>
      <small>${{escapeHtml(label)}}</small>
      <strong>${{escapeHtml(metricDisplayText(item))}}</strong>
      ${{metricStatusNote(item)}}
    </span>`;
}}

function anchorTargetSummary(metricItem) {{
  if (!hasValue(metricItem?.target) || !hasValue(metricItem?.attain_rate)) return "";
  return anchorMetricCell("当前 / 目标", {{ ...metricItem, actual: metricItem.attain_rate, unit: "比例" }});
}}

function anchorSummaryGrid(entity) {{
  const leads = metric(entity, "leads");
  const deals = metric(entity, "deals");
  const spend = metric(entity, "spend");
  const cpl = metric(entity, "cpl");
  const cps = metric(entity, "cps");
  const notApplicableVisits = [["到店率", "visit_rate"], ["到店成交率", "visit_deal_rate"]]
    .map(([label, key]) => {{
      const item = metric(entity, key);
      return item?.source_status === "not_applicable" ? anchorMetricCell(label, item) : "";
    }})
    .join("");
  return `
    <div class="anchor-summary-grid">
      ${{anchorMetricCell("风车线索（去重）", leads)}}
      ${{anchorMetricCell("成交数", deals)}}
      ${{anchorMetricCell("费用", spend)}}
      ${{anchorMetricCell("CPL", cpl)}}
      ${{anchorMetricCell("CPS", cps)}}
      ${{anchorTargetSummary(leads)}}
      ${{notApplicableVisits}}
    </div>`;
}}

function anchorMetricGroup(title, pairs, entity) {{
  const items = pairs.map(([label, key]) => anchorMetricCell(label, metric(entity, key))).join("");
  return `<div class="metric-group anchor-metric-group"><h4>${{escapeHtml(title)}}</h4><div>${{items}}</div></div>`;
}}

function anchorHasTrendValues(points) {{
  return (points || []).map(normalizePoint).some((point) => point.value !== null);
}}

function anchorTrendSwitcher(entity) {{
  const leads = metric(entity, "leads");
  const deals = metric(entity, "deals");
  const hasDealsTrend = anchorHasTrendValues(entity?.daily_trends?.deals || []);
  const leadsPayload = encodedTrendPayload("线索趋势", entity?.daily_trends?.leads || [], leads.unit || "条");
  const dealsPayload = hasDealsTrend ? encodedTrendPayload("成交趋势", entity?.daily_trends?.deals || [], deals.unit || "台") : "";
  const dealsButton = hasDealsTrend
    ? `<button type="button" data-anchor-trend-key="deals" aria-pressed="false">成交</button>`
    : "";
  const dealsData = hasDealsTrend ? ` data-trend-deals="${{dealsPayload}}"` : "";
  return `
    <div class="anchor-trend-switcher" data-anchor-trend data-active-trend="leads" data-trend-leads="${{leadsPayload}}"${{dealsData}}>
      <div class="anchor-trend-toolbar">
        <span>主播趋势</span>
        <div class="anchor-trend-buttons" role="group" aria-label="主播趋势指标">
          <button type="button" class="is-active" data-anchor-trend-key="leads" aria-pressed="true">线索</button>
          ${{dealsButton}}
        </div>
      </div>
      <div class="anchor-trend-pane is-active" data-anchor-trend-panel>
        ${{compactTrendChart("线索趋势", entity?.daily_trends?.leads || [], leads.unit || "条")}}
      </div>
    </div>`;
}}

function anchorTrendDetailNote(entity) {{
  const hasDealsTrend = anchorHasTrendValues(entity?.daily_trends?.deals || []);
  const note = hasDealsTrend ? "当前卡片可在线索趋势与成交趋势之间切换。" : "当前卡片保留线索趋势。";
  return `<div class="anchor-detail-trend-note"><h4>趋势</h4><p>${{escapeHtml(note)}}</p></div>`;
}}

function anchorDetailPanel(entity, expanded) {{
  const panelClass = expanded ? "anchor-detail-panel is-expanded" : "anchor-detail-panel";
  return `
    <div class="${{panelClass}}"${{expanded ? "" : " hidden"}} aria-hidden="${{expanded ? "false" : "true"}}">
      <div class="anchor-full-account" tabindex="0" title="${{escapeHtml(anchorParentScope(entity))}}">
        <small>所属账号</small>
        <strong>${{escapeHtml(anchorParentScope(entity))}}</strong>
      </div>
      ${{anchorMetricGroup("线索组", [["风车线索（去重）", "leads"]], entity)}}
      ${{anchorMetricGroup("抖音来客订单", [["抖音来客订单（去重）", "douyin_laike_orders"]], entity)}}
      ${{anchorMetricGroup("到店组", [["到店数", "visits"], ["到店率", "visit_rate"], ["到店成交率", "visit_deal_rate"]], entity)}}
      ${{anchorMetricGroup("成交组", [["成交数", "deals"], ["线索成交率", "lead_deal_rate"]], entity)}}
      ${{anchorMetricGroup("成本组", [["费用", "spend"], ["CPL", "cpl"], ["CPS", "cps"]], entity)}}
      ${{anchorTrendDetailNote(entity)}}
    </div>`;
}}

function anchorDetailCard(entity, className) {{
  const name = anchorDisplayName(entity);
  const parent = anchorParentScope(entity);
  const expanded = expandedAnchorNames.has(name);
  return `
    <article class="${{className}}" data-anchor-name="${{escapeHtml(name)}}">
      <div class="card-title-row">
        <div>
          <h3>${{escapeHtml(name)}}</h3>
          <p class="anchor-parent-scope" tabindex="0" title="${{escapeHtml(parent)}}">${{escapeHtml(parent)}}</p>
        </div>
        <button type="button" class="anchor-detail-toggle" data-anchor-detail-toggle aria-expanded="${{expanded ? "true" : "false"}}">${{expanded ? "收起详情" : "展开详情"}}</button>
      </div>
      ${{anchorSummaryGrid(entity)}}
      ${{anchorTrendSwitcher(entity)}}
      ${{anchorDetailPanel(entity, expanded)}}
    </article>`;
}}

function anchorMetricNumber(item) {{
  if (!item || item?.source_status === "not_connected") return null;
  if (item.actual === null || item.actual === undefined || Number.isNaN(Number(item.actual))) return null;
  return Number(item.actual);
}}

function anchorMetrics(entity) {{
  return Object.values(entity?.metrics || {{}});
}}

function anchorHasTarget(entity) {{
  return anchorMetrics(entity).some((item) => hasValue(item?.target));
}}

function anchorHasNotConnectedField(entity) {{
  return anchorMetrics(entity).some((item) => item?.source_status === "not_connected" || metricDisplayText(item) === "未提供");
}}

function anchorHasOver100Ratio(entity) {{
  return anchorMetrics(entity).some((item) => {{
    const actual = anchorMetricNumber(item);
    const unit = item?.unit || "";
    if (unit.includes("比例") && actual !== null && actual > 1) return true;
    return hasValue(item?.attain_rate) && Number(item.attain_rate) > 1;
  }});
}}

function anchorSortValue(entity, key) {{
  if (key === "target_rate") {{
    const rates = anchorMetrics(entity)
      .map((item) => hasValue(item?.attain_rate) ? Number(item.attain_rate) : null)
      .filter((value) => value !== null && Number.isFinite(value));
    return rates.length ? Math.max(...rates) : null;
  }}
  const metricKey = {{
    leads: "leads",
    deals: "deals",
    spend: "spend",
    cpl: "cpl",
    cps: "cps",
  }}[key] || "leads";
  return anchorMetricNumber(metric(entity, metricKey));
}}

function compareAnchorsByState(a, b, anchorOrder) {{
  if (anchorListState.sort === "default") return (anchorOrder.get(a) || 0) - (anchorOrder.get(b) || 0);
  const av = anchorSortValue(a, anchorListState.sort);
  const bv = anchorSortValue(b, anchorListState.sort);
  if (av === null && bv === null) return (anchorOrder.get(a) || 0) - (anchorOrder.get(b) || 0);
  if (av === null) return 1;
  if (bv === null) return -1;
  return (bv - av) || ((anchorOrder.get(a) || 0) - (anchorOrder.get(b) || 0));
}}

function anchorMatchesSearch(entity) {{
  const query = anchorListState.search.trim().toLowerCase();
  if (!query) return true;
  return anchorDisplayName(entity).toLowerCase().includes(query) || anchorParentScope(entity).toLowerCase().includes(query);
}}

function anchorMatchesFilter(entity, filterKey = anchorListState.filter) {{
  if (filterKey === "all") return true;
  if (filterKey === "has_target") return anchorHasTarget(entity);
  if (filterKey === "target_missing") return !anchorHasTarget(entity);
  if (filterKey === "has_deals") return (anchorMetricNumber(metric(entity, "deals")) || 0) > 0;
  if (filterKey === "has_spend") return (anchorMetricNumber(metric(entity, "spend")) || 0) !== 0;
  if (filterKey === "over_100") return anchorHasOver100Ratio(entity);
  return true;
}}

function anchorMatchesState(entity) {{
  return anchorMatchesSearch(entity) && anchorMatchesFilter(entity);
}}

function anchorConditionSummaryText() {{
  const parts = [];
  const search = anchorListState.search.trim();
  if (search) parts.push(`搜索“${{search}}”`);
  if (anchorListState.sort !== "default") parts.push(`排序：${{ANCHOR_SORT_OPTIONS[anchorListState.sort]?.label || "默认排序"}}`);
  if (anchorListState.filter !== "all") parts.push(`筛选：${{ANCHOR_FILTERS[anchorListState.filter]?.label || "全部主播"}}`);
  return parts.length ? `当前条件：${{parts.join(" · ")}}` : "当前条件：全部主播";
}}

function renderAnchorToolbar() {{
  const search = document.getElementById("anchor-search-input");
  const sort = document.getElementById("anchor-sort-select");
  const clear = document.getElementById("anchor-clear-filters");
  if (search) {{
    search.value = anchorListState.search;
    if (search.dataset.bound !== "1") {{
      search.addEventListener("input", () => {{
        anchorListState.search = search.value;
        applyAnchorListState();
      }});
      search.dataset.bound = "1";
    }}
  }}
  if (sort) {{
    sort.value = anchorListState.sort;
    if (sort.dataset.bound !== "1") {{
      sort.addEventListener("change", () => {{
        anchorListState.sort = sort.value || "default";
        applyAnchorListState();
      }});
      sort.dataset.bound = "1";
    }}
  }}
  document.querySelectorAll("[data-anchor-filter]").forEach((button) => {{
    const active = (button.dataset.anchorFilter || "all") === anchorListState.filter;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
    if (button.dataset.bound !== "1") {{
      button.addEventListener("click", () => {{
        anchorListState.filter = button.dataset.anchorFilter || "all";
        applyAnchorListState();
      }});
      button.dataset.bound = "1";
    }}
  }});
  if (clear && clear.dataset.bound !== "1") {{
    clear.addEventListener("click", () => {{
      anchorListState.search = "";
      anchorListState.sort = "default";
      anchorListState.filter = "all";
      applyAnchorListState();
    }});
    clear.dataset.bound = "1";
  }}
  const summary = document.getElementById("anchor-filter-summary");
  if (summary) summary.textContent = anchorConditionSummaryText();
}}

function applyAnchorListState() {{
  renderAnchorToolbar();
  const anchors = anchorListSource || [];
  const anchorOrder = new Map(anchors.map((entity, index) => [entity, index]));
  const visibleAnchors = anchors.filter(anchorMatchesState);
  visibleAnchors.sort((a, b) => compareAnchorsByState(a, b, anchorOrder));
  document.getElementById("trend-anchors").innerHTML = visibleAnchors.length
    ? visibleAnchors.map((entity) => anchorDetailCard(entity, "anchor-card")).join("")
    : `<div class="anchor-empty-state"><strong>无匹配主播</strong><span>可尝试清除搜索词或筛选条件。</span></div>`;
  const anchorRoot = document.getElementById("anchor-trends");
  bindAnchorTrendSwitchers(anchorRoot || document);
  bindChartInteractions(anchorRoot || document);
  bindAnchorDetailToggles(anchorRoot || document);
}}

function renderAnchors(payload) {{
  anchorListSource = payload.anchor_summary || [];
  applyAnchorListState();
}}

const SEED_SORT_OPTIONS = {{
  default: {{ label: "默认排序" }},
  impressions: {{ label: "曝光" }},
  target: {{ label: "目标参考" }},
  target_rate: {{ label: "当前 / 目标" }},
  latest: {{ label: "范围日曝光合计" }},
  name: {{ label: "名称" }},
}};

const SEED_FILTERS = {{
  all: {{ label: "全部种草" }},
  account_total: {{ label: "账号总曝光" }},
  anchor_exposure: {{ label: "主播曝光" }},
  has_target: {{ label: "有目标参考" }},
  target_missing: {{ label: "目标未提供" }},
  positive_exposure: {{ label: "曝光大于 0" }},
  over_100: {{ label: "当前 / 目标超过 100%" }},
}};

const seedListState = {{ search: "", sort: "default", filter: "all" }};
let seedAccountSource = [];
let seedAnchorSource = [];
const expandedSeedKeys = new Set();

function seedDisplayName(entity) {{
  return String(entity?.name || "未提供").trim();
}}

function seedParentScope(entity) {{
  return String(entity?.parent_scope || "").trim();
}}

function seedDisplayType(entity) {{
  if (entity?.display_type) return String(entity.display_type).trim();
  const rawType = String(entity?.type || "");
  if (rawType === "account") return "账号总曝光";
  if (rawType === "anchor" || rawType === "host") return "主播曝光";
  return "种草曝光";
}}

function seedScopeText(entity) {{
  return seedParentScope(entity) || seedDisplayType(entity);
}}

function seedIsAccountTotal(entity) {{
  return seedDisplayType(entity) === "账号总曝光" || String(entity?.type || "") === "account";
}}

function seedCardKey(entity) {{
  return [seedDisplayType(entity), seedDisplayName(entity), seedParentScope(entity)].join("::");
}}

function seedImpressionsMetric(entity) {{
  return entity?.metrics?.impressions || {{ key: "impressions", label: "曝光", actual: null, target: null, attain_rate: null, unit: "人次" }};
}}

function seedLatestMetric(entity) {{
  const metrics = entity?.metrics || {{}};
  const direct = metrics.latest_impressions || metrics.daily_impressions || metrics.latest_exposure;
  if (direct) return {{ ...direct, label: "范围日曝光合计" }};
  const impressions = seedImpressionsMetric(entity);
  return {{ ...impressions, label: "范围日曝光合计" }};
}}

function seedLatestExposureValue(entity) {{
  return seedMetricNumber(seedLatestMetric(entity)) ?? seedMetricNumber(seedImpressionsMetric(entity));
}}

function seedMetricNumber(item) {{
  if (!item || item?.source_status === "not_connected") return null;
  if (item.actual === null || item.actual === undefined || Number.isNaN(Number(item.actual))) return null;
  return Number(item.actual);
}}

function seedMetrics(entity) {{
  return Object.values(entity?.metrics || {{}});
}}

function seedHasTarget(entity) {{
  return hasValue(seedImpressionsMetric(entity)?.target);
}}

function seedHasNotConnectedField(entity) {{
  return seedMetrics(entity).some((item) => item?.source_status === "not_connected" || metricDisplayText(item) === "未提供");
}}

function seedHasOver100Ratio(entity) {{
  const impressions = seedImpressionsMetric(entity);
  return hasValue(impressions?.attain_rate) && Number(impressions.attain_rate) > 1;
}}

function seedMissingTargetMetric(metricItem) {{
  return {{ ...metricItem, actual: null, target: null, attain_rate: null }};
}}

function seedMetricText(item) {{
  if (item?.source_status === "not_connected") return "未提供";
  if (typeof item?.actual === "string" && item.actual.trim() && Number.isNaN(Number(item.actual))) return item.actual;
  return metricDisplayText(item);
}}

function seedMetricCell(label, item) {{
  return `
    <span>
      <small>${{escapeHtml(label)}}</small>
      <strong>${{escapeHtml(seedMetricText(item))}}</strong>
    </span>`;
}}

function seedTargetSummary(metricItem) {{
  if (!hasValue(metricItem?.target)) return seedMetricCell("目标参考", seedMissingTargetMetric(metricItem));
  const targetCell = seedMetricCell("目标参考", {{ ...metricItem, actual: metricItem.target }});
  if (!hasValue(metricItem?.attain_rate)) return targetCell;
  return targetCell + seedMetricCell("当前 / 目标", {{ ...metricItem, actual: metricItem.attain_rate, unit: "比例" }});
}}

function seedSummaryGrid(entity) {{
  const impressions = seedImpressionsMetric(entity);
  return `
    <div class="seed-summary-grid">
      ${{seedMetricCell("类型", {{ label: "类型", actual: seedDisplayType(entity), unit: "" }})}}
      ${{seedMetricCell("曝光", impressions)}}
      ${{seedTargetSummary(impressions)}}
    </div>`;
}}

function seedMetricGroup(title, items) {{
  return `<div class="metric-group seed-metric-group"><h4>${{escapeHtml(title)}}</h4><div>${{items.join("")}}</div></div>`;
}}

function seedFieldStateText(entity) {{
  if (seedHasNotConnectedField(entity)) return "未提供";
  if (!seedHasTarget(entity)) return "未提供";
  return "";
}}

function seedSourceGroup(entity) {{
  const items = [
    seedMetricCell("类型", {{ label: "类型", actual: seedDisplayType(entity), unit: "" }}),
  ];
  if (seedParentScope(entity)) items.push(seedMetricCell("所属账号", {{ label: "所属账号", actual: seedParentScope(entity), unit: "" }}));
  const fieldState = seedFieldStateText(entity);
  if (fieldState) items.push(seedMetricCell("字段状态", {{ label: "字段状态", actual: fieldState, unit: "" }}));
  return seedMetricGroup("来源组", items);
}}

function seedTrendBlock(entity, metricItem) {{
  return `<div class="seed-trend-block" data-seed-trend data-seed-trend-panel>${{compactTrendChart("曝光趋势", entity?.daily_trends?.impressions || [], metricItem.unit || "人次")}}</div>`;
}}

function seedDetailPanel(entity, expanded) {{
  const impressions = seedImpressionsMetric(entity);
  const latest = seedLatestMetric(entity);
  const panelClass = expanded ? "seed-detail-panel is-expanded" : "seed-detail-panel";
  return `
    <div class="${{panelClass}}"${{expanded ? "" : " hidden"}} aria-hidden="${{expanded ? "false" : "true"}}">
      ${{seedMetricGroup("曝光组", [
        seedMetricCell("曝光", impressions),
        seedMetricCell("范围日曝光合计", latest),
      ])}}
      ${{seedMetricGroup("目标组", [
        seedMetricCell("目标参考", hasValue(impressions?.target) ? {{ ...impressions, actual: impressions.target }} : seedMissingTargetMetric(impressions)),
        hasValue(impressions?.target) && hasValue(impressions?.attain_rate) ? seedMetricCell("当前 / 目标", {{ ...impressions, actual: impressions.attain_rate, unit: "比例" }}) : "",
      ].filter(Boolean))}}
      ${{seedSourceGroup(entity)}}
      <div class="metric-group seed-metric-group seed-trend-group"><h4>趋势组</h4>${{seedTrendBlock(entity, impressions)}}</div>
    </div>`;
}}

function seedCard(entity, className) {{
  const metricItem = seedImpressionsMetric(entity);
  const typeLabel = seedDisplayType(entity);
  const name = seedDisplayName(entity);
  const parent = seedParentScope(entity);
  const expanded = expandedSeedKeys.has(seedCardKey(entity));
  return `
    <article class="${{className}}" data-seed-key="${{escapeHtml(seedCardKey(entity))}}">
      <div class="card-title-row">
        <div>
          <h3>${{escapeHtml(name)}}</h3>
          ${{parent ? `<p class="seed-parent-scope" tabindex="0" title="${{escapeHtml(parent)}}">${{escapeHtml(parent)}}</p>` : ""}}
          <span class="seed-type-chip">类型：${{escapeHtml(typeLabel)}}</span>
        </div>
        <button type="button" class="seed-detail-toggle" data-seed-detail-toggle aria-expanded="${{expanded ? "true" : "false"}}">${{expanded ? "收起详情" : "展开详情"}}</button>
      </div>
      ${{seedSummaryGrid(entity)}}
      ${{progressBar(metricItem)}}
      ${{seedTrendBlock(entity, metricItem)}}
      ${{seedDetailPanel(entity, expanded)}}
    </article>`;
}}

function seedSortValue(entity, key) {{
  if (key === "name") return seedDisplayName(entity);
  if (key === "target") return hasValue(seedImpressionsMetric(entity)?.target) ? Number(seedImpressionsMetric(entity).target) : null;
  if (key === "target_rate") return hasValue(seedImpressionsMetric(entity)?.attain_rate) ? Number(seedImpressionsMetric(entity).attain_rate) : null;
  if (key === "latest") return seedLatestExposureValue(entity);
  return seedMetricNumber(seedImpressionsMetric(entity));
}}

function compareSeedsByState(a, b, seedOrder) {{
  if (seedListState.sort === "default") return (seedOrder.get(a) || 0) - (seedOrder.get(b) || 0);
  if (seedListState.sort === "name") {{
    return seedDisplayName(a).localeCompare(seedDisplayName(b), "zh-Hans-CN") || ((seedOrder.get(a) || 0) - (seedOrder.get(b) || 0));
  }}
  const av = seedSortValue(a, seedListState.sort);
  const bv = seedSortValue(b, seedListState.sort);
  if (av === null && bv === null) return (seedOrder.get(a) || 0) - (seedOrder.get(b) || 0);
  if (av === null) return 1;
  if (bv === null) return -1;
  return (bv - av) || ((seedOrder.get(a) || 0) - (seedOrder.get(b) || 0));
}}

function seedMatchesSearch(entity) {{
  const query = seedListState.search.trim().toLowerCase();
  if (!query) return true;
  return seedDisplayName(entity).toLowerCase().includes(query) || seedParentScope(entity).toLowerCase().includes(query);
}}

function seedMatchesFilter(entity, filterKey = seedListState.filter) {{
  if (filterKey === "all") return true;
  if (filterKey === "account_total") return seedIsAccountTotal(entity);
  if (filterKey === "anchor_exposure") return !seedIsAccountTotal(entity);
  if (filterKey === "has_target") return seedHasTarget(entity);
  if (filterKey === "target_missing") return !seedHasTarget(entity);
  if (filterKey === "positive_exposure") return (seedMetricNumber(seedImpressionsMetric(entity)) || 0) > 0;
  if (filterKey === "over_100") return seedHasOver100Ratio(entity);
  return true;
}}

function seedMatchesState(entity) {{
  return seedMatchesSearch(entity) && seedMatchesFilter(entity);
}}

function seedConditionSummaryText() {{
  const parts = [];
  const search = seedListState.search.trim();
  if (search) parts.push(`搜索“${{search}}”`);
  if (seedListState.sort !== "default") parts.push(`排序：${{SEED_SORT_OPTIONS[seedListState.sort]?.label || "默认排序"}}`);
  if (seedListState.filter !== "all") parts.push(`筛选：${{SEED_FILTERS[seedListState.filter]?.label || "全部种草"}}`);
  return parts.length ? `当前条件：${{parts.join(" · ")}}` : "当前条件：全部种草";
}}

function renderSeedToolbar() {{
  const search = document.getElementById("seed-search-input");
  const sort = document.getElementById("seed-sort-select");
  const clear = document.getElementById("seed-clear-filters");
  if (search) {{
    search.value = seedListState.search;
    if (search.dataset.bound !== "1") {{
      search.addEventListener("input", () => {{
        seedListState.search = search.value;
        applySeedListState();
      }});
      search.dataset.bound = "1";
    }}
  }}
  if (sort) {{
    sort.value = seedListState.sort;
    if (sort.dataset.bound !== "1") {{
      sort.addEventListener("change", () => {{
        seedListState.sort = sort.value || "default";
        applySeedListState();
      }});
      sort.dataset.bound = "1";
    }}
  }}
  document.querySelectorAll("[data-seed-filter]").forEach((button) => {{
    const active = (button.dataset.seedFilter || "all") === seedListState.filter;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
    if (button.dataset.bound !== "1") {{
      button.addEventListener("click", () => {{
        seedListState.filter = button.dataset.seedFilter || "all";
        applySeedListState();
      }});
      button.dataset.bound = "1";
    }}
  }});
  if (clear && clear.dataset.bound !== "1") {{
    clear.addEventListener("click", () => {{
      seedListState.search = "";
      seedListState.sort = "default";
      seedListState.filter = "all";
      applySeedListState();
    }});
    clear.dataset.bound = "1";
  }}
  const summary = document.getElementById("seed-filter-summary");
  if (summary) summary.textContent = seedConditionSummaryText();
}}

function applySeedListState() {{
  renderSeedToolbar();
  const accounts = seedAccountSource || [];
  const anchors = seedAnchorSource || [];
  const seedOrder = new Map([...accounts, ...anchors].map((entity, index) => [entity, index]));
  const visibleAccounts = accounts.filter(seedMatchesState);
  const visibleAnchors = anchors.filter(seedMatchesState);
  visibleAccounts.sort((a, b) => compareSeedsByState(a, b, seedOrder));
  visibleAnchors.sort((a, b) => compareSeedsByState(a, b, seedOrder));
  const accountBlock = visibleAccounts.length
    ? `<div class="seed-account-slot">${{visibleAccounts.map((entity) => seedCard(entity, "seed-card seed-account-card")).join("")}}</div>`
    : "";
  const anchorBlock = visibleAnchors.length
    ? `<div class="business-card-list seed-list">${{visibleAnchors.map((entity) => seedCard(entity, "seed-card")).join("")}}</div>`
    : "";
  document.getElementById("trend-seed").innerHTML = accountBlock || anchorBlock
    ? `${{accountBlock}}${{anchorBlock}}`
    : `<div class="seed-empty-state"><strong>无匹配种草项</strong><span>可尝试清除搜索词或筛选条件。</span></div>`;
  const seedRoot = document.getElementById("seed-trends");
  bindChartInteractions(seedRoot || document);
  bindSeedDetailToggles(seedRoot || document);
}}

function renderSeed(payload) {{
  const exposure = payload.seed_exposure_summary || {{}};
  seedAccountSource = exposure.accounts || [];
  seedAnchorSource = exposure.anchors || [];
  applySeedListState();
}}

function monthEndDate(monthText) {{
  const [year, month] = String(monthText || "").split("-").map(Number);
  if (!year || !month) return "";
  const day = new Date(year, month, 0).getDate();
  return `${{year}}-${{String(month).padStart(2, "0")}}-${{String(day).padStart(2, "0")}}`;
}}

function maxDateText(left, right) {{
  if (!left) return right || "";
  if (!right) return left || "";
  return left > right ? left : right;
}}

function minDateText(left, right) {{
  if (!left) return right || "";
  if (!right) return left || "";
  return left < right ? left : right;
}}

function monthCoverageRange(row, payload) {{
  const month = String(row?.month || "");
  const monthStart = month ? `${{month}}-01` : "";
  const monthEnd = monthEndDate(month);
  const range = payload?.date_range || {{}};
  const rangeStart = range.start_date || range.start || monthStart;
  const rangeEnd = range.end_date || range.end || monthEnd;
  const start = maxDateText(monthStart, rangeStart);
  const end = minDateText(monthEnd, rangeEnd);
  if (!start || !end || start > end) return {{ start: "", end: "", label: "未提供" }};
  return {{ start, end, label: `${{start}} 至 ${{end}}` }};
}}

function monthCoverageLabel(row, payload) {{
  return monthCoverageRange(row, payload).label;
}}

const MONTHLY_COVERAGE_EXAMPLES = [
  "2026年3月",
  "2026年4月",
  "2026年5月",
  "2026-03-01 至 2026-03-31",
  "2026-04-01 至 2026-04-30",
  "2026-05-01 至 2026-05-22",
];

function monthlyCellTooltip(row, metric, coverage) {{
  const month = row?.label || row?.month || "未提供";
  const label = metric?.label || metric?.key || "未提供";
  const value = fmtMetricValue(metric?.value, metric?.unit || "");
  return [
    `月份：${{month}}`,
    `指标：${{label}}`,
    `本期值：${{value}}`,
    `覆盖范围：${{coverage || "未提供"}}`,
  ].join("；");
}}

function monthlyComparisonPanel(payload) {{
  const rows = payload.monthly_comparison || [];
  if (!rows.length) return "";
  const metricKeys = ["impressions", "leads", "douyin_laike_orders", "deals", "spend", "cpl", "cps"];
  const maxByMetric = Object.fromEntries(metricKeys.map((key) => [
    key,
    Math.max(...rows.map((row) => Number(row.metrics?.[key]?.value ?? 0)).filter((value) => Number.isFinite(value)), 0),
  ]));
  const monthHeaders = rows.map((row) => {{
    const coverage = monthCoverageLabel(row, payload);
    return `
      <div class="monthly-month-coverage" role="columnheader">
        <strong>${{escapeHtml(row.label || row.month || "未提供")}}</strong>
        <small>${{escapeHtml(coverage)}}</small>
      </div>`;
  }}).join("");
  const matrixRows = metricKeys.map((key) => {{
    const label = rows[0]?.metrics?.[key]?.label || key;
    const maxValue = maxByMetric[key] || 0;
    const isCost = key === "cpl" || key === "cps";
    const cells = rows.map((row) => {{
      const metric = row.metrics?.[key] || {{}};
      const value = Number(metric.value);
      const hasMetricValue = hasValue(metric.value) && Number.isFinite(value);
      const width = hasMetricValue && maxValue > 0 ? Math.max(0, Math.min((value / maxValue) * 100, 100)) : 0;
      const coverage = monthCoverageLabel(row, payload);
      const tooltip = monthlyCellTooltip(row, metric, coverage);
      return `
        <div class="monthly-cell${{isCost ? " monthly-cell-cost" : ""}}" role="cell" tabindex="0" aria-label="${{escapeHtml(tooltip)}}">
          <strong>${{escapeHtml(fmtMetricValue(metric.value, metric.unit || ""))}}</strong>
          <span class="monthly-bar${{isCost ? " monthly-bar-muted" : ""}}" aria-hidden="true"><i style="width:${{width.toFixed(2)}}%"></i></span>
          <span class="monthly-cell-help" role="tooltip">${{escapeHtml(tooltip)}}</span>
        </div>`;
    }}).join("");
    return `
      <div class="monthly-row" role="row">
        <div class="monthly-metric" role="rowheader">${{escapeHtml(label)}}</div>
        ${{cells}}
      </div>`;
  }}).join("");
  return `
    <div class="monthly-comparison">
      <div class="section-subhead">
        <h3>月度对比</h3>
        <p>按当前查看范围内的自然月切片横向比较；月份下方展示覆盖范围。</p>
      </div>
      <div class="monthly-matrix-scroll">
        <div class="monthly-matrix" role="table" aria-label="月度对比矩阵" style="--monthly-cols:${{rows.length}}">
          <div class="monthly-row monthly-header-row" role="row">
            <div class="monthly-metric" role="columnheader">指标</div>
            ${{monthHeaders}}
          </div>
          ${{matrixRows}}
        </div>
      </div>
    </div>`;
}}

function tooltipRows(target, chart) {{
  const unit = chart.dataset.unit || "";
  const label = chart.dataset.metricLabel || "指标";
  const currentValue = target.dataset.value === "" ? null : Number(target.dataset.value);
  const previousValue = target.dataset.previousValue === "" ? null : Number(target.dataset.previousValue);
  const hasPrevious = target.dataset.previousDate !== "";
  const hasComparison = hasPrevious && currentValue !== null && previousValue !== null;
  const diff = hasComparison ? currentValue - previousValue : null;
  const rate = hasComparison && previousValue !== 0 ? diff / previousValue : null;
  const rows = [
    `<strong>日期：${{escapeHtml(target.dataset.date || "未提供")}}</strong>`,
    `<span>指标：${{escapeHtml(label)}}</span>`,
    `<span>本期值：${{escapeHtml(fmtMetricValue(currentValue, unit))}}</span>`,
  ];
  if (hasPrevious) {{
    rows.push(`<span>上一周期值：${{escapeHtml(fmtMetricValue(previousValue, unit))}}</span>`);
    rows.push(`<span>差值：${{escapeHtml(diff === null ? "未提供" : fmtMetricValue(diff, unit))}}</span>`);
    rows.push(`<span>变化率：${{escapeHtml(rate === null ? "未提供" : fmtPct(rate))}}</span>`);
  }}
  if (currentValue === null) rows.push("<span>当前日期没有可用值</span>");
  return rows.join("");
}}

function positionTooltip(event, target, chart, tooltip) {{
  const width = tooltip.offsetWidth || 220;
  const height = tooltip.offsetHeight || 96;
  const baseX = Number.isFinite(event?.offsetX) ? event.offsetX : Number(target.dataset.x || 0);
  const baseY = Number.isFinite(event?.offsetY) ? event.offsetY : 24;
  const maxLeft = Math.max(12, chart.clientWidth - width - 12);
  const maxTop = Math.max(12, chart.clientHeight - height - 12);
  const left = Math.min(Math.max(baseX + 14, 12), maxLeft);
  const top = Math.min(Math.max(baseY + 12, 12), maxTop);
  tooltip.style.left = `${{left}}px`;
  tooltip.style.top = `${{top}}px`;
}}

function bindChartInteractions(root = document) {{
  root.querySelectorAll(".trend-chart").forEach((chart) => {{
    if (chart.dataset.bound === "1") return;
    chart.dataset.bound = "1";
    const tooltip = chart.querySelector(".chart-tooltip");
    const hoverLine = chart.querySelector(".chart-hover-line");
    const points = chart.querySelectorAll(".chart-point");
    const clear = () => {{
      if (tooltip) tooltip.classList.remove("is-visible");
      if (hoverLine) hoverLine.classList.remove("is-visible");
      points.forEach((point) => point.classList.remove("is-active"));
    }};
    chart.querySelectorAll(".chart-hover-target").forEach((target) => {{
      const show = (event) => {{
        if (hoverLine) {{
          hoverLine.setAttribute("x1", target.dataset.x || "0");
          hoverLine.setAttribute("x2", target.dataset.x || "0");
          hoverLine.classList.add("is-visible");
        }}
        points.forEach((point) => point.classList.toggle("is-active", point.dataset.index === target.dataset.index));
        if (tooltip) {{
          tooltip.innerHTML = tooltipRows(target, chart);
          tooltip.classList.add("is-visible");
          positionTooltip(event, target, chart, tooltip);
        }}
      }};
      target.addEventListener("mouseenter", show);
      target.addEventListener("mousemove", show);
      target.addEventListener("focus", show);
    }});
    chart.addEventListener("mouseleave", clear);
    chart.addEventListener("focusout", clear);
  }});
}}

function bindAccountTrendSwitchers(root = document) {{
  root.querySelectorAll("[data-account-trend]").forEach((switcher) => {{
    if (switcher.dataset.bound === "1") return;
    switcher.dataset.bound = "1";
    const buttons = switcher.querySelectorAll("[data-account-trend-key]");
    const panel = switcher.querySelector("[data-account-trend-panel]");
    const trendData = (key) => {{
      try {{
        return JSON.parse(switcher.getAttribute(`data-trend-${{key}}`) || "{{}}");
      }} catch (error) {{
        return {{}};
      }}
    }};
    function renderAccountTrendPane(key) {{
      if (!panel) return;
      const data = trendData(key);
      panel.innerHTML = compactTrendChart(data.label || "线索趋势", data.points || [], data.unit || "");
      switcher.dataset.activeTrend = key;
      bindChartInteractions(panel);
    }}
    buttons.forEach((button) => {{
      button.addEventListener("click", () => {{
        const key = button.dataset.accountTrendKey || "";
        if (switcher.dataset.activeTrend !== key) renderAccountTrendPane(key);
        buttons.forEach((peer) => {{
          const active = peer === button;
          peer.classList.toggle("is-active", active);
          peer.setAttribute("aria-pressed", active ? "true" : "false");
        }});
      }});
    }});
  }});
}}

function bindAccountDetailToggles(root = document) {{
  root.querySelectorAll("[data-account-detail-toggle]").forEach((button) => {{
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", () => {{
      const card = button.closest(".account-card");
      const panel = card?.querySelector(".account-detail-panel");
      const name = card?.dataset.accountName || "";
      const expanded = button.getAttribute("aria-expanded") !== "true";
      button.setAttribute("aria-expanded", expanded ? "true" : "false");
      button.textContent = expanded ? "收起详情" : "展开详情";
      if (panel) {{
        panel.setAttribute("aria-hidden", expanded ? "false" : "true");
        if (expanded) {{
          panel.hidden = false;
          window.requestAnimationFrame(() => panel.classList.add("is-expanded"));
        }} else {{
          panel.classList.remove("is-expanded");
          window.setTimeout(() => {{
            if (button.getAttribute("aria-expanded") !== "true") panel.hidden = true;
          }}, 240);
        }}
      }}
      if (name) {{
        if (expanded) expandedAccountNames.add(name);
        else expandedAccountNames.delete(name);
      }}
    }});
  }});
}}

function bindAnchorTrendSwitchers(root = document) {{
  root.querySelectorAll("[data-anchor-trend]").forEach((switcher) => {{
    if (switcher.dataset.bound === "1") return;
    switcher.dataset.bound = "1";
    const buttons = switcher.querySelectorAll("[data-anchor-trend-key]");
    const panel = switcher.querySelector("[data-anchor-trend-panel]");
    const trendData = (key) => {{
      try {{
        return JSON.parse(switcher.getAttribute(`data-trend-${{key}}`) || "{{}}");
      }} catch (error) {{
        return {{}};
      }}
    }};
    function renderAnchorTrendPane(key) {{
      if (!panel) return;
      const data = trendData(key);
      panel.innerHTML = compactTrendChart(data.label || "线索趋势", data.points || [], data.unit || "");
      switcher.dataset.activeTrend = key;
      bindChartInteractions(panel);
    }}
    buttons.forEach((button) => {{
      button.addEventListener("click", () => {{
        const key = button.dataset.anchorTrendKey || "";
        if (switcher.dataset.activeTrend !== key) renderAnchorTrendPane(key);
        buttons.forEach((peer) => {{
          const active = peer === button;
          peer.classList.toggle("is-active", active);
          peer.setAttribute("aria-pressed", active ? "true" : "false");
        }});
      }});
    }});
  }});
}}

function bindAnchorDetailToggles(root = document) {{
  root.querySelectorAll("[data-anchor-detail-toggle]").forEach((button) => {{
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", () => {{
      const card = button.closest(".anchor-card");
      const panel = card?.querySelector(".anchor-detail-panel");
      const name = card?.dataset.anchorName || "";
      const expanded = button.getAttribute("aria-expanded") !== "true";
      button.setAttribute("aria-expanded", expanded ? "true" : "false");
      button.textContent = expanded ? "收起详情" : "展开详情";
      if (panel) {{
        panel.setAttribute("aria-hidden", expanded ? "false" : "true");
        if (expanded) {{
          panel.hidden = false;
          window.requestAnimationFrame(() => panel.classList.add("is-expanded"));
        }} else {{
          panel.classList.remove("is-expanded");
          window.setTimeout(() => {{
            if (button.getAttribute("aria-expanded") !== "true") panel.hidden = true;
          }}, 240);
        }}
      }}
      if (name) {{
        if (expanded) expandedAnchorNames.add(name);
        else expandedAnchorNames.delete(name);
      }}
    }});
  }});
}}

function bindSeedDetailToggles(root = document) {{
  root.querySelectorAll("[data-seed-detail-toggle]").forEach((button) => {{
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", () => {{
      const card = button.closest(".seed-card");
      const panel = card?.querySelector(".seed-detail-panel");
      const key = card?.dataset.seedKey || "";
      const expanded = button.getAttribute("aria-expanded") !== "true";
      button.setAttribute("aria-expanded", expanded ? "true" : "false");
      button.textContent = expanded ? "收起详情" : "展开详情";
      if (panel) {{
        panel.setAttribute("aria-hidden", expanded ? "false" : "true");
        if (expanded) {{
          panel.hidden = false;
          window.requestAnimationFrame(() => panel.classList.add("is-expanded"));
        }} else {{
          panel.classList.remove("is-expanded");
          window.setTimeout(() => {{
            if (button.getAttribute("aria-expanded") !== "true") panel.hidden = true;
          }}, 240);
        }}
      }}
      if (key) {{
        if (expanded) expandedSeedKeys.add(key);
        else expandedSeedKeys.delete(key);
      }}
    }});
  }});
}}

function updateDateInputs(range) {{
  if (range?.start_date || range?.start) document.getElementById("trend-start-date").value = range.start_date || range.start;
  if (range?.end_date || range?.end) document.getElementById("trend-end-date").value = range.end_date || range.end;
}}

function rangeModeLabel(mode) {{
  return {{
    "last-7": "近7天",
    "last-15": "近15天",
    "last-30": "近30天",
    "this-month": "本月",
    "last-month": "上月",
    "this-quarter": "本季度",
    "last-quarter": "上季度",
    "last-3-months": "近三个月",
    "custom": "自定义范围",
  }}[mode] || "自定义范围";
}}

function updateRangeSummary(startDate, endDate) {{
  const rangeNode = document.getElementById("trend-active-range");
  const daysNode = document.getElementById("trend-range-days");
  const stateNode = document.getElementById("trend-range-state");
  const days = rangeDays(startDate, endDate);
  if (rangeNode) rangeNode.textContent = startDate && endDate ? `当前范围：${{startDate}} 至 ${{endDate}}` : "当前范围：等待日期";
  if (daysNode) daysNode.textContent = days ? `查看天数：${{days}} / 92` : "查看天数：等待日期";
  if (stateNode) {{
    stateNode.textContent = rangeModeLabel(currentRangeMode);
    stateNode.dataset.rangeState = currentRangeMode === "custom" ? "custom" : "shortcut";
  }}
}}

function setActiveShortcut(mode) {{
  currentRangeMode = mode || "custom";
  document.querySelectorAll("[data-range-shortcut]").forEach((button) => {{
    const active = button.getAttribute("data-range-shortcut") === mode && mode !== "custom";
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  }});
}}

function renderTrendDashboard(payload) {{
  const range = payload.date_range || {{}};
  latestAvailableDate = range.latest_available_date || payload.latest_available_date || (range.all_available_dates || payload.all_available_dates || []).slice(-1)[0] || latestAvailableDate;
  updateDateInputs(range);
  const start = range.start_date || range.start || "未提供";
  const end = range.end_date || range.end || "未提供";
  updateRangeSummary(start, end);

  const byKey = Object.fromEntries((payload.core_kpi_summary || []).map((item) => [item.key, item]));
  let coreSummary = CORE_KPI_KEYS.map((key) => byKey[key]).filter(Boolean);
  coreSummary = coreSummary.slice(0, 7);
  document.getElementById("trend-core-cards").innerHTML = coreSummary.length
    ? coreSummary.map((item) => trendCard(item)).join("")
    : `<div class="loading">未提供核心经营表现</div>`;
  const previousByKey = seriesMap(payload.previous_period_trends || []);
  document.getElementById("trend-history").innerHTML = (payload.daily_trends || []).length
    ? `<div class="history-chart-grid">${{payload.daily_trends.map((series) => historyPanel(series, previousByKey)).join("")}}</div>`
    : `<div class="loading">未提供历史趋势</div>`;
  document.getElementById("trend-monthly-comparison").innerHTML = monthlyComparisonPanel(payload);

  renderAccounts(payload);
  renderAnchors(payload);
  renderSeed(payload);
  bindAccountTrendSwitchers();
  bindAnchorTrendSwitchers();
  bindChartInteractions();
  bindAnchorDetailToggles();
  bindSeedDetailToggles();
}}

function isTrendDataPath(path) {{
  try {{
    const url = new URL(path, window.location.origin);
    return url.pathname === "/dashboard/daily/trends";
  }} catch (error) {{
    return path === "/dashboard/daily/trends";
  }}
}}

async function fetchTrend(path) {{
  if (!isTrendDataPath(path)) throw new Error("只能读取经营趋势数据");
  return fetch(path, {{ method: "GET" }});
}}

function trendPath(startDate, endDate) {{
  const url = new URL(DATA_URL, window.location.origin);
  if (startDate) url.searchParams.set("start_date", startDate);
  if (endDate) url.searchParams.set("end_date", endDate);
  return `${{url.pathname}}${{url.search}}`;
}}

function rangeDays(startDate, endDate) {{
  if (!startDate || !endDate) return 0;
  const start = new Date(`${{startDate}}T00:00:00`);
  const end = new Date(`${{endDate}}T00:00:00`);
  return Math.floor((end - start) / 86400000) + 1;
}}

function setMessage(text) {{
  document.getElementById("trend-range-message").textContent = text || "";
}}

async function loadTrend(path = DATA_URL) {{
  try {{
    const response = await fetchTrend(path);
    if (!response.ok) {{
      let message = `读取失败 ${{response.status}}`;
      try {{
        const errorPayload = await response.json();
        message = errorPayload?.error?.message || message;
      }} catch (parseError) {{}}
      throw new Error(message);
    }}
    const payload = await response.json();
    setMessage("");
    renderTrendDashboard(payload);
  }} catch (error) {{
    setMessage(error.message);
    document.querySelectorAll(".loading").forEach((node) => {{
      node.textContent = `经营数据读取失败：${{error.message}}`;
    }});
  }}
}}

function padDate(value) {{
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${{year}}-${{month}}-${{day}}`;
}}

function shiftDays(base, days) {{
  const out = new Date(base.getTime());
  out.setDate(out.getDate() + days);
  return out;
}}

function quarterStart(base) {{
  const quarterMonth = Math.floor(base.getMonth() / 3) * 3;
  return new Date(base.getFullYear(), quarterMonth, 1);
}}

function bindDateFilter() {{
  const form = document.getElementById("trend-date-filter");
  const startInput = document.getElementById("trend-start-date");
  const endInput = document.getElementById("trend-end-date");
  const initial = new URL(DATA_URL, window.location.origin);
  const initialStart = initial.searchParams.get("start_date") || startInput.value || "";
  const initialEnd = initial.searchParams.get("end_date") || endInput.value || "";
  startInput.value = initialStart || (initialEnd ? defaultStartForEnd(initialEnd) : "");
  endInput.value = initialEnd || (initialStart ? initialStart : "");
  setActiveShortcut("custom");
  updateRangeSummary(startInput.value, endInput.value);
  form.addEventListener("submit", (event) => {{
    event.preventDefault();
    if (!startInput.value || !endInput.value) {{
      setMessage("开始日期和结束日期不能为空。");
      return;
    }}
    const days = rangeDays(startInput.value, endInput.value);
    if (days > 92) {{
      setMessage("单次查看范围建议不超过一个季度，请缩小日期范围。");
      return;
    }}
    setActiveShortcut("custom");
    updateRangeSummary(startInput.value, endInput.value);
    loadTrend(trendPath(startInput.value, endInput.value));
  }});
  document.querySelectorAll("[data-range-shortcut]").forEach((button) => {{
    button.addEventListener("click", () => {{
      const shortcutEnd = latestAvailableDate || initialEnd || endInput.value || "";
      const endBase = shortcutEnd ? new Date(`${{shortcutEnd}}T00:00:00`) : new Date();
      let start = new Date(endBase.getTime());
      let end = new Date(endBase.getTime());
      const mode = button.getAttribute("data-range-shortcut");
      if (mode === "this-month") {{
        start = new Date(end.getFullYear(), end.getMonth(), 1);
      }} else if (mode === "last-month") {{
        start = new Date(end.getFullYear(), end.getMonth() - 1, 1);
        end = new Date(end.getFullYear(), end.getMonth(), 0);
      }} else if (mode === "last-7") {{
        start = shiftDays(end, -6);
      }} else if (mode === "last-15") {{
        start = shiftDays(end, -14);
      }} else if (mode === "last-30") {{
        start = shiftDays(end, -29);
      }} else if (mode === "last-3-months") {{
        start = new Date(end.getFullYear(), end.getMonth() - 2, 1);
      }} else if (mode === "this-quarter") {{
        start = quarterStart(end);
      }} else if (mode === "last-quarter") {{
        const currentQuarter = quarterStart(end);
        start = new Date(currentQuarter.getFullYear(), currentQuarter.getMonth() - 3, 1);
        end = new Date(currentQuarter.getFullYear(), currentQuarter.getMonth(), 0);
      }}
      startInput.value = padDate(start);
      endInput.value = padDate(end);
      setActiveShortcut(mode);
      updateRangeSummary(startInput.value, endInput.value);
      loadTrend(trendPath(startInput.value, endInput.value));
    }});
  }});
}}

function defaultStartForEnd(endDate) {{
  const parts = String(endDate || "").split("-").map(Number);
  if (parts.length !== 3 || parts.some((part) => Number.isNaN(part))) return "";
  return padDate(new Date(parts[0], parts[1] - 3, 1));
}}

bindDateFilter();
loadTrend(DATA_URL);
"""


def _trend_initial_dates_from_api_path(api_path: str) -> tuple[str, str]:
    query = parse_qs(urlsplit(api_path).query)
    start_date = (query.get("start_date") or [""])[0]
    end_date = (query.get("end_date") or [""])[0]
    if not start_date and not end_date:
        end_date = date.today().isoformat()
    if not start_date and end_date:
        start_date = _trend_default_start_for_end(end_date)
    if start_date and not end_date:
        end_date = start_date
    return start_date, end_date


def _trend_range_days(start_date: str, end_date: str) -> int:
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        return 0
    return max((end - start).days + 1, 0)


def _trend_default_start_for_end(end_date: str) -> str:
    try:
        end = date.fromisoformat(end_date)
    except ValueError:
        return ""
    month_index = end.year * 12 + end.month - 1 - 2
    year = month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1).isoformat()


def _segment(source: DashboardSource, names: list[str]) -> SegmentMetrics:
    chosen = names[0]
    for name in names:
        if source.metric("segment", name, "mtd_unique_leads").actual:
            chosen = name
            break
    return SegmentMetrics(
        label=chosen,
        leads=source.metric("segment", chosen, "mtd_unique_leads").actual,
        deals=source.metric("segment", chosen, "mtd_deals").actual,
        spend=source.metric("segment", chosen, "mtd_spend").actual,
        cpl=source.metric("segment", chosen, "mtd_cpl").actual,
        cps=source.metric("segment", chosen, "mtd_cps").actual,
    )


def _num(value: object) -> float:
    text = "" if value is None else str(value).strip().replace(",", "")
    if not text or text in {"-", "nan", "NaN", "N/A"}:
        return 0.0
    scale = 0.01 if text.endswith("%") else 1.0
    if text.endswith("%"):
        text = text[:-1]
    try:
        return float(text) * scale
    except ValueError:
        return 0.0


def _optional_num(value: object) -> float | None:
    text = "" if value is None else str(value).strip().replace(",", "")
    if not text or text in {"-", "nan", "NaN", "N/A"}:
        return None
    scale = 0.01 if text.endswith("%") else 1.0
    if text.endswith("%"):
        text = text[:-1]
    try:
        return float(text) * scale
    except ValueError:
        return None


def _fmt_metric_target(metric: Metric) -> str:
    if metric.target is None:
        return "未提供"
    if "元" in metric.unit:
        return f"目标 {_fmt_money(metric.target)}"
    if "人次" in metric.unit:
        return f"目标 {_fmt_wan(metric.target)}"
    return f"目标 {_fmt_int(metric.target)}"


def _fmt_metric_rate(metric: Metric) -> str:
    return _fmt_optional_pct(metric.rate)


def _fmt_optional_wan(value: float | None) -> str:
    if value is None:
        return "未提供"
    return _fmt_wan(value)


def _fmt_optional_pct(value: float | None) -> str:
    if value is None:
        return "未提供"
    return _fmt_pct(value)


def _num_or_zero(value: float | None) -> float:
    return 0.0 if value is None else float(value)


def _fmt_int(value: float) -> str:
    return f"{value:,.0f}"


def _fmt_float(value: float) -> str:
    if abs(value - round(value)) < 0.000001:
        return _fmt_int(value)
    return f"{value:,.2f}"


def _fmt_wan(value: float) -> str:
    return f"{value / 10000:,.2f}万"


def _fmt_money(value: float) -> str:
    return f"¥{value:,.2f}"


def _fmt_money_wan(value: float) -> str:
    return f"¥{value / 10000:,.2f}万" if abs(value) >= 10000 else _fmt_money(value)


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _log_ratio(value: float, max_value: float) -> float:
    if value <= 0 or max_value <= 0:
        return 0.0
    import math

    return math.log10(value + 1) / math.log10(max_value + 1)


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _script_json(value: str) -> str:
    return value.replace("</", "<\\/")


def _script_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("</", "<\\/")


_CSS = """
:root {
  --color-bg: #f4f6f3;
  --color-surface: #ffffff;
  --color-surface-muted: #f7faf7;
  --color-border: #d8ded7;
  --color-border-strong: #b8c3bd;
  --color-text: #182026;
  --color-text-muted: #65727c;
  --color-text-subtle: #8a969e;
  --color-series-current: #2f62a3;
  --color-series-previous: #7a8b91;
  --color-series-target: #b76b00;
  --color-focus: #047b75;
  --color-tooltip-bg: #ffffff;
  --font-base: "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", sans-serif;
  --font-number: "DIN Alternate", "Avenir Next Condensed", "PingFang SC", sans-serif;
  --font-size-title: 34px;
  --font-size-section: 26px;
  --font-size-card-title: 12px;
  --font-size-value: 31px;
  --font-size-body: 14px;
  --font-size-caption: 12px;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --radius-control: 6px;
  --radius-card: 8px;
  --shadow-panel: 0 8px 20px rgba(24, 32, 38, 0.08);
  --shadow-tooltip: 0 12px 28px rgba(24, 32, 38, 0.16);
  --bg: var(--color-bg);
  --paper: var(--color-surface);
  --ink: var(--color-text);
  --muted: var(--color-text-muted);
  --line: var(--color-border);
  --teal: #047b75;
  --green: #2d7f4f;
  --amber: #b76b00;
  --red: #b73535;
  --blue: #2f62a3;
  --soft-teal: #e2f2ef;
  --soft-amber: #fff0d6;
  --soft-red: #fbe4e2;
  --shadow: var(--shadow-panel);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  color: var(--ink);
  background:
    linear-gradient(90deg, rgba(4,123,117,0.06) 1px, transparent 1px),
    linear-gradient(180deg, #fbfcf8 0%, var(--bg) 100%);
  background-size: 28px 28px, auto;
  font-family: var(--font-base);
}
button:focus-visible,
input:focus-visible,
select:focus-visible,
summary:focus-visible,
a:focus-visible,
.kpi-card:focus-visible,
.chart-hover-target:focus-visible {
  outline: 3px solid rgba(4, 123, 117, 0.28);
  outline-offset: 2px;
}
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
  padding: 34px 42px 24px;
  background: #182026;
  color: #f8faf6;
  border-bottom: 5px solid var(--teal);
}
.eyebrow, .kicker {
  margin: 0 0 8px;
  color: #86bcb6;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
}
h1, h2, h3, p { margin-top: 0; }
h1 { margin-bottom: 8px; font-size: 34px; line-height: 1.15; }
h2 { margin-bottom: 0; font-size: 26px; line-height: 1.2; }
h3 { margin-bottom: 16px; font-size: 22px; }
.subtitle { max-width: 820px; margin-bottom: 0; color: #dce5df; line-height: 1.7; font-size: 14px; }
.dashboard-meta {
  display: grid;
  grid-template-columns: repeat(4, minmax(130px, 1fr));
  gap: 10px;
  max-width: 940px;
  margin-top: 18px;
}
.dashboard-meta div {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid rgba(248,250,246,0.18);
  background: rgba(255,255,255,0.06);
}
.dashboard-meta span,
.dashboard-meta strong { display: block; }
.dashboard-meta span {
  margin-bottom: 5px;
  color: #9fb5b1;
  font-size: 11px;
}
.dashboard-meta strong {
  color: #f8faf6;
  font-size: 12px;
  overflow-wrap: anywhere;
}
.source-pill {
  min-width: 280px;
  padding: 14px 16px;
  border: 1px solid rgba(248,250,246,0.2);
  background: rgba(255,255,255,0.06);
}
.topbar-tools {
  display: grid;
  grid-template-columns: minmax(180px, 220px) minmax(280px, 360px);
  gap: 12px;
  align-items: stretch;
}
.date-switch {
  display: block;
  padding: 14px 16px;
  border: 1px solid rgba(248,250,246,0.2);
  background: rgba(255,255,255,0.06);
}
.date-switch span {
  display: block;
  color: #9fb5b1;
  font-size: 12px;
  margin-bottom: 7px;
}
.date-switch select {
  width: 100%;
  height: 32px;
  border: 1px solid rgba(248,250,246,0.24);
  background: #f8faf6;
  color: var(--ink);
  font: inherit;
  font-size: 13px;
  font-weight: 800;
}
.source-pill span, .source-pill strong { display: block; }
.source-pill span { color: #9fb5b1; font-size: 12px; margin-bottom: 4px; }
.source-pill strong { font-size: 13px; overflow-wrap: anywhere; }
.nav {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  gap: 2px;
  padding: 0 42px;
  background: rgba(244,246,243,0.94);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line);
}
.nav a {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  min-height: 44px;
  padding: 0 16px;
  color: var(--ink);
  text-decoration: none;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
  border-left: 1px solid transparent;
  border-right: 1px solid transparent;
}
.nav a:hover { color: var(--teal); background: #fff; border-color: var(--line); }
main { padding-bottom: 56px; }
.section { padding: 34px 42px 18px; border-bottom: 1px solid var(--line); }
.band-plain { background: rgba(255,255,255,0.48); }
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
  margin-bottom: 22px;
}
.section-note {
  max-width: 560px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
  margin-bottom: 0;
}
.decision-section {
  padding-top: 30px;
  background: #f8faf6;
}
.decision-board {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(320px, 0.85fr);
  gap: 16px;
}
.decision-main,
.decision-side {
  background: var(--paper);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}
.decision-main { padding: 18px; }
.decision-side {
  display: grid;
  gap: 16px;
  padding: 18px;
}
.decision-side h3 {
  margin-bottom: 10px;
  font-size: 16px;
}
.decision-title-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 14px;
}
.decision-title-row span,
.decision-block-label {
  display: block;
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.decision-title-row strong {
  display: block;
  margin-top: 3px;
  font-size: 22px;
}
.decision-block-label { margin-bottom: 8px; }
.readonly-badge {
  padding: 6px 10px;
  color: var(--teal);
  background: var(--soft-teal);
  border: 1px solid #b8d8d2;
}
.decision-kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.decision-kpi {
  min-height: 116px;
  padding: 14px;
  border: 1px solid var(--line);
  background: #fbfdf9;
}
.decision-kpi.tone-green { border-top: 4px solid var(--green); }
.decision-kpi.tone-amber { border-top: 4px solid var(--amber); }
.decision-kpi.tone-red { border-top: 4px solid var(--red); }
.decision-kpi.tone-blue { border-top: 4px solid var(--blue); }
.decision-kpi.tone-teal { border-top: 4px solid var(--teal); }
.decision-kpi.tone-ink { border-top: 4px solid var(--ink); }
.decision-kpi span,
.attention-item span {
  display: block;
  color: var(--muted);
  font-size: 12px;
}
.decision-kpi strong {
  display: block;
  margin-top: 8px;
  font-family: "DIN Alternate", "Avenir Next Condensed", "PingFang SC", sans-serif;
  font-size: 28px;
  line-height: 1.1;
}
.decision-kpi-foot {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  margin-top: 12px;
}
.decision-kpi em,
.status-row strong {
  font-style: normal;
  font-size: 12px;
  font-weight: 900;
}
.decision-kpi em.good,
.status-row strong.good { color: var(--green); }
.decision-kpi em.watch,
.status-row strong.watch { color: var(--amber); }
.decision-kpi em.risk,
.status-row strong.risk { color: var(--red); }
.decision-kpi em.neutral,
.status-row strong.neutral { color: var(--muted); }
.decision-status-list,
.attention-list {
  display: grid;
  gap: 8px;
}
.status-row {
  display: grid;
  grid-template-columns: minmax(90px, 1fr) 72px minmax(80px, 1fr);
  gap: 8px;
  align-items: center;
  min-height: 38px;
  padding: 8px 10px;
  background: #f7faf7;
  border: 1px solid var(--line);
}
.status-row span { color: var(--ink); font-size: 13px; font-weight: 800; }
.attention-item {
  padding: 11px 12px;
  background: #f7faf7;
  border: 1px solid var(--line);
  border-left: 4px solid var(--teal);
}
.attention-item.tone-blue { border-left-color: var(--blue); }
.attention-item.tone-green { border-left-color: var(--green); }
.attention-item strong {
  display: block;
  margin: 5px 0;
  font-size: 16px;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.loading {
  grid-column: 1 / -1;
  padding: 18px;
  background: var(--paper);
  border: 1px solid var(--line);
  color: var(--muted);
  font-weight: 700;
}
.metric-card {
  position: relative;
  min-height: 138px;
  padding: 18px;
  background: var(--paper);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}
.metric-card::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  width: 6px;
  height: 100%;
  background: var(--teal);
}
.metric-card.tone-green::before { background: var(--green); }
.metric-card.tone-amber::before { background: var(--amber); }
.metric-card.tone-red::before { background: var(--red); }
.metric-card.tone-blue::before { background: var(--blue); }
.metric-card.tone-ink::before { background: var(--ink); }
.metric-label { color: var(--muted); font-size: 13px; margin-bottom: 12px; }
.metric-value {
  font-family: "DIN Alternate", "Avenir Next Condensed", "PingFang SC", sans-serif;
  font-size: 32px;
  font-weight: 900;
  line-height: 1.1;
}
.metric-sub { margin-top: 10px; color: var(--muted); font-size: 12px; }
.metric-help {
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: calc(100% + 8px);
  opacity: 0;
  transform: translateY(6px);
  pointer-events: none;
  padding: 10px 12px;
  background: #182026;
  color: #f8faf6;
  font-size: 12px;
  line-height: 1.5;
  box-shadow: var(--shadow);
}
.metric-card:hover .metric-help,
.metric-card:focus .metric-help { opacity: 1; transform: translateY(0); }
.funnel-panel {
  display: grid;
  gap: 10px;
  padding: 18px;
  background: var(--paper);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}
.funnel-row {
  display: grid;
  grid-template-columns: 50px minmax(0, 1fr) 130px 96px;
  align-items: center;
  gap: 16px;
  min-height: 58px;
}
.funnel-index { color: var(--teal); font-weight: 900; }
.funnel-label { display: flex; justify-content: space-between; gap: 14px; margin-bottom: 8px; }
.funnel-label span { color: var(--muted); font-size: 12px; }
.funnel-track { height: 14px; background: #e8ece7; overflow: hidden; }
.funnel-fill { height: 100%; background: linear-gradient(90deg, var(--teal), #41a36d, var(--amber)); }
.funnel-value, .funnel-conversion {
  font-family: "DIN Alternate", "Avenir Next Condensed", "PingFang SC", sans-serif;
  font-weight: 900;
}
.funnel-value { text-align: right; font-size: 22px; }
.funnel-conversion { color: var(--muted); text-align: right; }
.quality-strip { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 14px; }
.quality-strip span {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  padding: 8px 12px;
  background: #fff;
  border: 1px solid var(--line);
  color: var(--muted);
}
.quality-strip strong { color: var(--ink); }
.segment-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.segment-panel {
  padding: 22px;
  background: var(--paper);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}
.segment-panel.ex7 { border-top: 6px solid var(--blue); }
.segment-panel.non-ex7 { border-top: 6px solid var(--green); }
.segment-panel ul {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  padding: 0;
  margin: 0;
  list-style: none;
}
.segment-panel li {
  min-height: 82px;
  padding: 12px;
  background: #f7f9f5;
  border: 1px solid var(--line);
}
.segment-panel li span { display: block; color: var(--muted); font-size: 12px; margin-bottom: 8px; }
.segment-panel li strong {
  font-family: "DIN Alternate", "Avenir Next Condensed", "PingFang SC", sans-serif;
  font-size: 21px;
}
.delta-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}
.delta-card {
  padding: 16px;
  background: linear-gradient(180deg, var(--soft-amber), #fff);
  border: 1px solid #e7c584;
}
.delta-card span, .delta-card small { display: block; color: #76500c; }
.delta-card strong {
  display: block;
  margin: 8px 0;
  font-family: "DIN Alternate", "Avenir Next Condensed", "PingFang SC", sans-serif;
  font-size: 28px;
}
.table-actions {
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(260px, 1fr);
  gap: 10px;
  align-items: end;
}
.table-search {
  display: grid;
  gap: 6px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.table-search input {
  width: 100%;
  height: 34px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  font: inherit;
  font-size: 13px;
  padding: 0 10px;
}
.table-search input:focus {
  outline: 2px solid rgba(4,123,117,0.2);
  border-color: var(--teal);
}
.sort-controls { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
.sort-controls button {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  font: inherit;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}
.sort-controls button:hover,
.sort-controls button.active-sort { border-color: var(--teal); color: var(--teal); background: var(--soft-teal); }
.table-wrap {
  overflow-x: auto;
  background: var(--paper);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}
table { width: 100%; border-collapse: collapse; min-width: 820px; }
th, td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--line);
  text-align: right;
  vertical-align: middle;
  font-size: 13px;
}
th:first-child, td:first-child { text-align: left; }
thead th {
  position: sticky;
  top: 45px;
  z-index: 2;
  background: #eef3ee;
  color: #4b5961;
  font-size: 12px;
}
tbody tr:hover { background: #f7faf7; }
tbody tr[hidden] { display: none; }
.anchor-name { display: block; font-weight: 900; color: var(--ink); }
small { color: var(--muted); font-size: 11px; }
.bar-cell {
  display: inline-block;
  width: min(42vw, 260px);
  height: 8px;
  margin-right: 10px;
  background: #e7ebe5;
  vertical-align: middle;
}
.bar-cell span { display: block; height: 100%; background: var(--blue); }
.bar-cell.seed span { background: var(--green); }
.seed-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: baseline;
  margin-bottom: 14px;
  padding: 14px 16px;
  background: var(--soft-teal);
  border: 1px solid #b8d8d2;
}
.seed-summary strong {
  font-family: "DIN Alternate", "Avenir Next Condensed", "PingFang SC", sans-serif;
  font-size: 28px;
}
body[data-dashboard-mode="business"] {
  background:
    linear-gradient(180deg, #eef2ed 0%, #f7f8f4 42%, #eef2ed 100%);
}
body[data-dashboard-mode="business"] .topbar {
  align-items: stretch;
  background: #f8faf6;
  color: var(--ink);
  border-bottom: 1px solid var(--line);
  box-shadow: 0 16px 40px rgba(24, 32, 38, 0.08);
}
body[data-dashboard-mode="business"] .eyebrow,
body[data-dashboard-mode="business"] .kicker {
  color: var(--blue);
}
body[data-dashboard-mode="business"] .subtitle {
  color: #4b5961;
}
body[data-dashboard-mode="business"] .dashboard-meta div,
body[data-dashboard-mode="business"] .date-switch,
body[data-dashboard-mode="business"] .business-range-query,
body[data-dashboard-mode="business"] .business-scope-note {
  border: 1px solid var(--line);
  background: #ffffff;
}
body[data-dashboard-mode="business"] .dashboard-meta span,
body[data-dashboard-mode="business"] .date-switch span,
body[data-dashboard-mode="business"] .business-range-query span,
body[data-dashboard-mode="business"] .business-scope-note span {
  color: var(--muted);
}
body[data-dashboard-mode="business"] .dashboard-meta strong,
body[data-dashboard-mode="business"] .business-scope-note strong {
  color: var(--ink);
}
body[data-dashboard-mode="business"] .topbar-tools {
  min-width: 640px;
  grid-template-columns: minmax(170px, 210px) minmax(420px, 1fr);
  align-content: end;
}
.business-range-query {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
}
.business-range-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(135px, 1fr)) auto;
  gap: 8px;
  align-items: end;
}
.business-range-fields label {
  display: grid;
  gap: 6px;
}
.business-range-fields span {
  font-size: 12px;
  font-weight: 800;
}
.business-range-fields input,
.business-range-fields button {
  min-height: 34px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  font: inherit;
  font-size: 13px;
}
.business-range-fields input {
  padding: 0 9px;
}
.business-range-fields button {
  padding: 0 12px;
  font-weight: 900;
  cursor: pointer;
}
.business-range-fields button:hover {
  border-color: var(--teal);
  color: var(--teal);
  background: var(--soft-teal);
}
.business-range-query p {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.45;
}
.business-scope-note {
  display: block;
  padding: 14px 16px;
}
.business-scope-note span,
.business-scope-note strong {
  display: block;
}
.business-scope-note span {
  margin-bottom: 7px;
  font-size: 12px;
}
.business-scope-note strong {
  font-size: 13px;
}
body[data-dashboard-mode="business"] .nav {
  position: static;
  top: auto;
  z-index: auto;
  background: rgba(248,250,246,0.96);
}
body[data-dashboard-mode="business"] .section {
  padding-left: clamp(22px, 4vw, 56px);
  padding-right: clamp(22px, 4vw, 56px);
}
body[data-dashboard-mode="business"] .table-wrap {
  overflow-x: auto;
}
body[data-dashboard-mode="business"] .metric-table {
  table-layout: fixed;
  min-width: 1120px;
}
body[data-dashboard-mode="business"] .lead-metric-table {
  min-width: 1280px;
}
body[data-dashboard-mode="business"] .lead-metric-table .col-label { width: 8%; }
body[data-dashboard-mode="business"] .lead-metric-table .col-parent { width: 13%; }
body[data-dashboard-mode="business"] .lead-metric-table .col-bar { width: 12%; }
body[data-dashboard-mode="business"] .lead-metric-table .col-value { width: 7%; }
body[data-dashboard-mode="business"] .lead-metric-table .col-orders { width: 9%; }
body[data-dashboard-mode="business"] .lead-metric-table .col-visits { width: 7%; }
body[data-dashboard-mode="business"] .lead-metric-table .col-visit-rate { width: 7%; }
body[data-dashboard-mode="business"] .lead-metric-table .col-visit-deal-rate { width: 8%; }
body[data-dashboard-mode="business"] .lead-metric-table .col-number { width: 7%; }
body[data-dashboard-mode="business"] .lead-metric-table .col-spend { width: 7%; }
body[data-dashboard-mode="business"] .lead-metric-table .col-money { width: 5%; }
body[data-dashboard-mode="business"] .seed-metric-table .col-label { width: 26%; }
body[data-dashboard-mode="business"] .seed-metric-table .col-bar { width: 25%; }
body[data-dashboard-mode="business"] .seed-metric-table .col-value { width: 11%; }
body[data-dashboard-mode="business"] .seed-metric-table .col-target { width: 12%; }
body[data-dashboard-mode="business"] .seed-metric-table .col-rate { width: 12%; }
body[data-dashboard-mode="business"] .seed-metric-table .col-number { width: 14%; }
body[data-dashboard-mode="business"] .metric-table th,
body[data-dashboard-mode="business"] .metric-table td {
  min-height: 64px;
  padding: 12px 10px;
}
body[data-dashboard-mode="business"] .metric-table thead th {
  white-space: nowrap;
}
body[data-dashboard-mode="business"] .metric-table th:first-child {
  padding-left: 18px;
}
body[data-dashboard-mode="business"] .lead-metric-table th,
body[data-dashboard-mode="business"] .lead-metric-table td {
  height: auto;
  vertical-align: middle;
}
body[data-dashboard-mode="business"] .anchor-parent-cell {
  color: var(--muted);
  font-weight: 700;
  line-height: 1.35;
  text-align: left;
  white-space: normal;
  word-break: break-word;
}
body[data-dashboard-mode="business"] .metric-table .bar-metric-cell,
body[data-dashboard-mode="business"] .metric-table .bar-track-cell {
  min-width: 0;
}
body[data-dashboard-mode="business"] .bar-metric {
  display: block;
  width: 100%;
}
body[data-dashboard-mode="business"] .bar-metric .bar-cell {
  display: block;
  width: 100%;
  min-width: 0;
  margin-right: 0;
}
body[data-dashboard-mode="business"] .bar-value,
body[data-dashboard-mode="business"] .metric-value-cell,
body[data-dashboard-mode="business"] .metric-number-cell,
body[data-dashboard-mode="business"] .metric-money-cell,
body[data-dashboard-mode="business"] .metric-rate-cell {
  font-family: "DIN Alternate", "Avenir Next Condensed", "PingFang SC", sans-serif;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  text-align: right;
}
body[data-dashboard-mode="business"] .bar-value {
  display: block;
  color: var(--ink);
  font-size: 15px;
  line-height: 1;
}
body[data-dashboard-mode="business"] .metric-value-header,
body[data-dashboard-mode="business"] .bar-header {
  text-align: right;
}
body[data-dashboard-mode="business"] .metric-rate-pair {
  display: inline-flex;
  justify-content: flex-end;
  align-items: baseline;
  gap: 6px;
  width: 100%;
}
body[data-dashboard-mode="business"] .number-main {
  display: inline-block;
  min-width: 28px;
  text-align: right;
}
body[data-dashboard-mode="business"] .rate-chip {
  display: inline-block;
  min-width: 58px;
  text-align: left;
}
body[data-dashboard-mode="business"] .decision-section {
  background:
    linear-gradient(90deg, rgba(47,98,163,0.08), transparent 46%),
    #f8faf6;
}
.business-home .section-head {
  align-items: center;
}
.business-home .decision-board {
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.95fr);
}
.business-home .decision-main,
.business-home .decision-side,
.workbench-panel {
  border-radius: 8px;
}
.business-home .decision-main {
  border-top: 5px solid var(--blue);
}
.business-home .decision-side {
  border-top: 5px solid var(--teal);
}
.business-home .decision-kpi-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.business-home .decision-kpi {
  min-height: 124px;
  background: linear-gradient(180deg, #ffffff, #fbfcf8);
}
.dimension-rail,
.dimension-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.dimension-rail {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}
.dimension-rail a,
.dimension-tabs span {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 11px;
  color: var(--ink);
  background: #f3f6f0;
  border: 1px solid var(--line);
  text-decoration: none;
  font-size: 12px;
  font-weight: 800;
}
.dimension-rail a:hover {
  color: var(--blue);
  border-color: rgba(47,98,163,0.34);
}
.workbench-section {
  background: #f5f7f2;
}
.dimension-tabs {
  margin-bottom: 14px;
}
.workbench-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}
.workbench-panel {
  min-height: 132px;
  padding: 16px;
  background: #ffffff;
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}
.workbench-panel span,
.workbench-panel small {
  display: block;
  color: var(--muted);
}
.workbench-panel span {
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 900;
}
.workbench-panel strong {
  display: block;
  min-height: 42px;
  color: var(--ink);
  font-family: "DIN Alternate", "Avenir Next Condensed", "PingFang SC", sans-serif;
  font-size: 21px;
  line-height: 1.15;
  overflow-wrap: anywhere;
}
.workbench-panel small {
  margin-top: 8px;
  line-height: 1.45;
}
body[data-dashboard-mode="trend"] {
  background:
    linear-gradient(180deg, #eef3ef 0%, #f8faf6 46%, #eef3ef 100%);
}
body[data-dashboard-mode="trend"] .topbar {
  align-items: stretch;
  background: #f8faf6;
  color: var(--ink);
  border-bottom: 1px solid var(--line);
  box-shadow: 0 16px 40px rgba(24, 32, 38, 0.08);
}
body[data-dashboard-mode="trend"] .eyebrow,
body[data-dashboard-mode="trend"] .kicker {
  color: var(--blue);
}
body[data-dashboard-mode="trend"] .subtitle {
  color: #46545d;
  max-width: 900px;
}
body[data-dashboard-mode="trend"] .dashboard-meta {
  grid-template-columns: repeat(4, minmax(130px, 1fr));
}
body[data-dashboard-mode="trend"] .dashboard-meta div,
.trend-boundary-card {
  border: 1px solid var(--line);
  background: #ffffff;
}
body[data-dashboard-mode="trend"] .dashboard-meta span,
.trend-boundary-card span {
  color: var(--muted);
}
body[data-dashboard-mode="trend"] .dashboard-meta strong,
.trend-boundary-card strong {
  color: var(--ink);
}
.trend-boundary-card {
  min-width: 300px;
  max-width: 360px;
  padding: 18px;
  border-top: 5px solid var(--blue);
  box-shadow: var(--shadow);
}
.trend-boundary-card span,
.trend-boundary-card strong {
  display: block;
}
.trend-boundary-card span {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 900;
}
.trend-boundary-card strong {
  font-size: 20px;
  line-height: 1.25;
}
.trend-boundary-card p {
  margin: 12px 0 0;
  color: #4b5961;
  font-size: 13px;
  line-height: 1.65;
}
.trend-status-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.trend-status-strip span {
  display: block;
  min-height: 70px;
  padding: 14px 16px;
  color: var(--muted);
  background: #ffffff;
  border: 1px solid var(--line);
  border-left: 5px solid var(--teal);
  font-size: 12px;
  font-weight: 900;
}
.trend-status-strip span:nth-child(2) { border-left-color: var(--amber); }
.trend-status-strip span:nth-child(3) { border-left-color: var(--blue); }
.trend-status-strip strong {
  display: block;
  margin-top: 8px;
  color: var(--ink);
  font-size: 15px;
  line-height: 1.35;
}
body[data-dashboard-mode="trend"] .metric-card {
  min-height: 156px;
}
body[data-dashboard-mode="trend"] .trend-spark {
  margin-top: 16px;
}
body[data-dashboard-mode="trend"] .trend-table td:last-child {
  min-width: 150px;
}
body[data-dashboard-mode="trend"] .topbar {
  align-items: center;
}
body[data-dashboard-mode="trend"] .trend-meta {
  grid-template-columns: minmax(240px, 360px);
}
.date-filter-panel {
  display: grid;
  gap: var(--space-4);
  max-width: 1120px;
  margin-top: 20px;
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-panel);
}
.date-input-group {
  display: grid;
  grid-template-columns: repeat(2, minmax(150px, 190px)) minmax(108px, auto);
  align-items: end;
  gap: var(--space-3);
}
.date-filter-panel label,
.date-filter-panel label span {
  display: block;
}
.date-filter-panel label span {
  margin-bottom: 6px;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  font-weight: 900;
}
.date-filter-panel input {
  width: 100%;
  min-height: 42px;
  padding: 9px 11px;
  color: var(--color-text);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  font: inherit;
}
.date-filter-panel button,
.quick-range-group button {
  min-height: 42px;
  padding: 9px 13px;
  color: var(--color-text);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  font-weight: 900;
  cursor: pointer;
}
.date-filter-panel button:hover,
.quick-range-group button:hover {
  border-color: var(--color-focus);
}
.date-filter-panel button.is-active,
.quick-range-group button.is-active {
  color: var(--color-focus);
  background: var(--soft-teal);
  border-color: rgba(4, 123, 117, 0.42);
}
.quick-range-groups {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1.5fr) minmax(160px, 0.65fr);
  gap: var(--space-3);
}
.quick-range-section {
  min-width: 0;
  padding: var(--space-3);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
}
.quick-range-section > span {
  display: block;
  margin-bottom: var(--space-2);
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  font-weight: 900;
}
.quick-range-group {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.quick-range-group button {
  min-height: 36px;
  padding: 7px 10px;
  font-size: var(--font-size-caption);
}
.range-summary {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
}
.range-summary span {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 10px;
  color: var(--color-text);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  font-size: var(--font-size-caption);
  font-weight: 900;
}
.range-summary .range-state-pill {
  color: var(--color-focus);
  background: var(--soft-teal);
  border-color: rgba(4, 123, 117, 0.32);
}
.range-message {
  min-height: 20px;
  margin: 0;
  color: #5a4d24;
  font-size: 13px;
  line-height: 1.45;
}
.kpi-card-grid,
.model-compare-grid,
.business-card-list {
  display: grid;
  gap: 14px;
}
.kpi-card-grid {
  grid-template-columns: repeat(6, minmax(0, 1fr));
}
.model-compare-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.business-card-list {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.business-card-list.account-list {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.account-summary-slot {
  display: grid;
  gap: 14px;
  margin-bottom: 14px;
}
.account-toolbar {
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(150px, 190px) minmax(0, 1fr) auto;
  gap: 12px;
  align-items: end;
  margin-bottom: 14px;
  padding: 14px;
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}
.account-search-control,
.account-sort-control {
  display: grid;
  gap: 6px;
  min-width: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  font-weight: 900;
}
.account-search-control input,
.account-sort-control select {
  width: 100%;
  min-height: 38px;
  padding: 8px 10px;
  color: var(--color-text);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  font: inherit;
  font-size: 13px;
}
.account-search-control input:focus,
.account-sort-control select:focus,
.account-filter-control button:focus-visible,
.account-clear-filters:focus-visible,
.account-detail-toggle:focus-visible {
  outline: 2px solid rgba(4, 123, 117, 0.28);
  outline-offset: 2px;
  border-color: var(--color-focus);
}
.account-filter-control {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}
.account-filter-separator {
  align-self: center;
  color: var(--color-text-muted);
  font-weight: 900;
}
.account-filter-control button,
.account-clear-filters,
.account-detail-toggle {
  min-height: 34px;
  padding: 7px 10px;
  color: var(--color-text);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  font: inherit;
  font-size: var(--font-size-caption);
  font-weight: 900;
  cursor: pointer;
}
.account-filter-control button:hover,
.account-filter-control button.is-active,
.account-clear-filters:hover,
.account-detail-toggle:hover {
  color: var(--color-focus);
  background: var(--soft-teal);
  border-color: rgba(4, 123, 117, 0.38);
}
.account-filter-summary {
  grid-column: 1 / -1;
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  font-weight: 900;
  line-height: 1.5;
}
.account-visibility-note {
  margin: 14px 0 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  line-height: 1.6;
}
.anchor-toolbar {
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(150px, 190px) minmax(0, 1fr) auto;
  gap: 12px;
  align-items: end;
  margin-bottom: 14px;
  padding: 14px;
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}
.anchor-search-control,
.anchor-sort-control {
  display: grid;
  gap: 6px;
  min-width: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  font-weight: 900;
}
.anchor-search-input,
.anchor-sort-select {
  width: 100%;
  min-height: 38px;
  padding: 8px 10px;
  color: var(--color-text);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  font: inherit;
  font-size: 13px;
}
.anchor-search-input:focus,
.anchor-sort-select:focus,
.anchor-filter-chip:focus-visible,
.anchor-clear-filters:focus-visible,
.anchor-detail-toggle:focus-visible,
.anchor-parent-scope:focus-visible,
.anchor-full-account:focus-visible {
  outline: 2px solid rgba(4, 123, 117, 0.28);
  outline-offset: 2px;
  border-color: var(--color-focus);
}
.anchor-filter-control {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}
.anchor-filter-separator {
  align-self: center;
  color: var(--color-text-muted);
  font-weight: 900;
}
.anchor-filter-chip,
.anchor-clear-filters,
.anchor-detail-toggle {
  min-height: 34px;
  padding: 7px 10px;
  color: var(--color-text);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  font: inherit;
  font-size: var(--font-size-caption);
  font-weight: 900;
  cursor: pointer;
}
.anchor-filter-chip:hover,
.anchor-filter-chip.is-active,
.anchor-clear-filters:hover,
.anchor-detail-toggle:hover {
  color: var(--color-focus);
  background: var(--soft-teal);
  border-color: rgba(4, 123, 117, 0.38);
}
.anchor-filter-summary {
  grid-column: 1 / -1;
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  font-weight: 900;
  line-height: 1.5;
}
.seed-toolbar {
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(150px, 190px) minmax(0, 1fr) auto;
  gap: 12px;
  align-items: end;
  margin-bottom: 14px;
  padding: 14px;
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}
.seed-search-control,
.seed-sort-control {
  display: grid;
  gap: 6px;
  min-width: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  font-weight: 900;
}
.seed-search-input,
.seed-sort-select {
  width: 100%;
  min-height: 38px;
  padding: 8px 10px;
  color: var(--color-text);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  font: inherit;
  font-size: 13px;
}
.seed-search-input:focus,
.seed-sort-select:focus,
.seed-filter-chip:focus-visible,
.seed-clear-filters:focus-visible,
.seed-detail-toggle:focus-visible,
.seed-parent-scope:focus-visible {
  outline: 2px solid rgba(4, 123, 117, 0.28);
  outline-offset: 2px;
  border-color: var(--color-focus);
}
.seed-filter-control {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}
.seed-filter-separator {
  align-self: center;
  color: var(--color-text-muted);
  font-weight: 900;
}
.seed-filter-chip,
.seed-clear-filters,
.seed-detail-toggle {
  min-height: 34px;
  padding: 7px 10px;
  color: var(--color-text);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  font: inherit;
  font-size: var(--font-size-caption);
  font-weight: 900;
  cursor: pointer;
}
.seed-filter-chip:hover,
.seed-filter-chip.is-active,
.seed-clear-filters:hover,
.seed-detail-toggle:hover {
  color: var(--color-focus);
  background: var(--soft-teal);
  border-color: rgba(4, 123, 117, 0.38);
}
.seed-filter-summary {
  grid-column: 1 / -1;
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  font-weight: 900;
  line-height: 1.5;
}
.kpi-card,
.model-compare-card,
.account-card,
.anchor-card,
.seed-card {
  min-width: 0;
  padding: 18px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  box-shadow: none;
}
.kpi-card {
  position: relative;
  min-height: 190px;
  border-top: 5px solid var(--teal);
  transition: border-color 0.16s ease, box-shadow 0.16s ease, transform 0.16s ease;
}
.kpi-card:hover,
.kpi-card:focus-within,
.kpi-card:focus-visible {
  border-color: rgba(4, 123, 117, 0.4);
  box-shadow: var(--shadow-panel);
}
.kpi-card.tone-green { border-top-color: var(--green); }
.kpi-card.tone-amber { border-top-color: var(--amber); }
.kpi-card.tone-red { border-top-color: var(--red); }
.kpi-card.tone-blue { border-top-color: var(--blue); }
.kpi-card.tone-ink { border-top-color: var(--ink); }
.business-label,
.card-measure span,
.compare-primary span {
  display: block;
  color: var(--color-text-muted);
  font-size: var(--font-size-card-title);
  font-weight: 900;
}
.business-value,
.card-measure strong,
.compare-primary strong {
  display: block;
  margin-top: 8px;
  font-family: var(--font-number);
  font-size: var(--font-size-value);
  font-weight: 900;
  line-height: 1.05;
  overflow-wrap: anywhere;
}
.business-sub {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  line-height: 1.4;
}
.kpi-card-help {
  position: absolute;
  left: var(--space-3);
  right: var(--space-3);
  bottom: calc(100% + var(--space-2));
  z-index: 12;
  opacity: 0;
  visibility: hidden;
  transform: translateY(4px);
  pointer-events: none;
  padding: 10px 12px;
  color: var(--color-text);
  background: var(--color-tooltip-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  box-shadow: var(--shadow-tooltip);
  font-size: var(--font-size-caption);
  line-height: 1.55;
}
.kpi-card:hover .kpi-card-help,
.kpi-card:focus-visible .kpi-card-help,
.kpi-card:focus-within .kpi-card-help {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}
.account-card-topline {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(130px, 0.8fr);
  gap: 12px;
  margin-top: 12px;
}
.account-card-topline .card-measure {
  min-width: 0;
  padding: 12px;
  background: #f7faf7;
  border: 1px solid #e0e7e2;
  border-radius: 8px;
}
.account-card-topline .card-measure strong {
  font-size: 27px;
}
.account-card-topline .card-measure.secondary strong {
  font-size: 24px;
}
.account-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}
.account-summary-grid span,
.anchor-summary-grid span,
.seed-summary-grid span {
  min-width: 0;
  min-height: 72px;
  padding: 10px;
  background: #f7faf7;
  border: 1px solid #e0e7e2;
  border-radius: var(--radius-control);
}
.account-summary-grid small,
.anchor-summary-grid small,
.seed-summary-grid small,
.anchor-full-account small {
  display: block;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  font-weight: 900;
  line-height: 1.35;
}
.account-summary-grid strong,
.anchor-summary-grid strong,
.seed-summary-grid strong,
.anchor-full-account strong {
  display: block;
  margin-top: 7px;
  color: var(--color-text);
  font-family: var(--font-number);
  font-size: 18px;
  line-height: 1.15;
  overflow-wrap: anywhere;
}
.anchor-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}
.seed-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}
.account-detail-toggle,
.anchor-detail-toggle,
.seed-detail-toggle {
  flex: 0 0 auto;
}
.account-detail-panel,
.anchor-detail-panel,
.seed-detail-panel {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  transition: max-height 0.24s ease, opacity 0.18s ease;
}
.account-detail-panel.is-expanded,
.anchor-detail-panel.is-expanded,
.seed-detail-panel.is-expanded {
  opacity: 1;
  max-height: none;
  overflow: visible;
}
.account-detail-panel .metric-group:first-child,
.anchor-detail-panel .metric-group:first-child,
.seed-detail-panel .metric-group:first-child {
  margin-top: 16px;
}
.anchor-full-account {
  min-width: 0;
  margin-top: 16px;
  padding: 10px;
  background: #f7faf7;
  border: 1px solid #e0e7e2;
  border-radius: var(--radius-control);
}
.anchor-detail-trend-note {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}
.anchor-detail-trend-note h4 {
  margin: 0 0 8px;
  color: var(--ink);
  font-size: 13px;
}
.anchor-detail-trend-note p {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  line-height: 1.55;
}
.account-empty-state,
.anchor-empty-state,
.seed-empty-state {
  grid-column: 1 / -1;
  min-height: 132px;
  padding: 28px;
  display: grid;
  align-content: center;
  justify-items: start;
  gap: 8px;
  color: var(--color-text-muted);
  background: #ffffff;
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-card);
}
.account-empty-state strong,
.anchor-empty-state strong,
.seed-empty-state strong {
  color: var(--color-text);
  font-size: 18px;
}
.account-empty-state span,
.anchor-empty-state span,
.seed-empty-state span {
  font-size: var(--font-size-body);
}
.featured-account-card {
  border-left: 5px solid var(--blue);
}
.featured-account-card .card-title-row h3 {
  font-size: 21px;
}
.featured-topline {
  grid-template-columns: minmax(0, 1fr) minmax(180px, 0.7fr);
}
.account-featured-trend-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 16px;
}
.featured-trend-block {
  min-width: 0;
  padding: 14px;
  background: #fbfdfb;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.progress-bar {
  width: 100%;
  height: 8px;
  margin-top: 14px;
  overflow: hidden;
  background: #e7ece6;
  border-radius: 999px;
}
.progress-fill {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--blue), var(--teal));
}
.progress-muted .progress-fill {
  background: #cfd8d2;
}
body[data-dashboard-mode="trend"] .trend-spark {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 48px;
  margin-top: 16px;
}
body[data-dashboard-mode="trend"] .trend-spark span {
  flex: 1;
  min-width: 4px;
  background: #a9c9c3;
  border-radius: 2px 2px 0 0;
}
body[data-dashboard-mode="trend"] .trend-spark.trend-empty {
  align-items: center;
  height: 40px;
  color: var(--muted);
  font-size: 12px;
}
body[data-dashboard-mode="trend"] .trend-spark .spark-gap {
  min-height: 8px;
  background: repeating-linear-gradient(90deg, #d7ded8 0 4px, transparent 4px 8px);
  opacity: 0.85;
}
.history-chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
.history-chart-card {
  min-width: 0;
  min-height: 440px;
  padding: 20px;
  background: #ffffff;
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
}
.trend-panel {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 14px;
}
.history-card-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(136px, auto);
  align-items: start;
  gap: 12px 18px;
  margin-bottom: 0;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--color-border);
}
.trend-panel-title h3 {
  margin: 0 0 8px;
  color: var(--color-text);
  font-size: 17px;
  line-height: 1.25;
}
.trend-panel-title span,
.trend-panel-meta span,
.trend-panel-value small {
  display: block;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  font-weight: 900;
  line-height: 1.35;
}
.trend-panel-value {
  text-align: right;
}
.trend-panel-value strong {
  margin: 6px 0 0;
}
.trend-panel-meta {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.history-chart-card span {
  display: block;
  color: var(--muted);
  font-size: 12px;
  font-weight: 900;
}
.history-chart-card strong {
  display: block;
  margin: 7px 0 12px;
  color: var(--ink);
  font-family: "DIN Alternate", "Avenir Next Condensed", "PingFang SC", sans-serif;
  font-size: 25px;
  line-height: 1.1;
  overflow-wrap: anywhere;
}
.line-chart {
  width: 100%;
  height: 78px;
  color: var(--blue);
  display: block;
}
.line-chart circle {
  fill: #ffffff;
  stroke: currentColor;
  stroke-width: 2;
}
.line-chart.empty-chart {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  background: #f7faf7;
  border: 1px dashed #cbd6d0;
  border-radius: 6px;
  font-size: 12px;
}
.trend-chart {
  position: relative;
  min-height: 332px;
  color: var(--ink);
}
.trend-chart svg {
  display: block;
  width: 100%;
  min-height: 318px;
}
.trend-chart.compact-chart {
  min-height: 0;
  max-width: 680px;
}
.trend-chart.compact-chart svg {
  width: min(100%, 680px);
  min-height: 0;
}
.trend-chart.featured-chart {
  min-height: 250px;
}
.trend-chart.featured-chart svg {
  min-height: 232px;
}
.chart-grid line {
  stroke: #e3e9e5;
  stroke-width: 1;
}
.axis-line {
  stroke: var(--color-border-strong);
  stroke-width: 1.2;
}
.axis-labels text {
  fill: var(--color-text-muted);
  font-size: 12px;
  font-weight: 800;
  text-anchor: end;
}
.x-axis.axis-labels text {
  text-anchor: middle;
}
.chart-line {
  stroke-width: 2.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.current-line {
  stroke: var(--color-series-current);
}
.previous-line {
  stroke: var(--color-series-previous);
  stroke-dasharray: 7 5;
}
.chart-line-draw {
  stroke-dasharray: 900;
  stroke-dashoffset: 900;
  animation: chart-draw 0.8s ease-out forwards;
}
.chart-point {
  fill: #ffffff;
  stroke-width: 2;
  opacity: 0.58;
  transition: r 0.16s ease, fill 0.16s ease;
}
.compact-chart .chart-point {
  opacity: 0.42;
}
.current-point {
  stroke: var(--color-series-current);
}
.previous-point {
  stroke: var(--color-series-previous);
}
.chart-point.is-active {
  r: 5.4;
  fill: #fff7d6;
  opacity: 1;
}
.chart-hover-line {
  stroke: var(--color-series-target);
  stroke-width: 1.4;
  opacity: 0;
  pointer-events: none;
}
.chart-hover-line.is-visible {
  opacity: 1;
}
.chart-hover-target {
  fill: transparent;
  cursor: crosshair;
  pointer-events: all;
}
.chart-tooltip {
  position: absolute;
  z-index: 8;
  display: none;
  visibility: hidden;
  min-width: 180px;
  max-width: 260px;
  padding: 10px 12px;
  color: var(--color-text);
  background: var(--color-tooltip-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  box-shadow: var(--shadow-tooltip);
  font-size: var(--font-size-caption);
  line-height: 1.55;
}
.chart-tooltip.is-visible {
  display: block;
  visibility: visible;
}
.chart-tooltip strong,
.chart-tooltip span {
  display: block;
}
.chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 8px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 900;
}
.chart-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.chart-legend i {
  display: inline-block;
  width: 18px;
  height: 0;
  border-top: 3px solid var(--color-series-current);
}
.chart-legend .legend-previous {
  border-top-color: var(--color-series-previous);
  border-top-style: dashed;
}
.mini-trend-block {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}
.account-trend-switcher {
  margin-top: 16px;
  padding: 12px;
  background: #fbfdfb;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.anchor-trend-switcher {
  margin-top: 16px;
  padding: 12px;
  background: #fbfdfb;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.account-trend-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}
.anchor-trend-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}
.account-trend-toolbar > span,
.anchor-trend-toolbar > span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 900;
}
.account-trend-buttons {
  display: inline-flex;
  gap: 2px;
  padding: 3px;
  background: #edf3ef;
  border: 1px solid var(--line);
  border-radius: 6px;
}
.anchor-trend-buttons {
  display: inline-flex;
  gap: 2px;
  padding: 3px;
  background: #edf3ef;
  border: 1px solid var(--line);
  border-radius: 6px;
}
.account-trend-buttons button,
.anchor-trend-buttons button {
  min-height: 28px;
  padding: 5px 10px;
  color: var(--muted);
  background: transparent;
  border: 0;
  border-radius: 4px;
  font: inherit;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}
.account-trend-buttons button.is-active,
.anchor-trend-buttons button.is-active {
  color: var(--ink);
  background: #ffffff;
  box-shadow: 0 1px 4px rgba(24, 32, 38, 0.12);
}
.account-trend-pane,
.anchor-trend-pane {
  display: none;
}
.account-trend-pane.is-active,
.anchor-trend-pane.is-active {
  display: block;
}
.account-trend-switcher .mini-trend-block,
.anchor-trend-switcher .mini-trend-block {
  margin-top: 0;
  padding-top: 0;
  border-top: 0;
}
.mini-trend-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}
.mini-trend-head span,
.mini-trend-head small {
  color: var(--muted);
  font-size: 12px;
  font-weight: 900;
  line-height: 1.35;
}
.monthly-comparison-slot {
  margin-top: 16px;
}
.monthly-comparison {
  padding: 18px;
  background: #ffffff;
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
}
.section-subhead h3 {
  margin: 0;
  font-size: 18px;
}
.section-subhead p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.55;
}
.monthly-matrix-scroll {
  margin-top: 14px;
  overflow-x: auto;
  padding-bottom: 4px;
}
.monthly-matrix {
  display: grid;
  min-width: 720px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  overflow: visible;
}
.monthly-row {
  display: grid;
  grid-template-columns: minmax(96px, 0.58fr) repeat(var(--monthly-cols, 3), minmax(150px, 1fr));
  min-height: 74px;
  border-top: 1px solid var(--color-border);
}
.monthly-row:first-child {
  border-top: 0;
}
.monthly-header-row {
  min-height: 68px;
  background: var(--color-surface-muted);
}
.monthly-metric,
.monthly-month-coverage,
.monthly-cell {
  min-width: 0;
  padding: 12px;
  border-left: 1px solid var(--color-border);
}
.monthly-metric:first-child {
  border-left: 0;
}
.monthly-metric {
  display: flex;
  align-items: center;
  color: var(--color-text);
  font-weight: 900;
}
.monthly-month-coverage strong,
.monthly-month-coverage small {
  display: block;
}
.monthly-month-coverage strong {
  color: var(--color-text);
  font-size: var(--font-size-body);
}
.monthly-month-coverage small {
  margin-top: 6px;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  line-height: 1.35;
}
.monthly-cell {
  position: relative;
  display: grid;
  align-content: center;
  gap: 8px;
  background: #ffffff;
}
.monthly-cell strong {
  color: var(--color-text);
  font-family: var(--font-number);
  font-size: 18px;
  line-height: 1.1;
}
.monthly-bar {
  display: block;
  width: 100%;
  height: 7px;
  overflow: hidden;
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: 999px;
}
.monthly-bar i {
  display: block;
  height: 100%;
  background: var(--color-series-current);
  border-radius: inherit;
}
.monthly-bar-muted i {
  background: var(--color-series-target);
  opacity: 0.62;
}
.monthly-cell-help {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: calc(100% + 8px);
  z-index: 14;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  padding: 10px 12px;
  color: var(--color-text);
  background: var(--color-tooltip-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  box-shadow: var(--shadow-tooltip);
  font-size: var(--font-size-caption);
  line-height: 1.55;
}
.monthly-cell:hover .monthly-cell-help,
.monthly-cell:focus-visible .monthly-cell-help,
.monthly-cell:focus-within .monthly-cell-help {
  opacity: 1;
  visibility: visible;
}
.monthly-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}
.monthly-card {
  min-width: 0;
  padding: 14px;
  background: #f7faf7;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.monthly-card h3 {
  margin: 0 0 10px;
  font-size: 14px;
}
.monthly-card > div {
  display: grid;
  gap: 8px;
}
.monthly-card span {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px solid #e0e7e2;
}
.monthly-card small {
  color: var(--muted);
  font-weight: 900;
}
.monthly-card strong {
  color: var(--ink);
  text-align: right;
}
.daily-bi-history {
  margin-top: 18px;
}
.daily-bi-history-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}
.daily-bi-history-grid .history-chart-card {
  min-height: 300px;
  padding: 16px;
}
.daily-bi-history-grid .trend-panel-title h3 {
  font-size: 16px;
}
.daily-bi-history-grid .history-card-head {
  grid-template-columns: minmax(0, 1fr);
  gap: 8px;
  padding-bottom: 10px;
}
.daily-bi-history-grid .trend-panel-value {
  text-align: left;
}
.daily-bi-history-grid .trend-panel-value strong {
  margin: 2px 0 0;
  font-size: 20px;
}
.daily-bi-chart {
  min-height: 220px;
}
.daily-bi-chart svg {
  min-height: 204px;
}
.daily-bi-chart .chart-point {
  opacity: 0;
  animation: chart-point-pop 0.28s ease-out forwards;
}
.daily-bi-monthly-comparison {
  margin-top: 20px;
}
.daily-bi-month-card {
  display: grid;
  gap: 14px;
  background: #ffffff;
  border-top: 4px solid var(--teal);
  box-shadow: var(--shadow);
}
.daily-bi-month-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 4px 12px;
  align-items: start;
}
.daily-bi-month-head span,
.daily-bi-month-head small {
  color: var(--muted);
  font-size: 12px;
  font-weight: 900;
  line-height: 1.3;
}
.daily-bi-month-head h3 {
  grid-column: 1;
  margin: 0;
  font-size: 18px;
  line-height: 1.2;
}
.daily-bi-month-head small {
  grid-column: 2;
  grid-row: 1 / span 2;
  align-self: center;
}
.daily-bi-month-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 14px;
}
.daily-bi-month-metrics span {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
  padding-top: 8px;
  border-top: 1px solid #e0e7e2;
}
.daily-bi-month-metrics small {
  color: var(--muted);
  font-weight: 900;
}
.daily-bi-month-metrics strong {
  color: var(--ink);
  text-align: right;
  overflow-wrap: anywhere;
}
@keyframes chart-draw {
  to {
    stroke-dashoffset: 0;
  }
}
@keyframes chart-point-pop {
  from {
    opacity: 0;
    transform: scale(0.6);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
.model-compare-card {
  border-top: 6px solid var(--blue);
}
.model-compare-card:nth-child(2) {
  border-top-color: var(--green);
}
.model-compare-card h3,
.account-card h3,
.anchor-card h3,
.seed-card h3 {
  margin-bottom: 0;
  font-size: 20px;
}
.compare-primary {
  margin: 18px 0;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--line);
}
.compare-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.compare-metrics span {
  display: block;
  min-height: 78px;
  padding: 12px;
  background: #f7faf7;
  border: 1px solid var(--line);
}
.compare-metrics small {
  display: block;
  margin-bottom: 8px;
  color: var(--muted);
  font-weight: 900;
}
.compare-metrics strong {
  font-family: "DIN Alternate", "Avenir Next Condensed", "PingFang SC", sans-serif;
  font-size: 20px;
  overflow-wrap: anywhere;
}
.segment-trend-pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}
.account-summary-card {
  border-left: 6px solid var(--blue);
}
.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  min-height: 50px;
}
.card-title-row p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.45;
}
.anchor-parent-scope {
  display: -webkit-box;
  max-width: 100%;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  border-radius: var(--radius-control);
}
.card-measure {
  margin-top: 18px;
}
.metric-group {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}
.metric-group h4 {
  margin: 0 0 10px;
  color: var(--ink);
  font-size: 13px;
}
.metric-group > div {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.metric-group span {
  min-width: 0;
  padding: 10px;
  background: #f7faf7;
  border: 1px solid var(--line);
  border-radius: 6px;
}
.metric-group small {
  display: block;
  color: var(--muted);
  font-size: 11px;
  font-weight: 900;
  line-height: 1.35;
}
.metric-group strong {
  display: block;
  margin-top: 6px;
  color: var(--ink);
  font-size: 16px;
  line-height: 1.2;
  overflow-wrap: anywhere;
}
.metric-status-note {
  display: block;
  margin-top: 6px;
  color: var(--muted);
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
.signal {
  flex: 0 0 auto;
  padding: 5px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 900;
}
.signal.good {
  color: var(--green);
  background: #e5f1e9;
}
.signal.watch {
  color: var(--amber);
  background: var(--soft-amber);
}
.signal.neutral {
  color: var(--blue);
  background: #e8eef7;
}
.anchor-card {
  border-top: 5px solid var(--green);
}
.seed-account-slot {
  margin-bottom: 14px;
}
.seed-card {
  border-top: 5px solid var(--teal);
}
.seed-account-card {
  border-top-color: var(--blue);
}
.seed-type-chip {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  margin-top: 8px;
  padding: 4px 8px;
  color: var(--color-focus);
  background: var(--soft-teal);
  border: 1px solid rgba(4, 123, 117, 0.24);
  border-radius: var(--radius-control);
  font-size: var(--font-size-caption);
  font-weight: 900;
  line-height: 1.2;
}
.seed-parent-scope {
  display: -webkit-box;
  max-width: 100%;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  border-radius: var(--radius-control);
}
.seed-trend-block {
  margin-top: 14px;
}
.seed-trend-group > .seed-trend-block {
  margin-top: 0;
}
.seed-trend-group .mini-trend-block {
  margin-top: 0;
}
.business-footnote {
  padding: 20px 42px 36px;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
}
.business-footnote details {
  max-width: 980px;
  margin: 0 auto;
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}
.business-footnote summary {
  cursor: pointer;
  color: var(--color-text);
  font-weight: 900;
}
.business-footnote p {
  margin: var(--space-2) 0 0;
  line-height: 1.7;
  text-align: left;
}
@media (max-width: 960px) {
  .topbar, .section-head, .segment-layout, .decision-board { display: block; }
  .topbar { padding: 26px 18px 20px; }
  .dashboard-meta { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  body[data-dashboard-mode="trend"] .dashboard-meta { grid-template-columns: repeat(2, minmax(0, 1fr)); }
	  .date-input-group,
	  .quick-range-groups { grid-template-columns: repeat(2, minmax(0, 1fr)); }
	  .account-toolbar,
	  .anchor-toolbar,
	  .seed-toolbar { grid-template-columns: repeat(2, minmax(0, 1fr)); }
	  .account-filter-control,
	  .account-filter-summary,
	  .anchor-filter-control,
	  .anchor-filter-summary,
	  .seed-filter-control,
	  .seed-filter-summary { grid-column: 1 / -1; }
	  .date-input-group > button,
	  .range-message { grid-column: 1 / -1; }
  .topbar-tools { display: grid; grid-template-columns: 1fr; margin-top: 18px; }
  body[data-dashboard-mode="business"] .topbar-tools { min-width: 0; grid-template-columns: 1fr; }
  .business-range-fields { grid-template-columns: 1fr; }
  .business-range-fields button { width: 100%; }
  .source-pill,
  .trend-boundary-card { margin-top: 18px; min-width: 0; max-width: none; }
  .nav { padding: 0 12px; overflow-x: auto; }
  .section { padding: 26px 18px 16px; }
  .metric-grid, .delta-grid, .decision-kpi-grid, .trend-status-strip, .kpi-card-grid, .business-card-list, .history-chart-grid, .monthly-grid, .account-featured-trend-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .model-compare-grid { grid-template-columns: 1fr; }
  .business-home .decision-kpi-grid,
  .workbench-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .decision-side { margin-top: 14px; }
  .segment-panel { margin-bottom: 14px; }
  .segment-panel ul { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .table-actions { display: block; }
  .table-search { margin-top: 14px; }
  .sort-controls { justify-content: flex-start; margin-top: 14px; }
  .funnel-row { grid-template-columns: 34px minmax(0, 1fr); }
  .funnel-value, .funnel-conversion { text-align: left; }
}
@media (max-width: 560px) {
  h1 { font-size: 26px; }
  .dashboard-meta { grid-template-columns: 1fr; }
	  body[data-dashboard-mode="trend"] .dashboard-meta { grid-template-columns: 1fr; }
	  .date-input-group,
	  .quick-range-groups,
	  .account-toolbar,
	  .anchor-toolbar,
	  .seed-toolbar,
	  .metric-grid, .delta-grid, .decision-kpi-grid, .trend-status-strip, .kpi-card-grid, .model-compare-grid, .business-card-list, .compare-metrics, .history-chart-grid, .monthly-grid, .metric-group > div, .segment-trend-pair, .account-card-topline, .account-featured-trend-grid, .account-summary-grid, .anchor-summary-grid, .seed-summary-grid { grid-template-columns: 1fr; }
  .business-home .decision-kpi-grid,
  .workbench-grid { grid-template-columns: 1fr; }
  .metric-value { font-size: 28px; }
  .decision-title-row { display: block; }
  .readonly-badge { display: inline-block; margin-top: 10px; }
  .status-row { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
"""


_JS = """
function sortTable(tableId, key, direction) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const tbody = table.querySelector("tbody");
  const rows = Array.from(tbody.querySelectorAll("tr"));
  const multiplier = direction === "asc" ? 1 : -1;
  rows.sort((a, b) => {
    const av = Number(a.dataset[key] || 0);
    const bv = Number(b.dataset[key] || 0);
    return (av - bv) * multiplier;
  });
  rows.forEach((row) => tbody.appendChild(row));
}

document.querySelectorAll("[data-sort-table]").forEach((button) => {
  button.addEventListener("click", () => {
    sortTable(button.dataset.sortTable, button.dataset.sortKey, button.dataset.sortDir || "desc");
    document.querySelectorAll(`[data-sort-table="${button.dataset.sortTable}"]`).forEach((peer) => {
      peer.classList.toggle("active-sort", peer === button);
    });
  });
});
"""


if __name__ == "__main__":
    raise SystemExit(main())
