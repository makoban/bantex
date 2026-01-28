const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();

  // HTMLファイルのパス
  const htmlPath = path.join(__dirname, 'sns_strategy.html');
  const pdfPath = path.join(__dirname, '美容室COCORO_SNS戦略.pdf');

  await page.goto(`file://${htmlPath}`, { waitUntil: 'networkidle0' });

  // PDF生成
  await page.pdf({
    path: pdfPath,
    format: 'A4',
    printBackground: true
  });

  console.log(`PDF created: ${pdfPath}`);
  await browser.close();
})();
