# -*- coding: utf-8 -*-
import os
os.environ["PYTHONIOENCODING"] = "utf-8"
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    all_reqs = []
    def on_req(req):
        if "/api/v1/metrics/core" in req.url:
            qs = parse_qs(urlparse(req.url).query)
            all_reqs.append(qs)

    page.on("request", on_req)

    def gs():
        return page.evaluate("""() => {
            const w = (inst) => {
                if (!inst) return null;
                if (inst.setupState && inst.setupState.dimension !== undefined) return inst.setupState;
                if (inst.subTree) { const r = wv(inst.subTree); if (r) return r; }
                return null;
            };
            const wv = (v) => {
                if (!v) return null;
                if (v.component) {
                    if (v.component.setupState && v.component.setupState.dimension !== undefined) return v.component.setupState;
                    const r = w(v.component); if (r) return r;
                }
                if (v.children) {
                    for (const c of (Array.isArray(v.children) ? v.children : [v.children])) { const r = wv(c); if (r) return r; }
                }
                return null;
            };
            const s = w(document.querySelector('#app').__vue_app__._instance);
            if (!s || !s.dimension) return null;
            return { dim: s.dimension.value, entity: s.selectedEntity?.value, dept: s.departmentScope?.value, cross: s.crossDimension?.value };
        }""")

    def sv(n, v):
        return page.evaluate("""([n,v]) => {
            const w = (inst) => {
                if (!inst) return false;
                if (inst.setupState && inst.setupState[n] !== undefined) { inst.setupState[n].value = v; return true; }
                if (inst.subTree) { return wv(inst.subTree); }
                return false;
            };
            const wv = (vv) => {
                if (!vv) return false;
                if (vv.component) {
                    if (vv.component.setupState && vv.component.setupState[n] !== undefined) { vv.component.setupState[n].value = v; return true; }
                    const r = w(vv.component); if (r) return r;
                }
                if (vv.children) {
                    for (const c of (Array.isArray(vv.children) ? vv.children : [vv.children])) { const r = wv(c); if (r) return r; }
                }
                return false;
            };
            return wv(document.querySelector('#app').__vue_app__._instance);
        }""", [n, v])

    page.goto("http://127.0.0.1:3005/login")
    page.wait_for_timeout(1500)
    page.fill("input[type='text']", "admin")
    page.fill("input[type='password']", "admin123")
    page.locator("button[type='submit']").click()
    page.wait_for_timeout(2000)
    page.goto("http://127.0.0.1:3005/metrics")
    page.wait_for_timeout(8000)
    all_reqs.clear()

    # 1. Department
    print("Step 1: dimension=department")
    sv("dimension", "department")
    page.wait_for_timeout(3000)
    print(f"  state: {gs()}")

    # 2. CBG
    print("Step 2: entity=CBG")
    sv("selectedEntity", "CBG")
    page.wait_for_timeout(3000)
    s = gs()
    print(f"  state: {s}")
    print(f"  reqs: {len(all_reqs)}")
    for qs in all_reqs:
        print(f"    dim={qs.get('dimension',[''])[0]:12s} dept={qs.get('department',[''])[0]:8s} ent={qs.get('entity',[''])[0] or '-'}")

    # 3. Cross-dim = customer
    print("\nStep 3: crossDimension=customer")
    all_reqs.clear()
    sv("crossDimension", "customer")
    page.wait_for_timeout(5000)
    s2 = gs()
    print(f"  state: {s2}")
    print(f"  reqs: {len(all_reqs)}")
    for qs in all_reqs:
        print(f"    dim={qs.get('dimension',[''])[0]:12s} dept={qs.get('department',[''])[0]:8s} ent={qs.get('entity',[''])[0] or '-'}")

    # Table content
    rows = page.locator(".ant-table-tbody").first.locator("tr").all()
    print(f"\nTable rows: {len(rows)}")
    for i, row in enumerate(rows[:6]):
        cells = row.locator("td").all()
        if len(cells) >= 3:
            v0 = (cells[0].inner_text()[:15] if len(cells)>0 else '').replace('\xa0','').strip()
            v1 = (cells[1].inner_text()[:30] if len(cells)>1 else '').replace('\xa0','').strip()
            v2 = (cells[2].inner_text()[:18] if len(cells)>2 else '').replace('\xa0','').strip()
            print(f"  [{i}] {v0:12s} {v1:20s} {v2}")

    items = page.locator(".concentration-panel .ant-list-item").all()
    print(f"Concentration: {len(items)}")

    browser.close()
