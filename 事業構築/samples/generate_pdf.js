const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
    const browser = await puppeteer.launch();
    const page = await browser.newPage();

    const htmlPath = path.join(__dirname, 'business_plan_print.html');
    await page.goto('file://' + htmlPath, { waitUntil: 'networkidle0' });

    await page.pdf({
        path: path.join(__dirname, '美容室COCORO_事業計画書.pdf'),
        format: 'A4',
        printBackground: true,
        margin: { top: 0, right: 0, bottom: 0, left: 0 }
    });

    await browser.close();
    console.log('PDF created: 美容室COCORO_事業計画書.pdf');
})();
