# xingtu-short-video-bi

星途短视频经营 BI 独立网页应用。

首版目标：

- 把已验收的短视频数据 MVP 固定成浅色企业 BI 页面。
- 支持手动上传/替换 Excel 后重新生成数据。
- 通过飞书固定网页应用入口访问。
- 保持账号维度和演员维度两张核心汇总表口径稳定。

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

首版生产形态为单服务同源部署：FastAPI 同时提供 `/api/*` 和 Vite 构建后的前端静态文件，适合飞书 iframe 内嵌。

当前已部署入口：

- BI 页面：https://xingtu-short-video-bi.onrender.com/
- 数据维护：https://xingtu-short-video-bi.onrender.com/admin
- Render Dashboard：https://dashboard.render.com/web/srv-d8jab01kh4rs73dfrnig

当前线上服务是 Render Free Web Service，使用公开 GitHub 仓库拉取 Dockerfile 部署。该免费服务未挂载 persistent disk，上传刷新可用，但服务重启或重新部署后需要重新上传 Excel。

项目已包含：

- `Dockerfile`
- `render.yaml`
- `docs/feishu-deploy.md`
- `scripts/verify_feishu_deploy.py`

`render.yaml` 保留为带 persistent disk 的正式生产 Blueprint 配置。启用后，上传刷新数据会写入 `XINGTU_DATA_DIR/dataset.json`，服务重启后仍可读取最近一次上传结果。

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
