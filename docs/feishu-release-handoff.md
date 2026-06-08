# 飞书上线交接清单

## 当前结论

当前项目已经部署到 Render，并具备飞书内嵌验收所需的稳定 HTTPS 入口：前端和后端同源、上传刷新可用、iframe 响应头未阻断、iframe DOM 可渲染、口径验证脚本可复跑。

当前 GitHub 仓库：

```text
https://github.com/294822682/xingtu-short-video-bi
```

当前 Render 服务：

```text
https://dashboard.render.com/web/srv-d8jab01kh4rs73dfrnig
```

当前飞书可内嵌入口：

```text
https://xingtu-short-video-bi.onrender.com/
```

当前数据维护入口：

```text
https://xingtu-short-video-bi.onrender.com/admin
```

注意：当前服务是 Render Free Web Service，未挂载 persistent disk。上传后的数据可立即刷新展示，但服务重启或重新部署后可能需要重新上传 Excel。长期生产入口建议升级到 `render.yaml` 中的 persistent disk Blueprint 配置。

## 已固定的生产入口

- `/`：浅色企业 BI 总览页
- `/admin`：手动上传或替换 Excel
- `/api/health`：健康检查
- `/api/short-video/overview`：看板数据
- `/api/admin/upload`：上传刷新

生产环境使用单服务同源部署，飞书只需要配置一个 HTTPS 地址：

```text
https://xingtu-short-video-bi.onrender.com/
```

## 上线前本地检查

```bash
.venv/bin/python scripts/preflight_deploy.py
```

当前预期结果：

- `status` 为 `ok`
- 允许出现 `not-a-git-repository` 警告
- 前端测试通过
- 前端生产构建通过
- Python 测试通过
- 生产资源不引用 `127.0.0.1:8010`
- 部署验证脚本会检查 `X-Frame-Options` 和 `frame-ancestors`，防止飞书 iframe 被浏览器拦截

推到 Git 远端后再运行：

```bash
.venv/bin/python scripts/preflight_deploy.py --require-git
```

这一步通过后，才适合去 Render 创建或更新服务。

## 需要提交到仓库的文件

只提交源码、配置、文档和测试，不提交生成物。

```text
.dockerignore
.gitignore
.impeccable/live/config.json
AGENTS.md
DESIGN.md
Dockerfile
PRODUCT.md
README.md
app/__init__.py
app/default_data.py
app/main.py
app/metrics.py
app/storage.py
docs/feishu-deploy.md
docs/feishu-release-handoff.md
docs/page-spec.md
docs/superpowers/plans/2026-06-08-feishu-https-deploy.md
frontend/formatters.js
frontend/formatters.test.js
frontend/src/main.jsx
frontend/src/sampleData.js
frontend/src/styles.css
index.html
package-lock.json
package.json
render.yaml
requirements.txt
scripts/preflight_deploy.py
scripts/verify_feishu_acceptance.sh
scripts/verify_feishu_deploy.py
scripts/verify_feishu_iframe_render.cjs
tests/test_api.py
tests/test_metrics.py
tests/test_storage.py
tests/test_verify_feishu_deploy.py
vite.config.js
```

不要提交：

```text
node_modules/
dist/
.venv/
__pycache__/
.env
uploads/
data/current/
```

## Render 创建服务

当前已用 Render CLI 创建 Free Web Service：

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

如需长期生产持久化，使用 Render Blueprint 入口：

```text
https://render.com/deploy?repo=https://github.com/294822682/xingtu-short-video-bi
```

Blueprint 创建后确认服务包含 persistent disk：

   - disk name: `xingtu-short-video-bi-data`
   - mount path: `/data`
   - size: `1GB`

确认环境变量：

   - `XINGTU_DATA_DIR=/data/current`

长期生产环境中，上传后的 Excel 计算结果应依赖 persistent disk。当前 Free Web Service 只用于首版飞书内嵌和业务验收。

## 部署后验收

先做只读检查：

```bash
.venv/bin/python scripts/verify_feishu_deploy.py https://<your-bi-domain>
```

只读检查通过时会返回 `iframe_headers: ok`，表示首页和 `/admin` 没有明显 iframe 阻断响应头。

如果当前环境有 Playwright 和本机 Chrome，继续做 iframe DOM 渲染检查：

```bash
node scripts/verify_feishu_iframe_render.cjs https://<your-bi-domain>
```

通过时会返回 `iframe_dom: ok`，表示首页和 `/admin` 能在模拟 iframe 中渲染出核心内容。

也可以用一键验收脚本串行执行只读、上传和 iframe DOM 检查：

```bash
scripts/verify_feishu_acceptance.sh https://<your-bi-domain>
scripts/verify_feishu_acceptance.sh https://<your-bi-domain> --upload
```

当前正式 URL 已通过：

```bash
PYTHON_BIN=.venv/bin/python \
NODE_BIN=/Users/ahs/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node \
NODE_PATH=/Users/ahs/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules \
scripts/verify_feishu_acceptance.sh https://xingtu-short-video-bi.onrender.com --upload
```

验证结果：

- `health: ok`
- `home: ok`
- `admin: ok`
- `iframe_headers: ok`
- `overview_contract: ok`
- `upload_refresh: ok`
- `iframe_dom: ok`
- `total_video_count: 1`
- `total_exposure: 120000`
- `completion_5s_display: 23.0%`
- `actor_exposure_not_split: true`
- `video_rankings_are_video_title_level: true`

如果是首次部署验收环境，再做上传刷新检查：

```bash
.venv/bin/python scripts/verify_feishu_deploy.py https://<your-bi-domain> --upload
```

`--upload` 会把线上当前数据替换为测试 Excel 的计算结果，只能在验收环境或明确允许覆盖时执行。

## 飞书内嵌检查

在飞书中配置网页应用入口为线上 HTTPS 首页地址：

```text
https://<your-bi-domain>/
```

验收以下项目：

- 首页在飞书 iframe 内正常加载。
- `/admin` 能打开上传页。
- 部署验证脚本返回 `iframe_headers: ok`。
- 如环境支持，iframe 渲染脚本返回 `iframe_dom: ok`。
- 上传 Excel 后页面刷新，账号汇总和演员汇总同步更新。
- 大于五位数的曝光量按 `万` 展示。
- 视频号没有 `5S完播率` 时显示 `未提供`。
- 多人演员贡献曝光量不平摊。
- Top1/Bot1 是具体视频标题维度，按曝光量排序。
- 页面不展示 sheet、字段来源、fallback、缺失字段等技术解释。
- 窄宽度下页面无整体横向滚动，表格只在表格容器内横向滚动。
- 刷新飞书页面后仍读取最近一次上传结果。

## 下一步建议

把 `https://xingtu-short-video-bi.onrender.com/` 配置到飞书网页应用并做现场验收；若领导确认要长期使用，升级到带 persistent disk 的 Render Blueprint 服务。
