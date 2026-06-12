export function dashboardHeaderStatusText({ status }) {
  return status === "live" ? "当前数据已就绪" : "样例数据";
}
