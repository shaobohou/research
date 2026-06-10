# Notes: Reproducing OrigamiSimulator physics (JAX) + rendering (NumPy)

Goal: reimplement amandaghassaei/OrigamiSimulator's
1. physics-based folding solver (GPU/GLSL compliant-dynamics solver) in JAX (fast when jitted)
2. the Three.js rendering in pure NumPy, close to pixel-perfect vs the original.

Original repo: https://github.com/amandaghassaei/OrigamiSimulator (MIT license), cloned to /tmp/OrigamiSimulator.

## Understanding the original

### Physics (js/dynamic/dynamicSolver.js + GLSL shaders in index.html)
Compliant dynamics solver (Ghassaei et al., "Fast, Interactive Origami Simulation using GPU Computation", 7OSME 2018).
State lives in float textures; one fragment shader pass per stage, per step:

1. `normalCalc`: per-face unit normal from last positions (`normalize(cross(b-a, c-a))`).
2. `thetaCalc`: per-crease dihedral angle. `x = clamp(dot(n1,n2),-1,1)`,
   `y = dot(cross(n1, creaseVec), n2)` with `creaseVec = normalize(p(node1)-p(node0))`
   (edge nodes in order), `theta = atan2(y,x)`, then unwrap vs lastTheta
   (if diff < -5 add 2pi, if diff > 5 subtract 2pi). Disabled creases keep lastTheta.
3. `updateCreaseGeo`: per-crease [h1, h2, coef1, coef2]:
   creaseVector = p4 - p3 (p3,p4 = edge nodes; p1,p2 = opposite vertices of the 2 adjacent faces),
   h_i = distance of p_i from the (infinite) crease line, coef_i = proj_i/creaseLength
   (projection of p_i-p3 onto unit crease vector / crease length).
   Crease disabled (flag -1) if creaseLength < 1e-6 or h_i < 1e-6.
4. `velocityCalc` (Euler, the default integrator): per-node force =
   - external force (0 by default)
   - axial beams: for each incident edge, `deltaP = pj - pi` (absolute positions),
     `F += deltaP*(1 - L0/|deltaP|)*K + (vj - vi)*D`,
     K = axialStiffness/L0 (per beam), D = percentDamping*2*sqrt(K*min(mass)).
   - creases: angForce = k_crease*(targetTheta*creasePercent - theta);
     k_crease = creaseStiffness*L (type=1, fold) or panelStiffness*L (type=0, facet);
     node1 (opp. vertex face1): F += angForce/h1*n1
     node2: F += angForce/h2*n2
     edge node3: F += -angForce*((1-coef1)/h1*n1 + (1-coef2)/h2*n2)
     edge node4: F += -angForce*(coef1/h1*n1 + coef2/h2*n2)
     (skip if crease disabled)
   - faces (angular springs on the 3 triangle angles toward nominal flat angles):
     anglesDiff = (nominalAngles - angles)*faceStiffness, then per-vertex forces using
     cross(normal, edgeUnitVec)/edgeLen terms (see shader; exact form copied into solver.py).
   Then `v += F*dt/mass`, fixed nodes v=0.
5. `positionCalc`: `p += v*dt`, fixed nodes hold position.

All forces are computed from *last* positions/velocities (Jacobi style) -> trivially
vectorizable: per-edge/per-crease/per-face quantities + scatter-add to nodes.

dt = 0.9/(2*pi*maxNaturalFreq), naturalFreq = sqrt(K/minMass) per beam. mass = 1 per node.
Defaults (globals.js): creasePercent 0.6, axialStiffness 20, creaseStiffness 0.7,
panelStiffness 0.7, faceStiffness 0.2, percentDamping 0.45, integrationType "euler",
numSteps 100 per frame. No nodes fixed, no external forces, no gravity.

Geometry setup (model.js): FOLD file -> triangulated (pattern.js), positions centered
(geometry.center(), i.e. subtract bounding-box center) and scaled by 1/boundingSphere.radius
(radius = max dist from bbox center). Creases come from creaseParams
[face1Ind, vert1Ind(opposite v on face1), face2Ind, vert2Ind, edgeInd, angle(deg)] for
edges with assignment M/V/F. Face order convention in getFacesAndVerticesForEdges:
face1 = the face where the edge appears in *reverse* winding order
(if v2 follows v1 in the face winding, faces are swapped).
The solver tracks displacement from original position; equivalent to absolute positions.

