import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { ArrowRight, BarChart3, Database, RefreshCw, TrendingDown, TrendingUp, UploadCloud } from "lucide-react";

import { BI_MODULES } from "./modules.js";
import { routeFromPath } from "./routing.js";
import { sampleDatasets } from "./sampleData.js";
import { formatBusinessNumber, formatInteger } from "../formatters.js";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE || (import.meta.env.PROD ? "" : "http://127.0.0.1:8010");
const PLATFORM_FILTERS = ["全部", "抖音", "视频号", "小红书"];

function App() {
  const route = routeFromPath(window.location.pathname);
  if (route.view === "hub") return <HubPage />;
  if (route.view === "admin") return <AdminPage module={route.module} />;
  return <DashboardPage module={route.module} />;
}

function HubPage() {
  useEffect(() => {
    document.title = "经营 BI Hub";
  }, []);

  return (
    <main className="app-shell">
      <header className="top-header">
        <div>
          <span className="eyebrow">OPERATIONS BI HUB</span>
          <h1>经营 BI Hub</h1>
        </div>
        <div className="header-meta">
          <span>共用一个 Render Web Service</span>
          <Badge text="模块隔离" tone="success" />
        </div>
      </header>
      <section className="hub-grid" aria-label="BI 模块入口">
        {BI_MODULES.map((module) => (
          <article className="hub-card" key={module.slug}>
            <div className="hub-icon">
              <Database size={22} />
            </div>
            <span className="eyebrow">{module.eyebrow}</span>
            <h2>{module.name}</h2>
            <p>{module.description}</p>
            <div className="hub-actions">
              <a className="admin-link primary" href={module.dashboardPath}>
                打开看板 <ArrowRight size={16} />
              </a>
              <a className="admin-link" href={module.adminPath}>数据维护</a>
            </div>
            <Badge text={module.uploadEnabled ? "已接入上传" : "待接入口径"} tone={module.uploadEnabled ? "success" : "warning"} />
          </article>
        ))}
      </section>
    </main>
  );
}

function DashboardPage({ module }) {
  const [dataset, setDataset] = useState(sampleDatasets[module.slug] || sampleDatasets.xingtu);
  const [status, setStatus] = useState("using-default");
  const [platform, setPlatform] = useState("全部");

  useEffect(() => {
    document.title = module.name;
  }, [module.name]);

  useEffect(() => {
    const controller = new AbortController();

    fetch(`${API_BASE}/api/bi/${module.slug}/overview`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("API unavailable");
        return response.json();
      })
      .then((payload) => {
        setDataset(payload);
        setStatus("live");
      })
      .catch((error) => {
        if (error.name !== "AbortError") setStatus("using-default");
      });

    return () => controller.abort();
  }, [module.slug]);

  const accountRows = useMemo(() => {
    if (platform === "全部") return dataset.account_metrics;
    return dataset.account_metrics.filter((row) => row.platform === platform);
  }, [dataset.account_metrics, platform]);
  const videoRankings = dataset.video_rankings || { top: null, bottom: null };

  const overview = dataset.overview;
  const isPending = overview.module_status === "pending_source_contract";

  return (
    <main className="app-shell">
      <Header dataset={dataset} status={status} module={module} />
      <nav className="tab-bar" aria-label="报表导航">
        <a href="/hub">BI Hub</a>
        <a href="#overview">总览驾驶舱</a>
        <a href="#rank">曝光榜单</a>
        <a href="#accounts">账号表现</a>
        <a href="#actors">演员表现</a>
      </nav>

      <section id="overview" className="hero-grid">
        <div className="overview-panel">
          <div className="section-label">经营总览</div>
          <h2>{module.name}</h2>
          <p>{module.description}</p>
        </div>
        {isPending ? <PendingPanel module={module} /> : <KpiGrid overview={overview} />}
      </section>

      {!isPending && (
        <>
          <section id="rank" className="rank-grid">
            <RankCard title="视频曝光 Top1" row={videoRankings.top} icon={<TrendingUp size={20} />} tone="top" />
            <RankCard title="视频曝光 Bot1" row={videoRankings.bottom} icon={<TrendingDown size={20} />} tone="bottom" />
          </section>

          <section className="chart-grid">
            <ChartPanel title="账号曝光排行" rows={accountRows.slice(0, 8)} labelKey="account_name" valueKey="exposure" />
            <ChartPanel title="演员拍摄排行" rows={dataset.actor_metrics.slice(0, 8)} labelKey="actor_name" valueKey="video_count" compact />
          </section>

          <section id="accounts" className="report-section">
            <SectionHeader title="账号表现" subtitle="按账号查看发布数量、曝光规模和演员参与情况。" />
            <div className="toolbar">
              {PLATFORM_FILTERS.map((item) => (
                <button
                  key={item}
                  type="button"
                  className={platform === item ? "active" : ""}
                  aria-pressed={platform === item}
                  onClick={() => setPlatform(item)}
                >
                  {item}
                </button>
              ))}
            </div>
            <div className="chart-grid secondary">
              <ChartPanel title="各账号发布条数" rows={accountRows} labelKey="account_name" valueKey="video_count" compact />
              <ChartPanel title="平均曝光对比" rows={accountRows} labelKey="account_name" valueKey="average_exposure" compact />
            </div>
            <AccountTable rows={accountRows} />
          </section>

          <section id="actors" className="report-section">
            <SectionHeader title="演员表现" subtitle="按演员查看拍摄条数、覆盖账号和带来的曝光表现。" />
            <div className="chart-grid secondary">
              <ChartPanel title="演员贡献曝光排行" rows={dataset.actor_metrics.slice(0, 8)} labelKey="actor_name" valueKey="contributed_exposure" />
              <ChartPanel title="参与账号数对比" rows={dataset.actor_metrics.slice(0, 8)} labelKey="actor_name" valueKey="account_count" compact />
            </div>
            <ActorTable rows={dataset.actor_metrics} />
          </section>
        </>
      )}
    </main>
  );
}

