# 飞书内嵌部署方案

## 目标

把当前本地 BI 固定成一个可放入飞书网页应用的稳定 HTTPS 入口。生产环境只暴露一个站点：

- `/`：BI 总览
- `/admin`：手动上传或替换 Excel
- `/api/health`：健康检查
- `/api/short-video/overview`：看板数据
- `/api/admin/upload`：上传刷新

## 当前线上入口

当前已创建 Render Free Web Service：

- Service: `xingtu-short-video-bi`
- Service ID: `srv-d8jab01kh4rs73dfrnig`
- Dashboard: `https://dashboard.render.com/web/srv-d8jab01kh4rs73dfrnig`
- Public URL: `https://xingtu-short-video-bi.onrender.com/`
- Admin URL: `https://xingtu-short-video-bi.onrender.com/admin`
- GitHub repo: `https://github.com/294822682/xingtu-short-video-bi`

当前服务用于飞书内嵌验收已经足够：HTTPS、同源 API、上传刷新、iframe 响应头和 iframe DOM 渲染均已通过脚本检查。

限制：当前服务是 Render Free Web Service，未挂载 persistent disk。上传后的数据在当前实例内可刷新展示，但实例重启或重新部署后可能回到默认数据，需要重新上传 Excel。若要作为长期生产入口，应升级到带 persistent disk 的 Render Blueprint 配置。

上传 Excel 使用轻量 `openpyxl` 读取，并会重置不可信的 sheet 维度元数据来识别 WPS/Excel 的可见行；如果上传解析不到有效视频行，接口会返回 422 并保留当前数据。

## 推荐架构

首版采用单服务同源部署：

1. Vite 构建前端到 `dist/`。
2. FastAPI 同时服务 `/api/*` 和 `dist/` 静态文件。
3. 飞书只内嵌一个 HTTPS URL，例如 `https://xingtu-short-video-bi.onrender.com/`。
4. 上传后的数据写入 `XINGTU_DATA_DIR/dataset.json`。

这样可以避免飞书 iframe 内的跨域、混合内容和 API 域名不一致问题。

## Render 部署

当前项目已提供：

- `Dockerfile`
- `.dockerignore`
- `render.yaml`
- `scripts/preflight_deploy.py`
- `scripts/verify_feishu_deploy.py`

当前线上服务使用 CLI 直接创建：

```bash
render services create \
  --name xingtu-short-video-bi \
  --type web_service \
  --repo https://github.com/294822682/xingtu-short-video-bi \
  --branch main \
  --runtime docker \
  --plan free \
  --health-check-path /api/health \
  --env-var XINGTU_DATA_DIR=/tmp/xingtu-data \
  --auto-deploy \
  --confirm \
  -o json
```

长期生产建议使用 `render.yaml` Blueprint，挂载 1GB persistent disk 到 `/data`，并设置 `XINGTU_DATA_DIR=/data/current`。

前置条件：

1. 将本目录放入一个 Git 仓库并推送到 GitHub/GitLab/Bitbucket。
2. 在 Render 中通过 Blueprint 导入该仓库。
3. Render 会按 `render.yaml` 创建 Docker Web Service，并挂载 1GB persistent disk 到 `/data`。

注意：Render persistent disk 需要付费 Web Service。`render.yaml` 未显式指定 `plan` 时，新 Web Service 会使用 Render 的默认 `starter` 实例；如果改成免费实例，上传后的本地文件会在重启或重新部署后丢失。

Render 环境变量：

- `XINGTU_DATA_DIR=/data/current`
- `PORT` 由 Render 自动提供，Docker CMD 会读取。

部署成功后，用 Render 分配的 HTTPS 域名作为飞书网页应用地址。

部署前本地检查：

```bash
.venv/bin/python scripts/preflight_deploy.py
```

推送到 Git 远端后，检查 Render Blueprint 所需的 Git 条件：

```bash
.venv/bin/python scripts/preflight_deploy.py --require-git
```

## 本地生产形态验证

```bash
npm run build
XINGTU_DATA_DIR="$(mktemp -d)" .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8020
```

另开终端验证：

```bash
curl http://127.0.0.1:8020/api/health
curl http://127.0.0.1:8020/
curl http://127.0.0.1:8020/admin
```

预期：

- `/api/health` 返回 `{"status":"ok"}`
- `/` 返回 BI 页面 HTML
- `/admin` 返回同一个前端应用，由 React 路由显示数据维护页

## 部署后自动验收

部署完成并拿到 HTTPS 地址后，先做只读检查：

```bash
.venv/bin/python scripts/verify_feishu_deploy.py https://<your-bi-domain>
```

这一步会检查：

- `/api/health` 是否正常。
- `/` 和 `/admin` 是否返回生产 HTML。
- 前端资源是否使用 `/assets/...` 路径。
- 首页和维护页是否没有 `X-Frame-Options` 或限制性的 `frame-ancestors`，避免飞书 iframe 被浏览器拦截。
- `/api/short-video/overview` 是否仍包含账号、演员和视频 Top/Bot 合同字段。

再在验收环境做上传刷新检查：

```bash
.venv/bin/python scripts/verify_feishu_deploy.py https://<your-bi-domain> --upload
```

注意：`--upload` 会上传一份临时生成的测试 Excel，并把当前 BI 数据刷新为测试数据。只在测试环境、首次部署验收或明确允许覆盖当前数据时执行。

如果当前环境有 Playwright 和本机 Chrome，还可以做真实 iframe DOM 渲染检查：

```bash
node scripts/verify_feishu_iframe_render.cjs https://<your-bi-domain>
```

这一步会把首页和 `/admin` 分别放进一个模拟飞书网页应用的 iframe，确认 iframe 内能渲染 React root，并出现 `星途短视频经营 BI` 和 `上传或替换 Excel`。

也可以使用一键验收脚本串行执行上述检查：

```bash
scripts/verify_feishu_acceptance.sh https://<your-bi-domain>
scripts/verify_feishu_acceptance.sh https://<your-bi-domain> --upload
```

当前正式 URL 的验收命令：

```bash
PYTHON_BIN=.venv/bin/python \
NODE_BIN=/Users/ahs/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node \
NODE_PATH=/Users/ahs/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules \
scripts/verify_feishu_acceptance.sh https://xingtu-short-video-bi.onrender.com --upload
```

## 飞书内嵌验收清单

- 首页能在飞书 iframe 中加载，不跳空白页。
- `/admin` 能打开，并显示上传 Excel 表单。
- 部署验证脚本返回 `iframe_headers: ok`。
- 如环境支持，iframe 渲染脚本返回 `iframe_dom: ok`。
- 上传 Excel 后，总发布条数、总曝光量、5S 完播率、账号表、演员表刷新。
- 总曝光量等大于五位数的数值按 `万` 展示。
- 视频号没有 5S 完播率时仍显示 `未提供`。
- 多人演员贡献曝光量不平摊。
- Top1/Bot1 是单条视频标题维度，按曝光量排序。
- 页面不展示 sheet、字段来源、fallback、缺失字段等技术解释。
- 飞书窄宽度下无页面级横向滚动，表格横向滚动只发生在表格容器内。
- 刷新页面后仍能读取最近一次上传结果。
