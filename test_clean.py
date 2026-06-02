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
            all_reqs.append((qs, req.url))

    page.on("request", on_req)

    def get_vue():
        return page.evaluate("""() => {
            const w = (inst) => {
                if (!inst) return;
                if (inst.setupState && inst.setupState.dimension !== undefined) return inst.setupState;
                if (inst.subTree) { return wv(inst.subTree); }
            };
            const wv = (v) => {
                if (!v) return;
                if (v.component) {
                    if (v.component.setupState && v.component.setupState.dimension !== undefined) return v.component.setupState;
                    const r = w(v.component); if (r) return r;
                }
                if (v.children) {
                    for (const c of (Array.isArray(v.children) ? v.children : [v.children])) { const r = wv(c); if (r) return r; }
                }
            };
            const s = w(document.querySelector('#app').__vue_app__._instance);
            return s ? { dim: s.dimension.value, entity: s.selectedEntity.value, deptScope: s.departmentScope.value, cross: s.crossDimension.value } : null;
        }""")

    def set_vue(name, val):
        return page.evaluate("""([n, v]) => {
            const w = (inst) => {
                if (!inst) return false;
                if (inst.setupState && inst.setupState[n] !== undefined) { inst.setupState[n].value = v; return true; }
                if (inst.subTree) { return wv(inst.subTree); }
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
        }""", [name, val])

    # Login
    page.goto("http://127.0.0.1:3005/login")
    page.wait_for_timeout(1500)
    page.fill("input[type='text']", "admin")
    page.fill("input[type='password']", "admin123")
    page.locator("button[type='submit']").click()
    page.wait_for_timeout(2000)
    page.goto("http://127.0.0.1:3005/metrics")
    page.wait_for_timeout(8000)
    all_reqs.clear()
    print(f"Initial state: {get_vue()}")

    # Set department
    print("=== Set dimension=department ===")
    set_vue("dimension", "department")
    page.wait_for_timeout(3000)
    r = all_reqs[-1] if all_reqs else None
    print(f"  State: {get_vue()}")
    if r: print(f"  Last REQ: dim={r[0].get('dimension',['?'])[0]} dept={r[0].get('department',['(none)'])[0]} entity={r[0].get('entity',[''])[0] or '(none)'}")

    # Set entity to CBG
    print("=== Set entity=CBG ===")
    set_vue("selectedEntity", "CBG")
    page.wait_for_timeout(3000)
    s = get_vue()
    print(f"  State: {s}")
    r = all_reqs[-2] if len(all_reqs) >= 2 else all_reqs[-1] if all_reqs else None
    if r: print(f"  Last+REQ: dim={r[0].get('dimension',['?'])[0]} dept={r[0].get('department',['(none)'])[0]} entity={r[0].get('entity',[''])[0] or '(none)'}")

    # All current requests
    print(f"  All reqs count: {len(all_reqs)}")
    for qs, url in all_reqs:
        dim = qs.get('dimension',['?'])[0]
        dept = qs.get('department',['(none)'])[0]
        ent = qs.get('entity',[''])[0] or '(none)'
        print(f"    dim={dim:12s} dept={dept:8s} entity={ent}")

    # Set cross-dimension to customer
    print("=== Set crossDimension=customer ===")
    all_reqs.clear()
    set_vue("crossDimension", "customer")
    page.wait_for_timeout(5000)
    print(f"  State: {get_vue()}")
    print(f"  Reqs: {len(all_reqs)}")
    for qs, url in all_reqs:
        dim = qs.get('dimension',['?'])[0]
        dept = qs.get('department',['(none)'])[0]
        ent = qs.get('entity',[''])[0] or '(none)'
        print(f"    dim={dim:12s} dept={dept:8s} entity={ent}")

    # Check table
    rows = page.locator(".ant-table-tbody").first.locator("tr").all()
    print(f"\nTable rows: {len(rows)}")
    for i, row in enumerate(rows[:3]):
        cells = row.locator("td").all()
        if len(cells) >= 3:
            v0 = (cells[0].inner_text()[:15] if len(cells)>0 else '').replace(u'\xa0','').strip()
            v1 = (cells[1].inner_text()[:25] if len(cells)>1 else '').replace(u'\xa0','').strip()
            v2 = (cells[2].inner_text()[:15] if len(cells)>2 else '').replace(u'\xa0','').strip()
            print(f"  [{i}] {v0:12s} {v1:20s} {v2}")

    # Concentration
    items = page.locator(".concentration-panel .ant-list-item").all()
    print(f"Concentration items: {len(items)}")

    browser.close()
