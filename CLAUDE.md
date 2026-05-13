# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI+BI 数智化财务管报系统 — Building an intelligent financial management reporting system that combines BI dashboards with AI-powered analysis, report generation, and predictive analytics.

**Key platforms involved:**
- BI平台: FineBI (ruijiebi.ruijie.com.cn) — data visualization and dashboards
- AI平台: ruijie.aiforce.cloud — AI capabilities (问答、报告生成、预测)
- ERP及内部系统: data sources for financial reporting
- Excel: supplementary data source

## Project Structure

```
/
├── CLAUDE.md          # This file — project guidance for Claude
├── rule.md            # Generic behavioral guidelines (merged below)
└── doc/
    └── 通过AI+BI构建数智化财务管报.docx  # Project requirements & architecture doc
```

## Architecture & Core Modules

The system has 6 core functional modules:

1. **AI智能可视化推荐** — AI recommends chart types and layouts based on data types; supports auto-layout for web/mobile/tablet
2. **多渠道数据源接入** — Data sources: BI平台, Excel上传, ERP, internal systems; priority: BI > ERP > 内部系统 > Excel
3. **数据清洗与校验** — AI-powered data cleaning (dedup, missing values, standardize口径), cross-validation with original data
4. **指标自动计算** — Auto-calculate financial KPIs (DSO, ITO, DPO, 毛利率, 净利率, 现金周转率), match industry benchmarks
5. **AI自动报告撰写** — Auto-generate financial reports (日报/周报/月报) with analysis, anomaly alerts, and recommendations; supports Word/PDF export
6. **前瞻预测** — Anomaly detection and predictive modeling for cash flow, AR aging, cost trends; forecast revenue/DSO/AR for next 3 months

## Behavioral Guidelines

### 1. Think Before Coding
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.

### 2. Simplicity First
- No features beyond what was asked.
- No abstractions for single-use code.
- No error handling for impossible scenarios.
- If 200 lines could be 50, rewrite it.

### 3. Surgical Changes
- Touch only what you must. Clean up only your own mess.
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- Remove imports/variables/functions that YOUR changes made unused.

### 4. Goal-Driven Execution
- Transform tasks into verifiable goals.
- For multi-step tasks, state a brief plan with verification steps.

## Key Documents

- `doc/通过AI+BI构建数智化财务管报.docx` — Contains detailed requirements, architecture decisions, and implementation priorities for all modules. Consult this before implementing any feature.
