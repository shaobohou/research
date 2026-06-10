// Captures reference renders of a model from all camera views the original app
// exposes (iso + the six axis views), at a settled fold percent, dumping the
// exact camera matrices alongside each screenshot.
//
// Usage: PCT=0.6 node extract_views.js <model-data-url> <outdir>

const { chromium } = require('/tmp/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const MODEL = process.argv[2] || 'Origami/traditionalCrane.svg';
const OUTDIR = process.argv[3] || 'groundtruth/crane_views';
const PCT = Number(process.env.PCT || '0.6');
const PORT = 8745;
const W = 800, H = 600;

(async () => {
  fs.mkdirSync(OUTDIR, { recursive: true });

  const server = require('child_process').spawn(
    'python3', ['-m', 'http.server', String(PORT)],
    { cwd: '/tmp/OrigamiSimulator', stdio: 'ignore' });
  await new Promise((resolve, reject) => {
    let tries = 0;
    const probe = () => {
      require('http').get(`http://localhost:${PORT}/index.html`, res => resolve(res.resume()))
        .on('error', () => (++tries > 50 ? reject(new Error('server never came up')) :
          setTimeout(probe, 200)));
    };
    probe();
  });

  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium_headless_shell-1223/chrome-headless-shell-linux64/chrome-headless-shell',
    args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader'],
  });
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.log('pageerror:', e.message));

  await page.goto(`http://localhost:${PORT}/`, { waitUntil: 'load' });
  await page.waitForFunction(() => window.globals && globals.importer && globals.model,
    null, { timeout: 60000 });

  for (let i = 0; i < 30; i++) {
    await page.evaluate(m => globals.importer.importDemoFile(m), MODEL);
    await page.waitForTimeout(2000);
    const ok = await page.evaluate(() =>
      globals.model.getNodes().length > 0 && !globals.needsSync && !globals.simNeedsSync);
    if (ok) break;
    if (i === 29) throw new Error('model never loaded');
  }
  await page.evaluate(() => {
    globals.threeView.pauseSimulation();
    globals.shouldAnimateFoldPercent = false;
    document.querySelectorAll('body > *').forEach(el => {
      if (!el.contains(document.querySelector('#threeContainer canvas'))) el.remove();
    });
  });
  await page.waitForTimeout(200);

  // settle at the target fold percent
  await page.evaluate(p => {
    globals.creasePercent = p;
    globals.shouldChangeCreasePercent = true;
    globals.model.reset();
    globals.model.step(3000);
  }, PCT);
  await page.waitForTimeout(300);

  const positions = await page.evaluate(() => Array.from(globals.model.getPositionsArray()));

  const views = [
    ['iso', 'setCameraIso', null],
    ['x_pos', 'setCameraX', 1], ['x_neg', 'setCameraX', -1],
    ['y_pos', 'setCameraY', 1], ['y_neg', 'setCameraY', -1],
    ['z_pos', 'setCameraZ', 1], ['z_neg', 'setCameraZ', -1],
  ];
  const out = { creasePercent: PCT, width: W, height: H, positions, views: [] };
  for (const [name, fn, sign] of views) {
    const cam = await page.evaluate(([fn, sign]) => {
      if (sign === null) globals.threeView[fn]();
      else globals.threeView[fn](sign);
      const cam = globals.threeView.camera;
      cam.updateMatrixWorld(true);
      return {
        projectionMatrix: cam.projectionMatrix.toArray(),
        matrixWorldInverse: cam.matrixWorldInverse.toArray(),
        cameraPosition: [cam.position.x, cam.position.y, cam.position.z],
      };
    }, [fn, sign]);
    await page.waitForTimeout(300); // let the loop render the new view
    const img = `view_${name}.png`;
    await page.locator('canvas').first().screenshot({ path: path.join(OUTDIR, img) });
    out.views.push({ name, image: img, ...cam });
    console.log('captured', name, 'cam at', cam.cameraPosition.map(v => v.toFixed(2)).join(','));
  }
  fs.writeFileSync(path.join(OUTDIR, 'views.json'), JSON.stringify(out));

  await browser.close();
  server.kill();
  console.log('done ->', OUTDIR);
})().catch(e => { console.error(e); process.exit(1); });
