function toNumber(value: number | string | undefined | null): number | null {
  if (value === undefined || value === null || value === '') return null;
  const numeric = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function formatNumber(value: number, decimals: number): string {
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function toWan(value: number | undefined): number {
  const numeric = toNumber(value);
  return numeric == null ? 0 : numeric / 10000;
}

export function formatYuan(value: number | string | undefined | null, decimals = 0): string {
  const numeric = toNumber(value);
  if (numeric == null) return '-';
  return formatNumber(numeric, decimals);
}

export function formatWan(value: number | string | undefined | null, decimals = 0): string {
  const numeric = toNumber(value);
  if (numeric == null) return '-';
  return formatNumber(numeric / 10000, decimals);
}

export function formatYi(value: number | string | undefined | null, decimals = 2): string {
  const numeric = toNumber(value);
  if (numeric == null) return '-';
  return formatNumber(numeric / 100000000, decimals);
}

export function formatPercent(value: number | string | undefined | null, decimals = 2): string {
  const numeric = toNumber(value);
  if (numeric == null) return '-';
  return `${formatNumber(numeric, decimals)}%`;
}

export function formatPp(value: number | string | undefined | null, decimals = 2): string {
  const numeric = toNumber(value);
  if (numeric == null) return '-';
  return `${formatNumber(numeric, decimals)}pp`;
}
