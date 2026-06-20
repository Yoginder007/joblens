// @ts-check
/**
 * Frontend inspection / "design teardown" tool — point it at any public site and
 * it extracts the *real* design system: CSS custom properties (tokens), font
 * stack, transition + animation declarations, @keyframes, easing curves, nav
 * structure, button styles, favicons/theme-color — plus screenshots in light and
 * dark across desktop + mobile, including a primary-button hover frame.
 *
 * Reusable across projects — this is how you "scrape a frontend for inspiration":
 *   node scripts/inspect-site.mjs https://example.com mysite
 *
 * Output → frontend/.inspect/<label>/  (report.json + report.md + *.png)
 * Stylesheets are fetched directly (not via sheet.cssRules) to dodge CORS.
 */
import { chromium } from "playwright";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const URL = process.argv[2] || "https://example.com/";
const LABEL = process.argv[3] || "site";
const OUT = join(dirname(fileURLToPath(import.meta.url)), "..", ".inspect", LABEL);

const VIEWPORTS = { desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } };

/** Pull design-relevant facts out of the live DOM. */
function extractInPage() {
  const cs = getComputedStyle(document.documentElement);
  const tokens = {};
  for (const name of cs) if (name.startsWith("--")) tokens[name] = cs.getPropertyValue(name).trim();

  const bodyCS = getComputedStyle(document.body);
  const sample = (sel, n = 8) =>
    [...document.querySelectorAll(sel)].slice(0, n).map((el) => {
      const s = getComputedStyle(el);
      return {
        text: (el.textContent || "").trim().slice(0, 40),
        borderRadius: s.borderRadius,
        transition: s.transition,
        background: s.backgroundColor,
        color: s.color,
        padding: s.padding,
        fontWeight: s.fontWeight,
        boxShadow: s.boxShadow.slice(0, 80),
      };
    });

  return {
    title: document.title,
    fonts: { body: bodyCS.fontFamily, h1: getComputedStyle(document.querySelector("h1") || document.body).fontFamily },
    colorScheme: bodyCS.colorScheme,
    bg: bodyCS.backgroundColor,
    fg: bodyCS.color,
    tokens,
    nav: [...document.querySelectorAll("header a, nav a")].slice(0, 24).map((a) => ({
      label: (a.textContent || "").trim().slice(0, 32),
      href: a.getAttribute("href"),
    })),
    buttons: sample("button, a[class*='button'], a[class*='btn'], [role='button']"),
    favicons: [...document.querySelectorAll("link[rel*='icon']")].map((l) => ({
      rel: l.getAttribute("rel"), href: l.getAttribute("href"), sizes: l.getAttribute("sizes"),
    })),
    themeColor: (document.querySelector("meta[name='theme-color']") || {}).content || null,
    stylesheets: [...document.styleSheets].map((s) => s.href).filter(Boolean),
  };
}

/** Scan concatenated CSS for the animation language of the site. */
function distillCss(css) {
  const uniq = (arr) => [...new Set(arr)];
  const keyframes = uniq((css.match(/@keyframes[^{]+\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}/g) || []).map((k) => k.slice(0, 240)));
  const easings = uniq(css.match(/cubic-bezier\([^)]+\)/g) || []);
  const durations = uniq(css.match(/(?:transition|animation)(?:-duration)?:[^;]*?(\d+m?s)/g)?.map((m) => (m.match(/\d+m?s/) || [])[0]) || []);
  const transitions = uniq((css.match(/transition:\s*[^;{}]+/g) || []).map((t) => t.slice(0, 100))).slice(0, 40);
  return {
    keyframeCount: keyframes.length,
    keyframes: keyframes.slice(0, 30),
    easings,
    durations,
    transitions,
  };
}

async function run() {
  await rm(OUT, { recursive: true, force: true });
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch();
  const report = { url: URL, capturedAt: new Date().toISOString(), themes: {} };

  // Fetch + distill stylesheets once (theme-independent) using a throwaway context.
  const probe = await browser.newContext({ viewport: VIEWPORTS.desktop });
  const probePage = await probe.newPage();
  await probePage.goto(URL, { waitUntil: "load", timeout: 45000 });
  await probePage.waitForTimeout(1500);
  const base = await probePage.evaluate(extractInPage);
  let allCss = "";
  for (const href of base.stylesheets.slice(0, 12)) {
    try {
      const res = await probe.request.get(href, { timeout: 15000 });
      if (res.ok()) allCss += "\n" + (await res.text());
    } catch { /* skip unreachable sheet */ }
  }
  report.meta = base;
  report.css = distillCss(allCss);
  report.cssBytes = allCss.length;
  await probe.close();

  // Screenshots per theme × viewport (theme via prefers-color-scheme emulation).
  for (const scheme of ["light", "dark"]) {
    report.themes[scheme] = {};
    for (const [vpName, viewport] of Object.entries(VIEWPORTS)) {
      const ctx = await browser.newContext({ viewport, colorScheme: scheme });
      const page = await ctx.newPage();
      try {
        await page.goto(URL, { waitUntil: "load", timeout: 45000 });
        await page.waitForTimeout(1800);
        await page.screenshot({ path: join(OUT, `${vpName}-${scheme}.png`), fullPage: true });
        if (vpName === "desktop") {
          await page.screenshot({ path: join(OUT, `hero-${scheme}.png`), fullPage: false });
          // Hover the first primary-looking button and capture the hover state.
          const btn = page.locator("a[class*='button'], button").first();
          if (await btn.count()) {
            await btn.hover().catch(() => {});
            await page.waitForTimeout(450);
            await page.screenshot({ path: join(OUT, `hover-${scheme}.png`), fullPage: false });
          }
          report.themes[scheme].sampledBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
        }
        console.log(`✓ ${vpName}-${scheme}`);
      } catch (e) {
        console.log(`✗ ${vpName}-${scheme} — ${e.message}`);
      }
      await ctx.close();
    }
  }

  await browser.close();
  await writeFile(join(OUT, "report.json"), JSON.stringify(report, null, 2));
  console.log(`\nReport → ${join(OUT, "report.json")}`);
  console.log(`Tokens: ${Object.keys(base.tokens).length} · keyframes: ${report.css.keyframeCount} · easings: ${report.css.easings.length} · CSS: ${(report.cssBytes / 1024) | 0}KB`);
}

run().catch((e) => { console.error(e); process.exit(1); });