function Header({ dataset, status, module }) {
  const live = status === "live";
  return (
    <header className="top-header">
      <div>
        <span className="eyebrow">{module.eyebrow}</span>
        <h1>{module.name}</h1>
      </div>
      <div className="header-meta">
        <span>{dataset.overview.source_file_name}</span>
        <span>{dataset.overview.generated_at}</span>
        <Badge text={live ? "已刷新" : "样例数据"} tone={live ? "success" : "neutral"} />
        <a className="admin-link" href={module.adminPath}>数据维护</a>
      </div>
    </header>
  );
}

function PendingPanel({ module }) {
  return (
    <section className="pending-panel" aria-label={`${module.name} 待接入`}>
      <Badge text="待接入口径" tone="warning" />
      <h2>已预留独立入口，等待 OAE 数据源</h2>
      <p>{module.adminDescription}</p>
      <div className="pending-actions">
        <a className="admin-link primary" href={module.adminPath}>查看维护入口</a>
        <a className="admin-link" href="/hub">返回 BI Hub</a>
      </div>
    </section>
  );
}

function KpiGrid({ overview }) {
  const items = [
    { label: "总发布条数", value: formatInteger(overview.total_video_count), hint: "发布内容数" },
    { label: "总曝光量", value: formatBusinessNumber(overview.total_exposure), hint: "总播放规模", featured: true },
    { label: "整体 5S 完播率", value: overview.overall_5s_completion_rate_display, hint: "留存表现" },
    { label: "有演员视频条数", value: formatInteger(overview.actor_video_count), hint: "演员参与内容" },
    { label: "参与演员人数", value: formatInteger(overview.actor_count), hint: "参与内容生产" },
  ];
  return (
    <div className="kpi-grid">
      {items.map(({ label, value, hint, featured }) => (
        <article className={featured ? "kpi-card featured" : "kpi-card"} key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
          <small>{hint}</small>
        </article>
      ))}
    </div>
  );
}

function RankCard({ title, row, icon, tone }) {
  return (
    <article className={`rank-card ${tone}`} aria-label={title}>
      <div className="rank-heading">
        <span>{icon}</span>
        <strong>{title}</strong>
      </div>
      {row ? (
        <>
          <h3>{row.video_title}</h3>
          <div className="rank-value">{formatBusinessNumber(row.exposure)}</div>
          <dl>
            <div>
              <dt>平台</dt>
              <dd>{row.platform}</dd>
            </div>
            <div>
              <dt>账号</dt>
              <dd>{row.account_name}</dd>
            </div>
            <div>
              <dt>发布时间</dt>
              <dd>{row.publish_time || "未提供"}</dd>
            </div>
          </dl>
        </>
      ) : (
        <p>暂无数据</p>
      )}
    </article>
  );
}

