// Capture dashboard screenshots for the dissertation.
//   node tools/capture_screenshots.js http://localhost:8000
// Needs:  npm i playwright  (once) and the Poacher Guard server running.
const { chromium } = require("playwright");
const fs = require("fs");
(async () => {
  const url = process.argv[2] || "http://localhost:8000";
  fs.mkdirSync("results/screens", { recursive: true });
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await p.goto(url); await p.waitForTimeout(4000);
  await p.screenshot({ path: "results/screens/dashboard_overview.png", fullPage: true });
  for (const [sel, name] of [["#live", "camera_dialog"], ["#map-ex", "map_dialog"], ["#activity-card", "activity_dialog"]]) {
    await p.click(sel); await p.waitForTimeout(1200);
    await p.screenshot({ path: `results/screens/${name}.png` }); await p.keyboard.press("Escape");
  }
  await b.close(); console.log("saved to results/screens/");
})();