NOTE: thetaCalc theta unwrap uses theta from *current* normals but lastTheta storage;
w (angular velocity) output but unused (damping term on crease commented out in shader).

### Rendering (threeView.js + model.js), three.js r87
- PerspectiveCamera fov 60, near 0.1, far 500, zoom 7, aspect = w/h.
  Position (5,5,5), lookAt origin, up (0,1,0) (TrackballControls.reset(Vector3(1,1,1))
  keeps |pos| and sets direction -> stays (5,5,5)).
- Background white. 6 DirectionalLights (white): intensity .8 at (0,100,0),
  .3 at (0,-100,0), .8 at (100,-30,0), .8 at (-100,-30,0), .3 at (0,30,100), .3 at (0,30,-100).
- Mesh: front MeshPhongMaterial flatShading side=FrontSide color #ec008b,
  back MeshPhongMaterial flatShading side=BackSide color #dddddd; both with
  polygonOffset factor 0.5 units 1. Phong defaults: specular #111111, shininess 30.
- Lines: LineBasicMaterial black 1px, same position buffer, indexed per assignment;
  visible by default: M, V, B (panels/facets F and unassigned U hidden).
- renderer antialias=true (MSAA), no gamma correction in r87 by default, no tonemapping.
- r87 lighting math (BlinnPhong, PHYSICALLY_CORRECT_LIGHTS off):
  diffuse += dotNL * lightColor * materialColor
  specular += dotNL * lightColor * F_Schlick(spec, dotLH) * 0.25 * (shininess*0.5+1) * pow(dotNH, shininess)
  F_Schlick = spec + (1-spec)*2^((-5.55473*dotLH-6.98316)*dotLH); H = normalize(L+V) per fragment.
  flatShading derives normal from screen-space derivatives = geometric face normal (sign per facing).

## Ground truth strategy
- playwright-core + chromium-headless-shell (installed at /opt/pw-browsers) runs the
  *actual* original app (SwiftShader WebGL). Serve /tmp/OrigamiSimulator via http.server.
- Extract via page.evaluate: processed triangulated fold, creaseParams, scaled node
  positions, solver params, camera matrices; pause sim, reset(), step(N) deterministically,
  dump positions; screenshot canvas for renderer reference.

## Log
- Cloned repo, read dynamicSolver.js, all GLSL shaders, model.js, beam/crease/node.js,
  pattern.js (processFold, getFacesAndVerticesForEdges, triangulatePolys), importer.js,
  threeView.js, globals.js. Confirmed three.js r87, default model huffmanWaterbomb.svg,
  `globals` is a window global -> extraction via page.evaluate is easy.
- Installed playwright-core + chromium-headless-shell 148 in /tmp + /opt/pw-browsers.
- Headless WebGL works with --enable-unsafe-swiftshader --use-angle=swiftshader.
  The startup demo-link auto-click is racy headless; calling
  globals.importer.importDemoFile(...) directly (with retry) is reliable.
- Canvas screenshots include the DOM UI on top -> remove all body children that
  don't contain the canvas before screenshotting (the firsttime helper tooltip
  appears on a delay, remove again right before shots).
- Physics validation (compare_physics.py): trajectory dumps at steps 1/10/100/500/1000.
  - waterbomb (440 nodes): max err 8e-8 (step 1) ... 2e-5 (step 1000) -> bit-faithful.
  - boxpleat (2704 nodes, via standalone load_fold): 7e-9 (step 1) ... 5e-5 (step 1000).
  - crane (60 nodes, SVG import): 3e-4 transient max, 6e-5 at equilibrium. Larger
    transient error than the others; consistent with fp32 cancellation in 1/h moment
    arms for the near-degenerate crease geometry this SVG produces (GPU mediump vs
    CPU float32) - converges to the same equilibrium.
  - benchmark (jitted, CPU): crane 80us/step, waterbomb 207us/step, boxpleat 1.3ms/step.
