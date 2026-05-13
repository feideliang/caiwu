# Implementation Plan: 交易分析组件 + Bug 修复

## Overview
Fix 3 bugs and build a new Transaction Analysis module with API layer, Pinia store, and components.

## Changes Overview

### Bug Fixes
1. **MobileDrawer.vue** — Capture emit ref, replace `props.open = false` with `emit('update:open', false)`
2. **AIChartRecommender.vue** — Fix broken HTML attribute quoting on line 67
3. **CorrelationAnalysis.vue** — Add missing `<style scoped lang="less">` block

### New Files
4. **src/api/transactions.ts** — API layer with typed interfaces + 6 endpoint functions
5. **src/store/transactions.ts** — Pinia store (contracts, orders, projects, anomalies, largeAmounts)
6. **src/components/analysis/AnomalyAlertList.vue** — Alert list with sigma-based coloring
7. **src/components/analysis/LargeAmountTable.vue** — Table with adjustable threshold
8. **src/components/analysis/TransactionAnalysis.vue** — Tabbed container

### Modified Files
9. **src/views/AnalysisPage.vue** — Replace a-empty placeholder with TransactionAnalysis

## Verification
- `npm run build` passes without TypeScript/build errors
- MobileDrawer no longer throws props mutation warning
- AIChartRecommender empty state shows correct Chinese text
- CorrelationAnalysis has scoped styles
