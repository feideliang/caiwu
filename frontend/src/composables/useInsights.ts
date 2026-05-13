import { computed, type ComputedRef } from 'vue';
import type { BreakdownItem, CoreMetricsSummary, TrendDataPoint } from '@/types/metrics';
import type { RouteLocationRaw } from 'vue-router';

export interface InlineInsight {
  title: string;
  calculation: string;
  type: 'positive' | 'negative' | 'neutral' | 'warning';
  route?: RouteLocationRaw;
}

const DIM_LABELS: Record<string, string> = { department: '部门', product_line: '产品线', company: '公司' };

function wan(v: number | undefined | null): string {
  if (v == null) return '0.0';
  return (v / 10000).toFixed(1);
}

export function useInlineInsights(opts: {
  dimension: 'department' | 'product_line' | 'company';
  breakdowns: ComputedRef<BreakdownItem[]>;
  summary: ComputedRef<CoreMetricsSummary | undefined>;
  trendSeries?: ComputedRef<TrendDataPoint[]>;
  maxCount?: number;
}): ComputedRef<InlineInsight[]> {
  const { dimension, breakdowns, summary, trendSeries, maxCount = 5 } = opts;
  const dim = DIM_LABELS[dimension] || '维度';

  return computed(() => {
    const items: InlineInsight[] = [];
    const data = breakdowns.value;
    const s = summary.value;

    if (!data?.length && dimension !== 'company') return items;

    if (dimension !== 'company' && data.length > 0) {
      // 1. Top revenue
      const byRev = [...data].sort((a, b) => (b.revenue || 0) - (a.revenue || 0));
      const top = byRev[0];
      if (top?.revenue != null) {
        items.push({
          title: `${top.dimension_value}${dim}领跑全公司 ${wan(top.revenue)}万`,
          calculation: `计算方式：按各${dim}的 revenue 字段降序排列取最高值。${top.dimension_value} 的 revenue = ${top.revenue} 元 = ${wan(top.revenue)} 万元`,
          type: 'positive',
          route: { path: dimension === 'department' ? '/department-analysis' : '/product-analysis', query: { entity: top.dimension_value } },
        });
      }

      // 2. Best margin
      const byMar = [...data].sort((a, b) => (b.gross_margin || 0) - (a.gross_margin || 0));
      const best = byMar[0];
      if (best?.gross_margin != null) {
        items.push({
          title: `${best.dimension_value}${dim}毛利率最优 ${best.gross_margin.toFixed(1)}%`,
          calculation: `计算方式：按各${dim}的 gross_margin 字段降序排列取最高值。${best.dimension_value} 的 gross_margin = ${best.gross_margin.toFixed(2)}%`,
          type: best.gross_margin >= 30 ? 'positive' : 'neutral',
          route: { path: dimension === 'department' ? '/department-analysis' : '/product-analysis', query: { entity: best.dimension_value } },
        });
      }

      // 3. Declining count
      const declining = data.filter((d) => (d.revenue_yoy_growth ?? 0) < 0).length;
      items.push({
        title: `${declining}个${dim}收入同比下滑`,
        calculation: `计算方式：统计各${dim}的 revenue_yoy_growth 字段 < 0 的数量。共 ${data.length} 个${dim}，其中 ${declining} 个同比负增长`,
        type: declining === 0 ? 'positive' : declining > data.length * 0.5 ? 'negative' : 'warning',
        route: { path: dimension === 'department' ? '/department-analysis' : '/product-analysis' },
      });

      // 4. Negative margin (only if exists)
      const worst = byMar[byMar.length - 1];
      if (worst?.gross_margin != null && worst.gross_margin < 0) {
        items.push({
          title: `${worst.dimension_value}${dim}毛利率为负 ${worst.gross_margin.toFixed(1)}%`,
          calculation: `计算方式：按各${dim}的 gross_margin 字段升序排列取最低值。${worst.dimension_value} 的 gross_margin = ${worst.gross_margin.toFixed(2)}%`,
          type: 'negative',
          route: { path: dimension === 'department' ? '/analysis/department' : '/analysis/product', query: { entity: worst.dimension_value } },
        });
      }

      // 5. Fastest growth
      const byGrw = [...data].sort((a, b) => (b.revenue_yoy_growth ?? 0) - (a.revenue_yoy_growth ?? 0));
      const fast = byGrw[0];
      if (fast && (fast.revenue_yoy_growth ?? 0) > 0) {
        items.push({
          title: `${fast.dimension_value}${dim}增速最快 ${(fast.revenue_yoy_growth ?? 0).toFixed(1)}%`,
          calculation: `计算方式：按各${dim}的 revenue_yoy_growth 字段降序排列取最高值。${fast.dimension_value} 的 revenue_yoy_growth = ${(fast.revenue_yoy_growth ?? 0).toFixed(2)}%`,
          type: 'positive',
          route: { path: dimension === 'department' ? '/analysis/department' : '/analysis/product', query: { entity: fast.dimension_value } },
        });
      }
    }

    // Company-level insights
    if (dimension === 'company') {
      if (s) {
        if (s.revenue != null) {
          items.push({
            title: `公司累计收入 ${wan(s.revenue)} 万元`,
            calculation: `计算方式：取自 summary.revenue = ${s.revenue} 元，转换为万元为 ${wan(s.revenue)}`,
            type: 'neutral',
            route: { path: '/trend-analysis' },
          });
        }
        if (s.gross_margin != null) {
          items.push({
            title: `公司整体毛利率 ${s.gross_margin.toFixed(1)}%`,
            calculation: `计算方式：取自 summary.gross_margin = ${s.gross_margin.toFixed(2)}%`,
            type: s.gross_margin >= 20 ? 'positive' : s.gross_margin >= 0 ? 'warning' : 'negative',
            route: { path: '/trend-analysis' },
          });
        }
        if (s.revenue_yoy_growth != null) {
          items.push({
            title: `收入同比${s.revenue_yoy_growth >= 0 ? '增长' : '下滑'} ${Math.abs(s.revenue_yoy_growth).toFixed(1)}%`,
            calculation: `计算方式：取自 summary.revenue_yoy_growth = ${s.revenue_yoy_growth.toFixed(2)}%`,
            type: s.revenue_yoy_growth >= 0 ? 'positive' : 'negative',
            route: { path: '/trend-analysis' },
          });
        }
      }

      const trends = trendSeries?.value || [];
      if (trends.length >= 2) {
        const first = trends[0];
        const last = trends[trends.length - 1];
        if (first.revenue != null && last.revenue != null && first.revenue > 0) {
          const g = ((last.revenue - first.revenue) / first.revenue * 100);
          items.push({
            title: `期间收入${g >= 0 ? '增长' : '下降'} ${g.toFixed(1)}%（${trends.length}期）`,
            calculation: `计算方式：(${last.revenue} - ${first.revenue}) / ${first.revenue} * 100 = ${g.toFixed(2)}%。统计区间：${first.period} 至 ${last.period}，共 ${trends.length} 期`,
            type: g >= 0 ? 'positive' : 'negative',
            route: { path: '/trend-analysis' },
          });
        }

        const peak = [...trends].sort((a, b) => (b.revenue || 0) - (a.revenue || 0))[0];
        if (peak) {
          items.push({
            title: `${peak.period} 收入达峰 ${wan(peak.revenue)} 万`,
            calculation: `计算方式：在 trend_series 中按 revenue 字段降序，取最高值所在期间。${peak.period} 的 revenue = ${peak.revenue} 元 = ${wan(peak.revenue)} 万元`,
            type: 'neutral',
            route: { path: '/trend-analysis' },
          });
        }

        const mPts = trends.filter((t) => t.gross_margin != null);
        if (mPts.length >= 2) {
          const mF = mPts[0];
          const mL = mPts[mPts.length - 1];
          const d = mL.gross_margin! - mF.gross_margin!;
          items.push({
            title: `毛利率${d >= 0 ? '提升' : '下降'} ${Math.abs(d).toFixed(1)} 个百分点`,
            calculation: `计算方式：末期 gross_margin (${mL.gross_margin?.toFixed(2)}%) - 初期 gross_margin (${mF.gross_margin?.toFixed(2)}%) = ${d.toFixed(2)} 个百分点`,
            type: d >= 0 ? 'positive' : 'negative',
            route: { path: '/trend-analysis' },
          });
        }
      }
    }

    return items.slice(0, maxCount);
  });
}