- Render validation (compare_render.py, exact positions+camera from the browser dump):
  - first try (4x4 supersampling): 96-99% pixels exactly identical; ALL residual
    error on 1px edges (AA pattern mismatch), interiors exact -> shading math right.
  - switched to true 4-sample MSAA emulation (per-sample coverage+depth, per-pixel
    center shading). Vulkan standard sample pattern *y-flipped* matches chromium/
    SwiftShader best: crane 97.5-99.1% exact, 99.4-99.7% within +-2; waterbomb
    92-97% exact (denser line coverage), 98-99.1% within +-2.
  - line-rule variants (caps, strict bounds) made no measurable difference;
    leftover diffs are sparse single pixels along the black lines.
- Full pipeline (JAX positions -> NumPy render vs original screenshots):
  96.8-98.8% exact, >=99.4% within +-2 on the crane; waterbomb similar to
  renderer-only numbers (solver error invisible at pixel scale).
- BUG found & fixed in standalone load_fold: I initially had crease face1/face2
  inverted (all 7701 boxpleat creases had node1/node2 swapped vs the original's
  creaseParams; folding crumpled). pattern.js getFacesAndVerticesForEdges checks the
  *second* adjacent face: if the edge v1->v2 is forward in its winding, that face
  becomes face1. After fix: 0 differing crease entries, trajectory bit-faithful.
- Quad triangulation in the original splits along the *shorter diagonal*
  (not a fan) - matched in load_fold.
- Stress tests (looking for models with bigger differences): hypar (chaotic,
  all-facet), Bistable/curvedPleatSimple, langOrchid (complex SVG) all match
  *tighter* than the crane (error after 3000 steps 1e-6..7e-6 relative across
  0/30/60/90%, pixels 93-99% exact). Bistability doesn't split the solvers
  because both follow the same deterministic ramp from the same flat reset.
- crane at 99% fold: worst finite physics case, 1.6e-3 relative max error
  (collapsing creases -> tiny moment arms -> fp32 sensitivity); render still
  97.9% exact.
- REAL divergence found: needsCollisions/rose.svg. The ORIGINAL GPU solver
  NaNs at step <=1 (positions read back as 2^127 float garbage; reference
  screenshots render a blank canvas). Cause: the SVG import produces 27
  exactly-degenerate triangles (area ~1e-11, |dot| = 1.0 to 10 decimals);
  in fp32 the dot rounds slightly above 1 and the face-constraint shader's
  acos() is UNCLAMPED in the original (thetaCalc clamps, velocityCalc's face
  angles don't) -> NaN forces -> whole state NaN in one step. Our JAX port
  clips acos inputs to [-1,1] and stays stable (max|p| ~ 0.95 over 3000 steps,
  plausible crumpled rose). So the only model with a "significant difference"
  is one where the original itself breaks down.
- Multi-view comparison (extract_views.js / compare_views.py): iso + six axis
  views x 5 models at 60% fold, all using setCameraX/Y/Z/Iso (TrackballControls
  reset keeps the sqrt(75) orbit radius -> axis cams at +-8.66). All 35 views
  agree 89.6-99.5% exact, >=97.1% within +-2. Side views best; top/bottom worst
  (full crease grid on screen; 99.5% of >2-off pixels lie on the 1px lines).
  Top/bottom views needed r87 Matrix4.lookAt's degenerate-up nudge
  (z.z += 1e-4 when up || view dir) added to look_at_inverse; analytic camera
  matches all dumped matrices to 1e-5. Front/back material switch verified
  (top all pink, bottom all gray).
- Convergence check: the 3000-step "settle" used throughout (matching the
  extraction protocol) is NOT full convergence - residual max|v| 1e-3..3e-2,
  and 3k->9k steps still drifts geometry by up to 6e-1 of extent (hypar 90%).
  hypar@90% truly converges by ~30k steps (max|v| 5e-6, then zero drift);
  crane@60% never converges (max|v| oscillates 5e-3..3e-2 even at 100k steps -
  sustained ringing from near-degenerate creases around the disable threshold;
  no static equilibrium exists). Comparisons are unaffected: both solvers ran
  the identical reset + N-step protocol, so all fidelity numbers compare
  matched mid-relaxation states (a stricter, trajectory-level test).
