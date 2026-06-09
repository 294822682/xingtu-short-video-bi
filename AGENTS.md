默认用中文回复。当前仓库以星途短视频经营 BI 和 OAE 经营 BI 为已接入模块，并预留为多 BI Hub。OAE 只能读取 OAE pipeline 已产出的 dashboard source TSV，不得混用星途短视频数据口径。

工作边界：
- 首版采用浅色企业 BI，不做深色大屏。
- 数据口径以 `docs/page-spec.md` 为准。
- 原始 Excel 不允许被修改。
- 视频号没有 `5S完播率` 时显示 `未提供`，不得使用普通 `完播率` 代替。
- 多人演员贡献曝光量不平摊。
- 星途短视频刷新方式为手动上传/替换 Excel 后重新计算。
- OAE 刷新方式为先在 Operations Analytics Engine 仓库完成多源清洗、归因、导出，再同步 `feishu_dashboard_source_latest_*.tsv`。
- 飞书只是固定网页应用入口，首版不做复杂飞书 API 同步。
- `/` 与 `/admin` 保持星途入口兼容；新增 BI 模块必须使用独立路由、独立数据文件和独立上传或只读数据源口径。

工程纪律：
- 修改指标、API、数据结构或前端行为必须补测试。
- 不要使用 `git add .`。
- 不要默认 commit、tag、merge、push。
- 不要新增重型 BI 平台依赖。
