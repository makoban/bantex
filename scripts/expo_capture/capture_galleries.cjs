// 展示会動画（src/ExpoVideo）の「1 映画」「2 HP採点」に使う実画面を撮影して public/expo/ に保存する。
//
// 前提: 2つのギャラリーが起動していること
//   映画  http://127.0.0.1:8820/gallery （BANTEX AI CINEMA）
//   採点  http://127.0.0.1:8792/gallery （SITE CHECK）
// 使い方（このリポジトリには playwright を入れていないので、入っている場所を指定する）:
//   PLAYWRIGHT=/path/to/node_modules/playwright node scripts/expo_capture/capture_galleries.cjs
//
// 動画に載せるための加工（撮影時にページへCSS/DOMで当てる。元のアプリは変えない）:
//   映画: 「完成」のうち CINEMA_JOB の1件だけを表示し、QRはぼかす（限定公開のYouTubeリンクを動画に載せないため）
//   採点: 実在企業の名前・ドメインを「企業A」などに置き換え、サイトのサムネイルをぼかす
const path = require("path");
const { chromium } = require(process.env.PLAYWRIGHT || "playwright");

const OUT = path.resolve(__dirname, "../../public/expo");
const CINEMA = process.env.CINEMA_URL || "http://127.0.0.1:8820/gallery";
const SITECHECK = process.env.SITECHECK_URL || "http://127.0.0.1:8792/gallery";
const CINEMA_JOB = process.env.CINEMA_JOB || "001"; // 動画に載せる映画の受付番号

(async () => {
  const browser = await chromium.launch();

  // 1) 映画ギャラリー（1600x1000 を 1.2倍で撮る → 1920x1200）
  const p = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1.2 });
  await p.goto(CINEMA, { waitUntil: "networkidle" });
  await p.getByRole("button", { name: "完成", exact: true }).click();
  await p.addStyleTag({ content: 'img[alt*="QR"]{filter:blur(9px) !important;}' });
  // 載せるのは指定した受付番号のカードだけ（顔が写るため、掲載してよい作品だけを選ぶ）
  await p.evaluate((job) => {
    document.querySelectorAll("article.delivery-card").forEach((card) => {
      if (!card.textContent.includes(`受付 ${job}`)) card.remove();
    });
  }, CINEMA_JOB);
  await p.waitForTimeout(800);
  await p.screenshot({ path: `${OUT}/cinema_gallery.jpg`, type: "jpeg", quality: 90 });

  // 2) SITE CHECK 50社比較（1600幅、上から3000pxまで）
  const q = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
  await q.goto(SITECHECK, { waitUntil: "networkidle" });
  // 遅延読み込みのサムネイルを全部出す
  const h = await q.evaluate(() => document.body.scrollHeight);
  for (let y = 0; y < h; y += 600) {
    await q.evaluate((yy) => window.scrollTo(0, yy), y);
    await q.waitForTimeout(250);
  }
  await q.evaluate(() => {
    window.scrollTo(0, 0);
    const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    document.querySelectorAll(".company-card").forEach((card, i) => {
      const label = `企業${letters[i % 26]}${i >= 26 ? 2 : ""}`;
      const name = card.querySelector("h2");
      if (name) name.textContent = label;
      const domain = card.querySelector(".company-domain");
      if (domain) domain.textContent = "www.●●●●.co.jp";
      card.setAttribute("aria-label", label);
    });
  });
  await q.addStyleTag({ content: ".company-image img{filter:blur(7px) saturate(1.15) !important;transform:scale(1.04);}" });
  await q.waitForLoadState("networkidle");
  await q.waitForTimeout(1200);
  await q.screenshot({
    path: `${OUT}/sitecheck_gallery.jpg`,
    type: "jpeg",
    quality: 88,
    fullPage: true,
    clip: { x: 0, y: 0, width: 1600, height: 3000 },
  });

  await browser.close();
  console.log(`saved: ${OUT}/cinema_gallery.jpg, ${OUT}/sitecheck_gallery.jpg`);
})();
