/** Convert a value in 元 to 万元. */
export function toWan(value: number | undefined): number {
  if (value === undefined || value === null) return 0;
  return value / 10000;
}

/** Format a value in 万元 with comma separators and 2 decimal places. */
export function formatWan(value: number | undefined): string {
  if (value === undefined || value === null) return '-';
  return (value / 10000).toLocaleString('zh-CN', { maximumFractionDigits: 2, minimumFractionDigits: 2 });
}
