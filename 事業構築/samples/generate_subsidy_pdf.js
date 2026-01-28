const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();

  // HTMLファイルのパス
  const htmlPath = path.join(__dirname, 'subsidy_report.html');
  const pdfPath = path.join(__dirname, '美容室開業_補助金レポート.pdf');

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
