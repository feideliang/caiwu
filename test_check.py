# -*- coding: utf-8 -*-
import os
os.environ["PYTHONIOENCODING"] = "utf-8"
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    def dm():
        for _ in range(3):
            page.evaluate("document.querySelectorAll('vite-error-overlay,[data-vite-dev-overlay]').forEach(e=>e.remove())")
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)

    page.goto("http://127.0.0.1:3005/login")
    page.wait_for_timeout(1500)
    page.fill("input[type='text']", "admin")
    page.fill("input[type='password']", "admin123")
    page.locator("button[type='submit']").click()
    page.wait_for_timeout(2000)
    print(f"URL after login: {page.url}")

    page.goto("http://127.0.0.1:3005/metrics")
    page.wait_for_timeout(8000)
    dm()
    print(f"URL after navigate: {page.url}")

    # Check if app is mounted
    has_vue = page.evaluate("() => !!document.querySelector('#app').__vue_app__")
    print(f"Vue app mounted: {has_vue}")

    state = page.evaluate("""() => {
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
        try {
            const s = w(document.querySelector('#app').__vue_app__._instance);
            if (!s) return 'not found';
            return { dim: s.dimension?.value, entity: s.selectedEntity?.value, dept: s.departmentScope?.value, cross: s.crossDimension?.value };
        } catch(e) { return 'err: ' + e.message; }
    }""")
    print(f"State: {state}")

    # Try setting something
    result = page.evaluate("""() => {
        const w = (inst) => {
            if (!inst) return false;
            if (inst.setupState && inst.setupState.dimension !== undefined) { inst.setupState.dimension.value = 'department'; return true; }
            if (inst.subTree) { return wv(inst.subTree); }
            return false;
        };
        const wv = (v) => {
            if (!v) return false;
            if (v.component) {
                if (v.component.setupState && v.component.setupState.dimension !== undefined) { v.component.setupState.dimension.value = 'department'; return true; }
                const r = w(v.component); if (r) return r;
            }
            if (v.children) {
                for (const c of (Array.isArray(v.children) ? v.children : [v.children])) { const r = wv(c); if (r) return r; }
            }
            return false;
        };
        return wv(document.querySelector('#app').__vue_app__._instance);
    }""")
    print(f"Set result: {result}")

    page.wait_for_timeout(2000)
    state2 = page.evaluate("""() => {
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
        try {
            const s = w(document.querySelector('#app').__vue_app__._instance);
            if (!s) return 'not found';
            return { dim: s.dimension?.value, entity: s.selectedEntity?.value, dept: s.departmentScope?.value, cross: s.crossDimension?.value };
        } catch(e) { return 'err: ' + e.message; }
    }""")
    print(f"State after set: {state2}")

    browser.close()
