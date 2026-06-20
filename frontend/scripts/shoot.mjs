// @ts-check
/**
 * JobLens screenshot harness for visual checks across themes + breakpoints.
 *
 * Assumes `npm run dev` is already serving the app (default http://localhost:3000)
 * and, for real data, the backend is up on :8000. Writes PNGs to `frontend/.shots/`
 * which you can open and review. Captures both themes across
 * mobile / tablet / desktop, plus a few interaction states.
 *
 *   node scripts/shoot.mjs                  # all states, both themes, 3 viewports
 *   BASE_URL=http://localhost:3000 node scripts/shoot.mjs
 *   SHOT=browse THEME=dark VP=desktop node scripts/shoot.mjs   # filter
 *
 * Reduced-motion is emulated so frames are stable (no half-played animations).
 */
import { chromium } from "playwright";
import { mkdir, rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const BASE_URL = process.env.BASE_URL || "http://localhost:3000";
const OUT = join(dirname(fileURLToPath(import.meta.url)), "..", ".shots");

const VIEWPORTS = {
  mobile: { width: 390, height: 844 },
  tablet: { width: 834, height: 1112 },
  desktop: { width: 1440, height: 900 },
};
const THEMES = ["light", "dark"];

// Each "shot" navigates to a state and screenshots it. `prepare` runs after the
// page settles (e.g. click a tab/open a modal). Keep selectors text-based so they
// survive class churn. `fullPage` captures beyond the fold where useful.
const SHOTS = {
  browse: {
    path: "/",
    fullPage: true,
    async prepare() {},
  },
  "match-configure": {
    path: "/",
    fullPage: true,
    async prepare(page) {
      await page.getByRole("button", { name: /Match My Resume/i }).click();
      await page.waitForTimeout(500);
    },
  },
  "auth-modal": {
    path: "/",
    fullPage: false,
    async prepare(page) {
      // UserMenu exposes a Log in / Sign in trigger; open it then the modal.
      const trigger = page.getByRole("button", { name: /log ?in|sign ?in|account/i }).first();
      if (await trigger.count()) {
        await trigger.click().catch(() => {});
        await page.waitForTimeout(400);
      }
    },
  },
};

const want = {
  shot: process.env.SHOT,
  theme: process.env.THEME,
  vp: process.env.VP,
};
const pick = (val, key) => !want[key] || want[key] === val;

async function run() {
  await rm(OUT, { recursive: true, force: true });
  await mkdir(OUT, { recursive: true });

  const browser = await chromium.launch();
  let count = 0;
  const failures = [];

  for (const theme of THEMES) {
    if (!pick(theme, "theme")) continue;
    for (const [vpName, viewport] of Object.entries(VIEWPORTS)) {
      if (!pick(vpName, "vp")) continue;

      const context = await browser.newContext({ viewport, reducedMotion: "reduce" });
      // Set the theme before any app script runs (next-themes reads localStorage).
      await context.addInitScript((t) => {
        try { localStorage.setItem("theme", t); } catch {}
      }, theme);
      const page = await context.newPage();

      for (const [shotName, shot] of Object.entries(SHOTS)) {
        if (!pick(shotName, "shot")) continue;
        const label = `${shotName}-${vpName}-${theme}`;
        try {
          await page.goto(BASE_URL + shot.path, { waitUntil: "networkidle", timeout: 30000 });
          await page.waitForTimeout(900); // settle layout + data
          await shot.prepare(page);
          await page.waitForTimeout(400);
          const file = join(OUT, `${label}.png`);
          await page.screenshot({ path: file, fullPage: shot.fullPage });
          count++;
          console.log(`✓ ${label}`);
        } catch (err) {
          failures.push(`${label}: ${err.message}`);
          console.log(`✗ ${label} — ${err.message}`);
        }
      }
      await context.close();
    }
  }

  await browser.close();
  console.log(`\n${count} screenshots → ${OUT}`);
  if (failures.length) {
    console.log(`${failures.length} failed:`);
    for (const f of failures) console.log("  - " + f);
  }
}

run().catch((e) => { console.error(e); process.exit(1); });
