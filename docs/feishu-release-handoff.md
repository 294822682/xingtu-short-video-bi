# 飞书上线交接清单

## 当前结论

当前项目已经具备飞书内嵌所需的本地生产形态：前端和后端同源、上传刷新可持久化、口径验证脚本可复跑。代码已推送到 GitHub 私有仓库。还不能直接内嵌飞书的唯一缺口是没有正式 HTTPS 域名。

当前 GitHub 私有仓库：

```text
https://github.com/294822682/xingtu-short-video-bi
```

Render Blueprint 入口：

```text
https://render.com/deploy?repo=https://github.com/294822682/xingtu-short-video-bi
```

## 已固定的生产入口

- `/`：浅色企业 BI 总览页
- `/admin`：手动上传或替换 Excel
- `/api/health`：健康检查
- `/api/short-video/overview`：看板数据
- `/api/admin/upload`：上传刷新

生产环境使用单服务同源部署，飞书只需要配置一个 HTTPS 地址，例如：

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

这一步通过后，才适合去 Render 创建服务。

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

1. 打开 Render Blueprint 入口。
2. 登录 Render，并授权 Render 访问 GitHub 私有仓库 `294822682/xingtu-short-video-bi`。
3. Render 会读取 `render.yaml`，创建 Docker Web Service。
4. 确认服务包含 persistent disk：
   - disk name: `xingtu-short-video-bi-data`
   - mount path: `/data`
   - size: `1GB`
5. 确认环境变量：
   - `XINGTU_DATA_DIR=/data/current`
6. 等待部署完成，记录 Render 分配的 HTTPS URL。

注意：上传后的 Excel 计算结果依赖 persistent disk。不要改成无磁盘或临时文件存储。

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

## 下一步授权点

如果需要我继续代执行线上部署，需要明确授权：

1. 初始化 Git 仓库、创建提交。
2. 创建 GitHub 远端仓库并推送。
3. 使用 Render Dashboard 或可用的 Render 凭证创建服务。

没有这三项授权前，当前阶段应停在本地生产验收和上线交接清单。
