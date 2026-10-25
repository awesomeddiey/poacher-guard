// Captures Label Studio screenshots for Figure 3.2: node shot_labelstudio.js <taskId> <out.png>
const { chromium } = require("playwright");
(async () => {
  const [task, out] = [process.argv[2] || "1", process.argv[3] || "ls.png"];
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1500, height: 900 } });
  await p.goto("http://localhost:8099/user/login/"); await p.fill('input[name="email"]', "researcher@example.com"); await p.fill('input[name="password"]', "poacherguard2026");
  await p.click('button[type="submit"], button:has-text("Log in")'); await p.waitForLoadState("networkidle");
  await p.goto(`http://localhost:8099/projects/1/data?tab=1&task=${task}`); await p.waitForTimeout(6000);
  await p.screenshot({ path: out }); console.log("saved", out, p.url()); await b.close();
})();
