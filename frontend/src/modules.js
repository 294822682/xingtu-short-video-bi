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
    description: "面向 OAE 业务报表的独立 BI 入口，当前先完成 Render 共用和数据隔离。",
    adminDescription: "OAE 上传入口已预留。拿到 OAE 报表字段口径后，再接入对应解析器，避免套用星途短视频口径。",
    status: "pending_source_contract",
    uploadEnabled: false,
    dashboardPath: "/oae",
    adminPath: "/admin/oae",
  },
];

export const MODULE_BY_SLUG = Object.fromEntries(BI_MODULES.map((module) => [module.slug, module]));

export function moduleForSlug(slug) {
  return MODULE_BY_SLUG[slug] || MODULE_BY_SLUG.xingtu;
}