function ChartPanel({ title, rows, labelKey, valueKey, compact = false }) {
  const max = Math.max(...rows.map((row) => Number(row[valueKey] || 0)), 1);
  return (
    <section className="panel" aria-label={title}>
      <div className="panel-title">
        <BarChart3 size={18} />
        <h3>{title}</h3>
      </div>
      <div className={compact ? "bars compact" : "bars"}>
        {rows.map((row) => {
          const value = Number(row[valueKey] || 0);
          const width = Math.max(2, (value / max) * 100);
          return (
            <div className="bar-row" key={`${title}-${row[labelKey]}`}>
              <span>{row[labelKey]}</span>
              <div className="bar-track">
                <i style={{ width: `${width}%` }} />
              </div>
              <b>{formatBusinessNumber(value)}</b>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function AccountTable({ rows }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>平台</th>
            <th>账号名称</th>
            <th>发布条数</th>
            <th>曝光量</th>
            <th>平均曝光</th>
            <th>5S 完播率</th>
            <th>有演员视频</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.account_name}>
              <td>{row.platform}</td>
              <td>{row.account_name}</td>
              <td>{formatInteger(row.video_count)}</td>
              <td>{formatBusinessNumber(row.exposure)}</td>
              <td>{formatBusinessNumber(row.average_exposure)}</td>
              <td>{row.completion_5s_display}</td>
              <td>{formatInteger(row.actor_video_count)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ActorTable({ rows }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>视频演员</th>
            <th>拍摄条数</th>
            <th>参与账号数</th>
            <th>贡献曝光量</th>
            <th>参与账号</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.actor_name}>
              <td>{row.actor_name}</td>
              <td>{formatInteger(row.video_count)}</td>
              <td>{formatInteger(row.account_count)}</td>
              <td>{formatBusinessNumber(row.contributed_exposure)}</td>
              <td>{row.accounts}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AdminPage({ module }) {
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState(
    module.uploadEnabled ? "选择 Excel 后上传，系统会重新生成 BI 数据。" : "该模块上传入口已预留，等待确认 OAE 报表字段口径。"
  );
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = `${module.shortName}数据维护`;
  }, [module.shortName]);

  async function handleUpload(event) {
    event.preventDefault();
    if (!module.uploadEnabled) {
      setMessage("OAE 解析口径尚未配置，不能套用星途短视频上传逻辑。");
      return;
    }
    if (!file) {
      setMessage("请先选择 .xlsx 文件。");
      return;
    }
    setBusy(true);
    const body = new FormData();
    body.append("file", file);
    try {
      const response = await fetch(`${API_BASE}/api/bi/${module.slug}/admin/upload`, { method: "POST", body });
      if (!response.ok) throw new Error(await response.text());
      const payload = await response.json();
      setMessage(`刷新完成：${payload.overview.total_video_count} 条视频，${formatBusinessNumber(payload.overview.total_exposure)} 曝光。`);
    } catch (error) {
      setMessage(`刷新失败：${error.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="app-shell admin-shell">
      <header className="top-header">
        <div>
          <span className="eyebrow">DATA MAINTENANCE</span>
          <h1>{module.shortName}数据维护</h1>
        </div>
        <a className="admin-link" href={module.dashboardPath}>返回 BI</a>
      </header>
      <section className="admin-panel">
        <UploadCloud size={34} />
        <h2>上传或替换 Excel</h2>
        <p>{module.adminDescription}</p>
        <form onSubmit={handleUpload} aria-busy={busy}>
          <label className="sr-only" htmlFor="excel-upload">选择 Excel 文件</label>
          <input id="excel-upload" type="file" accept=".xlsx" required disabled={!module.uploadEnabled} onChange={(event) => setFile(event.target.files?.[0] || null)} />
          <button type="submit" disabled={busy || !module.uploadEnabled}>
            {busy ? <RefreshCw size={16} className="spin" /> : <UploadCloud size={16} />}
            {busy ? "刷新中" : "上传并刷新"}
          </button>
        </form>
        <div className="admin-message" aria-live="polite">{message}</div>
      </section>
    </main>
  );
}

function SectionHeader({ title, subtitle }) {
  return (
    <div className="section-header">
      <h2>{title}</h2>
      <p>{subtitle}</p>
    </div>
  );
}

function Badge({ icon, text, tone = "neutral" }) {
  return (
    <span className={`badge ${tone}`}>
      {icon}
      {text}
    </span>
  );
}

createRoot(document.getElementById("root")).render(<App />);
