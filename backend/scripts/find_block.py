with open('backend/app/api/ai.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The section to replace - from "if is_financial_question:" to the data_section assignment
old = '''            if is_financial_question:
                # Only inject dimension breakdowns when the question mentions them
                need_dept = any(kw in body.question for kw in ["部门", "销售", "CBG", "EBG", "TBU", "SBG"])
                need_prod = any(kw in body.question for kw in ["产品", "系列", "物料"])

                # Build concise data section
                data_lines = []
                k = kpis
                data_lines.append(f"营业收入: {(k.get('revenue') or 0):,.0f}元, 毛利率: {(k.get('gross_margin') or 0):.2f}%, 毛利额: {(k.get('gross_profit') or 0):,.0f}元")
                data_lines.append(f"达成率: {(k.get('achievement_rate') or 0):.2f}%, 收入环比: {(k.get('revenue_mom_growth') or 0):+.2f}%")
                if need_dept and dept_items:
                    data_lines.append("部门: " + ", ".join(f"{d['dimension_value']}收入{d.get('revenue') or 0:,.0f}毛利率{d.get('gross_margin') or 0:.2f}%" for d in dept_items[:5]))
                if need_prod and prod_items:
                    data_lines.append("产品: " + ", ".join(f"{d['dimension_value']}收入{d.get('revenue') or 0:,.0f}毛利率{d.get('gross_margin') or 0:.2f}%" for d in prod_items[:5]))
                data_section = "当前数据: " + "。".join(data_lines) + "。"'''

new = '''            if is_financial_question:
                    # Build concise data section with all available data
                    data_lines = []
                    k = kpis
                    rev = k.get('revenue') or 0
                    gp = k.get('gross_profit') or 0
                    gm = k.get('gross_margin') or 0
                    base_rev = k.get('base_revenue')
                    base_gp = k.get('base_gross_profit')
                    base_gm = k.get('base_gross_margin')
                    rev_yoy = k.get('revenue_yoy_growth')
                    gp_yoy = k.get('profit_yoy_growth')
                    gm_yoy_change = k.get('gross_margin_yoy_change')

                    data_lines.append(f"营业收入: {rev:,.0f}元, 毛利率: {gm:.2f}%, 毛利额: {gp:,.0f}元, 达成率: {(k.get('achievement_rate') or 0):.2f}%")
                    data_lines.append(f"收入环比: {(k.get('revenue_mom_growth') or 0):+.2f}%, 毛利环比: {(k.get('profit_mom_growth') or 0):+.2f}%")
                    if rev_yoy is not None:
                        data_lines.append(f"收入同比: {rev_yoy:+.2f}%, 毛利同比: {gp_yoy:+.2f}%")
                    if base_rev is not None:
                        data_lines.append(f"基期收入: {base_rev:,.0f}元, 基期毛利额: {base_gp:,.0f}元, 基期毛利率: {base_gm:.2f}%")
                    if gm_yoy_change is not None:
                        data_lines.append(f"毛利率同比变化: {gm_yoy_change:+.2f}个百分点")
                    if dept_items:
                        data_lines.append("部门: " + ", ".join(f"{d['dimension_value']}收入{d.get('revenue') or 0:,.0f}毛利率{d.get('gross_margin') or 0:.2f}%" for d in dept_items[:5]))
                    if prod_items:
                        data_lines.append("产品: " + ", ".join(f"{d['dimension_value']}收入{d.get('revenue') or 0:,.0f}毛利率{d.get('gross_margin') or 0:.2f}%" for d in prod_items[:5]))
                    data_section = "当前数据: " + "。".join(data_lines) + "。"
                    data_section += "\\n注意：请基于以上数据进行分析，不要编造数据。如果数据充分请给出具体分析，如果数据不足请说明具体缺少哪些维度的数据，避免笼统地说'无明细数据'。"'''

if old in content:
    print("Found exact match, replacing...")
    content = content.replace(old, new)
    with open('backend/app/api/ai.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Done!")
else:
    print("Exact match NOT found")
    # Try to find where it differs
    idx = content.find('is_financial_question')
    if idx >= 0:
        snippet = content[idx:idx+800]
        print("Content around is_financial_question:")
        print(repr(snippet[:500]))
    else:
        print("is_financial_question not found!")