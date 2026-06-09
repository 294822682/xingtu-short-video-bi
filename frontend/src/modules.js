export const BI_MODULES = [
  {
    slug: "xingtu",
    name: "星途短视频经营 BI",
    shortName: "星途短视频",
    eyebrow: "XINGTU SHORT VIDEO BI",
    description: "面向星途新媒体伙伴的数据可视化 BI，聚焦账号曝光、发布表现和演员贡献。",
    adminDescription: "上传或替换星途短视频 Excel 后，系统会重新生成账号维度、演员维度和 Top/Bot 视频榜单。",
    status: "ready",
    uploadEnabled: true,
    dashboardPath: "/xingtu",
    adminPath: "/admin/xingtu",
  },
  {
    slug: "oae",
    name: "OAE 经营 BI",
    shortName: "OAE",
    eyebrow: "OAE OPERATIONS BI",
    description: "面向 OAE 多源经营日报的独立 BI 入口，读取清洗归因后的 dashboard source 数据。",
    adminDescription: "OAE 数据由 Operations Analytics Engine pipeline 生成，本页只读展示最终 dashboard source，不接收原始 Excel 上传。",
    status: "ready",
    uploadEnabled: false,
    dashboardPath: "/oae",
    adminPath: "/admin/oae",
  },
];

export const MODULE_BY_SLUG = Object.fromEntries(BI_MODULES.map((module) => [module.slug, module]));

export function moduleForSlug(slug) {
  return MODULE_BY_SLUG[slug] || MODULE_BY_SLUG.xingtu;
}
