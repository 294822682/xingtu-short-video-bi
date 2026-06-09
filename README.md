# xingtu-short-video-bi

星途短视频经营 BI 独立网页应用，并预留为一个 Render Web Service 承载多个 BI 模块的 Hub。

首版目标：

- 把已验收的短视频数据 MVP 固定成浅色企业 BI 页面。
- 支持手动上传/替换 Excel 后重新生成数据。
- 通过飞书固定网页应用入口访问。
- 保持账号维度和演员维度两张核心汇总表口径稳定。

## BI Hub 路由

当前共用同一个 Render Web Service，不新建第二个 Render 服务。

- Hub 入口：`/hub`
- 星途短视频 BI：`/` 和 `/xingtu`
- 星途数据维护：`/admin` 和 `/admin/xingtu`
- OAE BI：`/oae`
- OAE 数据说明：`/admin/oae`

`/` 与 `/admin` 保持向后兼容，避免已配置的飞书网页应用入口失效。OAE 不使用星途短视频解析器，也不接收原始 Excel 上传；它读取 Operations Analytics Engine pipeline 已产出的 `feishu_dashboard_source_latest_*.tsv`。

## 当前口径

- 曝光量：底层字段为 `播放量`。
- 发布条数：有效视频行数量。
- 5S 完播率：只读取 `5S完播率` / `5s完播率` 等 5S 字段。
- 视频号无 5S 字段时显示 `未提供`，不使用普通 `完播率` 代替。
- 演员贡献曝光量不平摊。

## 技术栈

- Backend: FastAPI
- Frontend: React + Vite
- Charts: 轻量 SVG/CSS 首版实现，后续可替换 Recharts/ECharts

## 开发命令

后端：

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
uvicorn app.main:app --reload --port 8010
```

前端：

```bash
npm install
npm test
npm run build
npm run dev -- --host 127.0.0.1 --port 5174
```

本地入口：

- BI 页面：`http://127.0.0.1:5174`
- 数据维护：`http://127.0.0.1:5174/admin`
- API 健康检查：`http://127.0.0.1:8010/api/health`

## 生产部署

首版生产形态为单服务同源部署：FastAPI 同时提供 `/api/*` 和 Vite 构建后的前端静态文件，适合飞书 iframe 内嵌。该服务现在可作为 BI Hub 使用，用不同路由隔离不同 BI 模块。

当前已部署入口：

- BI 页面：https://xingtu-short-video-bi.onrender.com/
- BI Hub：https://xingtu-short-video-bi.onrender.com/hub
- OAE BI：https://xingtu-short-video-bi.onrender.com/oae
- 数据维护：https://xingtu-short-video-bi.onrender.com/admin
- Render Dashboard：https://dashboard.render.com/web/srv-d8jab01kh4rs73dfrnig

当前线上服务是 Render Free Web Service，使用公开 GitHub 仓库拉取 Dockerfile 部署。该免费服务未挂载 persistent disk，上传刷新可用，但服务重启或重新部署后需要重新上传 Excel。

上传 Excel 使用轻量 `openpyxl` 读取，并会重置不可信的 sheet 维度元数据来识别 WPS/Excel 的可见行。若上传解析不到有效视频行，接口会返回 422，不会把当前数据覆盖成 0。

项目已包含：

- `Dockerfile`
- `render.yaml`
- `docs/feishu-deploy.md`
- `scripts/verify_feishu_deploy.py`

`render.yaml` 保留为带 persistent disk 的正式生产 Blueprint 配置。启用后，上传刷新数据会写入 `XINGTU_DATA_DIR/dataset.json`，服务重启后仍可读取最近一次上传结果。OAE dashboard source TSV 默认打包在 `data/oae/sql_reports/`；如果设置 `OAE_DASHBOARD_SOURCE_DIR` 或在 `BI_DATA_DIR/oae/sql_reports/` 放入 TSV，会优先读取运行时数据。

GitHub 仓库：

- https://github.com/294822682/xingtu-short-video-bi

Render Blueprint 入口（用于创建带持久磁盘的正式生产服务）：

- https://render.com/deploy?repo=https://github.com/294822682/xingtu-short-video-bi

正式 URL 验收：

```bash
PYTHON_BIN=.venv/bin/python \
NODE_BIN=/Users/ahs/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node \
NODE_PATH=/Users/ahs/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules \
scripts/verify_feishu_acceptance.sh https://xingtu-short-video-bi.onrender.com --upload
```

部署前检查：

```bash
.venv/bin/python scripts/preflight_deploy.py
```

仓库推到 GitHub/GitLab/Bitbucket 后，再运行：

```bash
.venv/bin/python scripts/preflight_deploy.py --require-git
```

部署方案见 [docs/feishu-deploy.md](docs/feishu-deploy.md)，上线交接清单见 [docs/feishu-release-handoff.md](docs/feishu-release-handoff.md)。

## 规格

详见 [docs/page-spec.md](docs/page-spec.md)。
