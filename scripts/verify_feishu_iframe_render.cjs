#!/usr/bin/env node

const DEFAULT_VIEWPORT = { width: 1280, height: 900 };
const DEFAULT_IFRAME = { width: 1200, height: 760 };

function usage() {
  return [
    "Usage: node scripts/verify_feishu_iframe_render.cjs <base_url>",
    "",
    "Verifies that the BI homepage and /admin page can render inside an iframe.",
    "Requires Playwright to be resolvable and uses the local Chrome channel by default.",
    "Set PLAYWRIGHT_CHROME_CHANNEL=chromium if you want Playwright's bundled Chromium.",
  ].join("\n");
}

function targetUrl(baseUrl, path) {
  const normalizedBase = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`;
  return new URL(path.replace(/^\//, ""), normalizedBase).toString();
}

async function verifyTarget({ page, baseUrl, path, expectedText, minHeight }) {
  const url = targetUrl(baseUrl, path);
  await page.setContent(
    `<!doctype html><html><body style="margin:0"><iframe title="feishu-smoke" src="${url}" style="width:${DEFAULT_IFRAME.width}px;height:${DEFAULT_IFRAME.height}px;border:0"></iframe></body></html>`,
    { waitUntil: "load" },
  );
  await page.waitForTimeout(1000);

  const frame = page.frames().find((candidate) => candidate.url().startsWith(url));
  if (!frame) {
    throw new Error(`${path} iframe frame was not created. Frames: ${page.frames().map((item) => item.url()).join(", ")}`);
  }

  await frame.waitForSelector("#root", { timeout: 10000 });
  await frame.waitForSelector(`text=${expectedText}`, { timeout: 10000 });
  const rootBox = await frame.locator("#root").boundingBox();
  if (!rootBox || rootBox.width < 1000 || rootBox.height < minHeight) {
    throw new Error(`${path} rendered with unexpected root box: ${JSON.stringify(rootBox)}`);
  }

  return {
    path,
    url,
    expectedText,
    rootBox,
  };
}

async function main() {
  const baseUrl = process.argv[2];
  if (!baseUrl || baseUrl === "-h" || baseUrl === "--help") {
    console.error(usage());
    process.exit(baseUrl ? 0 : 2);
  }

  let chromium;
  try {
    ({ chromium } = require("playwright"));
  } catch (error) {
    throw new Error(
      "Playwright is not resolvable. Install it for this environment or run with NODE_PATH pointing to a Playwright package.",
    );
  }

  const browser = await chromium.launch({
    channel: process.env.PLAYWRIGHT_CHROME_CHANNEL || "chrome",
    headless: true,
  });

  try {
    const page = await browser.newPage({ viewport: DEFAULT_VIEWPORT });
    const checks = [];
    checks.push(await verifyTarget({ page, baseUrl, path: "/", expectedText: "星途短视频经营 BI", minHeight: 500 }));
    checks.push(await verifyTarget({ page, baseUrl, path: "/admin", expectedText: "上传或替换 Excel", minHeight: 350 }));
    console.log(JSON.stringify({ status: "ok", iframe_dom: "ok", checks }, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(JSON.stringify({ status: "failed", error: error.message }, null, 2));
  process.exit(1);
});
