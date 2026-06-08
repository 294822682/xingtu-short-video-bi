export function formatInteger(value) {
  return Number(value || 0).toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

export function formatBusinessNumber(value) {
  const number = Number(value || 0);
  if (Math.abs(number) >= 100000) {
    return `${Math.trunc(number / 10000)}万`;
  }
  return formatInteger(number);
}

export function formatRate(value, fallback = "未提供") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return fallback;
  return `${(Number(value) * 100).toFixed(1)}%`;
}
