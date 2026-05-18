export type PeriodDimension = 'monthly' | 'quarterly' | 'cumulative' | 'custom';

export interface PeriodOption {
  label: string;
  value: string;
}

function normalizeMonth(period: string): string | null {
  const match = period.match(/^(\d{4})-(\d{2})$/);
  if (!match) return null;
  return `${match[1]}-${match[2]}`;
}

function parseMonth(period: string): { year: number; month: number } | null {
  const normalized = normalizeMonth(period);
  if (!normalized) return null;
  const [year, month] = normalized.split('-');
  return { year: Number(year), month: Number(month) };
}

export function normalizePeriodDimension(value?: string | null): PeriodDimension {
  if (value === 'weekly') return 'quarterly';
  if (value === 'yearly') return 'cumulative';
  if (value === 'quarterly' || value === 'cumulative' || value === 'custom') return value;
  return 'monthly';
}

export function formatMonthLabel(period: string): string {
  const parsed = parseMonth(period);
  if (!parsed) return period;
  return `${parsed.year}年${parsed.month}月`;
}

export function formatQuarterLabel(period: string): string {
  const match = period.match(/^(\d{4})-Q([1-4])$/);
  if (!match) return period;
  return `${match[1]}年Q${match[2]}`;
}

export function toQuarterValue(period: string): string {
  const parsed = parseMonth(period);
  if (!parsed) return period;
  return `${parsed.year}-Q${Math.ceil(parsed.month / 3)}`;
}

export function quarterEndMonth(quarter: string): string | undefined {
  const match = quarter.match(/^(\d{4})-Q([1-4])$/);
  if (!match) return undefined;
  const year = match[1];
  const quarterNumber = Number(match[2]);
  return `${year}-${String(quarterNumber * 3).padStart(2, '0')}`;
}

export function getDefaultPeriod(allPeriods: string[], periodDimension: PeriodDimension): string | undefined {
  const normalized = [...new Set(allPeriods)]
    .map((item) => normalizeMonth(item))
    .filter((item): item is string => Boolean(item))
    .sort();
  const latest = normalized[normalized.length - 1];
  if (!latest) return undefined;
  if (periodDimension === 'quarterly') return toQuarterValue(latest);
  return latest;
}

export function buildPeriodOptions(allPeriods: string[], periodDimension: PeriodDimension): PeriodOption[] {
  const normalized = [...new Set(allPeriods)]
    .map((item) => normalizeMonth(item))
    .filter((item): item is string => Boolean(item))
    .sort()
    .reverse();

  if (periodDimension === 'quarterly') {
    return [...new Set(normalized.map((item) => toQuarterValue(item)))]
      .map((value) => ({ value, label: formatQuarterLabel(value) }));
  }

  if (periodDimension === 'cumulative') {
    return normalized.map((value) => ({ value, label: `${formatMonthLabel(value)}累计` }));
  }

  return normalized.map((value) => ({ value, label: formatMonthLabel(value) }));
}

export function formatMonthValue(dateLike: any): string {
  if (!dateLike) return '';
  const year = typeof dateLike.year === 'function' ? dateLike.year() : dateLike.getFullYear();
  const rawMonth = typeof dateLike.month === 'function' ? dateLike.month() + 1 : dateLike.getMonth() + 1;
  return `${year}-${String(rawMonth).padStart(2, '0')}`;
}

export function getComparePeriod(
  period: string | undefined,
  compareBase: string,
  periodDimension: PeriodDimension,
): string | undefined {
  if (!period) return undefined;

  if (periodDimension === 'quarterly') {
    const match = period.match(/^(\d{4})-Q([1-4])$/);
    if (!match) return undefined;
    const year = Number(match[1]);
    const quarter = Number(match[2]);
    if (compareBase === 'yoy') return `${year - 1}-Q${quarter}`;
    if (compareBase === 'mom') {
      if (quarter === 1) return `${year - 1}-Q4`;
      return `${year}-Q${quarter - 1}`;
    }
    return undefined;
  }

  const parsed = parseMonth(period);
  if (!parsed) return undefined;

  if (compareBase === 'yoy') {
    return `${parsed.year - 1}-${String(parsed.month).padStart(2, '0')}`;
  }

  if (compareBase === 'mom') {
    if (periodDimension === 'cumulative') {
      if (parsed.month === 1) return `${parsed.year - 1}-12`;
      return `${parsed.year}-${String(parsed.month - 1).padStart(2, '0')}`;
    }
    if (parsed.month === 1) return `${parsed.year - 1}-12`;
    return `${parsed.year}-${String(parsed.month - 1).padStart(2, '0')}`;
  }

  return undefined;
}
