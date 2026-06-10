// Drives the original OrigamiSimulator (served from /tmp/OrigamiSimulator) in headless
// chromium and extracts:
//  - the processed (triangulated, centered, scaled) model + crease params + solver params
//  - deterministic solver trajectories (positions after fixed step counts)
//  - reference renders (canvas screenshots) + camera matrices for those states
//
// Usage: node extract_groundtruth.js <model-data-url> <outdir>
//   e.g. node extract_groundtruth.js Origami/traditionalCrane.svg groundtruth/crane

const { chromium } = require('/tmp/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const MODEL = process.argv[2] || 'Origami/traditionalCrane.svg';
const OUTDIR = process.argv[3] || 'groundtruth/crane';
const PORT = 8741;
const W = 800, H = 600;

(async () => {
  fs.mkdirSync(OUTDIR, { recursive: true });

  const server = require('child_process').spawn(
    'python3', ['-m', 'http.server', String(PORT)],
    { cwd: '/tmp/OrigamiSimulator', stdio: 'ignore' });
  // wait for the server to accept connections
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
    args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--disable-gpu-sandbox'],
  });
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.log('pageerror:', e.message));

  await page.goto(`http://localhost:${PORT}/`, { waitUntil: 'load' });
  await page.waitForFunction(() => window.globals && globals.importer && globals.model,
    null, { timeout: 60000 });

  // the demo-link auto-click at startup is racy in headless; load the model directly,
  // retrying until the (async) import completes
  for (let i = 0; i < 30; i++) {
    await page.evaluate(m => globals.importer.importDemoFile(m), MODEL);
    await page.waitForTimeout(2000);
    const n = await page.evaluate(() =>
      globals.model.getNodes().length > 0 && !globals.needsSync && !globals.simNeedsSync);
    if (n) break;
    if (i === 29) throw new Error('model never loaded');
  }
  await page.waitForTimeout(500);

  // freeze the animation-driven sim, then reset state deterministically
  await page.evaluate(() => {
    globals.threeView.pauseSimulation();
    globals.shouldAnimateFoldPercent = false;
  });
  await page.waitForTimeout(200);

  const model = await page.evaluate(() => {
    const nodes = globals.model.getNodes();
    const edges = globals.model.getEdges();
    const faces = globals.model.getFaces();
    const creases = globals.model.getCreases();
    const nodeIndex = n => n.getIndex();
    return {
      params: {
        creasePercent: globals.creasePercent,
        axialStiffness: globals.axialStiffness,
        creaseStiffness: globals.creaseStiffness,
        panelStiffness: globals.panelStiffness,
        faceStiffness: globals.faceStiffness,
        percentDamping: globals.percentDamping,
        integrationType: globals.integrationType,
        numSteps: globals.numSteps,
        scale: globals.scale,
        color1: globals.color1, color2: globals.color2,
        backgroundColor: globals.backgroundColor,
      },
      positions: nodes.map(n => { const p = n.getOriginalPosition(); return [p.x, p.y, p.z]; }),
      fixed: nodes.map(n => n.isFixed()),
      edges: edges.map(b => [nodeIndex(b.nodes[0]), nodeIndex(b.nodes[1])]),
      edgeK: edges.map(b => b.getK()),
      edgeD: edges.map(b => b.getD()),
      edgeLength: edges.map(b => b.getLength()),
      faces: faces,
      creases: creases.map(c => ({
        edge: [nodeIndex(c.edge.nodes[0]), nodeIndex(c.edge.nodes[1])],
        face1: c.face1Index, face2: c.face2Index,
        node1: nodeIndex(c.node1), node2: nodeIndex(c.node2),
        k: c.getK(), targetTheta: c.getTargetTheta(), type: c.type,
      })),
      edgesAssignment: globals.pattern.getFoldData().edges_assignment,
      edgesVerticesFold: globals.pattern.getFoldData().edges_vertices,
    };
  });
  fs.writeFileSync(path.join(OUTDIR, 'model.json'), JSON.stringify(model));
  console.log(`model: ${model.positions.length} nodes, ${model.edges.length} edges,` +
    ` ${model.faces.length} faces, ${model.creases.length} creases`);

  // deterministic trajectory: reset, then step in chunks, dumping positions
  const stepDumps = [1, 10, 100, 500, 1000];
  await page.evaluate(() => globals.model.reset());
  const traj = {};
  let done = 0;
  for (const target of stepDumps) {
    await page.evaluate(n => globals.model.step(n), target - done);
    done = target;
    traj[target] = await page.evaluate(() => Array.from(globals.model.getPositionsArray()));
  }
  fs.writeFileSync(path.join(OUTDIR, 'trajectory.json'), JSON.stringify(traj));
  console.log('trajectory dumped at steps', stepDumps.join(','));

  // hide all DOM UI overlaying the WebGL canvas so screenshots are pure renders
  await page.evaluate(() => {
    document.querySelectorAll('body > *').forEach(el => {
      if (!el.contains(document.querySelector('#threeContainer canvas'))) {
        el.style.display = 'none';
      }
    });
    document.querySelectorAll('#threeContainer ~ *, .ui-slider, #helper').forEach(
      el => el.style.display = 'none');
  });

  // reference renders at several fold percents (after settling), plus camera + positions
  const PCTS = (process.env.PCTS || '0,0.3,0.6,0.9').split(',').map(Number);
  const renders = [];
  for (const pct of PCTS) {
    await page.evaluate(p => {
      globals.creasePercent = p;
      globals.shouldChangeCreasePercent = true;
      globals.model.reset();
    }, pct);
    await page.evaluate(() => globals.model.step(3000));  // settle
    // force a render of the new geometry
    await page.waitForTimeout(300);
    const state = await page.evaluate(() => {
      const cam = globals.threeView.camera;
      cam.updateMatrixWorld(true);
      return {
        positions: Array.from(globals.model.getPositionsArray()),
        projectionMatrix: cam.projectionMatrix.toArray(),
        matrixWorldInverse: cam.matrixWorldInverse.toArray(),
        cameraPosition: [cam.position.x, cam.position.y, cam.position.z],
      };
    });
    // the "first time" helper tooltip pops up on a delay; nuke any UI again
    await page.evaluate(() => {
      document.querySelectorAll('body > *').forEach(el => {
        if (!el.contains(document.querySelector('#threeContainer canvas'))) el.remove();
      });
    });
    const name = `render_${Math.round(pct * 100)}`;
    await page.locator('canvas').first().screenshot({ path: path.join(OUTDIR, name + '.png') });
    state.image = name + '.png';
    state.creasePercent = pct;
    state.width = W; state.height = H;
    renders.push(state);
    console.log('rendered', name);
  }
  fs.writeFileSync(path.join(OUTDIR, 'renders.json'), JSON.stringify(renders));

  await browser.close();
  server.kill();
  console.log('done ->', OUTDIR);
})().catch(e => { console.error(e); process.exit(1); });
