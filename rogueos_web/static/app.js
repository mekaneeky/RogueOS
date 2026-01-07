const THREE = window.THREE;
const OrbitControls = window.THREE.OrbitControls;

const API_BASE = '';
const PALETTE = {
  bg: '#010402',
  accent: '#0aff9d',
  wire: '#0aff9d',
  file: '#0affd0',
  dir: '#3cff8c',
  link: '#63ffcb',
  container: '#1eff64',
  npc: '#9cfffb',
};

const state = {
  currentDir: null,
  nodes: new Map(),
  floatingGroups: [],
  rootId: null,
  clock: new THREE.Clock(),
  hovered: null,
  selected: null,
  searchCache: [],
  frameLogged: false,
  rootLogged: false,
};

const statusEl = document.querySelector('#status');
const breadcrumbsEl = document.querySelector('#breadcrumbs');
const infoPanel = document.querySelector('#info-panel');
const infoContent = document.querySelector('#info-content');
const infoClose = document.querySelector('#info-close');
const searchInput = document.querySelector('#search-input');
const resetBtn = document.querySelector('#reset-view');
const debugLogEl = document.querySelector('#debug-log');
const loadingHint = document.querySelector('#loading-hint');

if (!THREE) {
  throw new Error('Three.js failed to load');
}

const MAX_LOG_ENTRIES = 60;

function logDebug(message, payload) {
  const ts = new Date().toISOString().split('T')[1]?.replace('Z', '') ?? '';
  const entryText = payload !== undefined ? `${message} :: ${JSON.stringify(payload)}` : message;
  console.log(`[AstralGUI ${ts}] ${message}`, payload ?? '');
  if (!debugLogEl) return;
  const entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.innerHTML = `<pre>[${ts}] ${entryText}</pre>`;
  debugLogEl.appendChild(entry);
  while (debugLogEl.children.length > MAX_LOG_ENTRIES) {
    debugLogEl.removeChild(debugLogEl.firstChild);
  }
  debugLogEl.scrollTop = debugLogEl.scrollHeight;
}

const scene = new THREE.Scene();
scene.background = new THREE.Color(PALETTE.bg);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
const initRenderer = () => {
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(new THREE.Color(PALETTE.bg), 1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  document.body.appendChild(renderer.domElement);
  loadingHint?.classList.add('hidden');
  logDebug('renderer:init', {
    pixelRatio: window.devicePixelRatio,
    size: { width: window.innerWidth, height: window.innerHeight },
  });

  const glContext = renderer.getContext();
  logDebug('renderer:context', {
    hasContext: !!glContext,
    contextType: glContext ? (glContext instanceof WebGL2RenderingContext ? 'WebGL2' : 'WebGL1') : 'none',
  });
  if (!glContext) {
    setStatus('WebGL context unavailable.');
  }
};

const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 300);
camera.position.set(0, 32, 54);
logDebug('camera:init', { position: camera.position });

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.07;
controls.minDistance = 6;
controls.maxDistance = 120;
controls.enablePan = false;
logDebug('controls:init', { damping: controls.enableDamping });

const majorGridColor = new THREE.Color(PALETTE.wire);
const minorGridColor = new THREE.Color(PALETTE.wire).multiplyScalar(0.35);
const gridHelper = new THREE.GridHelper(240, 48, majorGridColor, minorGridColor);
gridHelper.material.transparent = true;
gridHelper.material.opacity = 0.22;
if (gridHelper.material2) {
  gridHelper.material2.transparent = true;
  gridHelper.material2.opacity = 0.08;
}
gridHelper.position.y = -0.01;
scene.add(gridHelper);

const verticalLines = createMatrixColumns(24, 90, 120);
scene.add(verticalLines);

const matrixRain = createMatrixRain(700);
matrixRain.position.y = 40;
scene.add(matrixRain);

const nodesGroup = new THREE.Group();
scene.add(nodesGroup);

initRenderer();
logDebug('scene:setup-complete');

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

infoClose.addEventListener('click', () => infoPanel.classList.add('hidden'));
resetBtn.addEventListener('click', () => resetCamera());

renderer.domElement.addEventListener('pointermove', onPointerMove);
renderer.domElement.addEventListener('pointerleave', () => setHovered(null));
renderer.domElement.addEventListener('pointerdown', onPointerDown);

window.addEventListener('resize', onResize);
window.addEventListener('keydown', onKey);
searchInput.addEventListener('keydown', onSearchKey);

animate();
bootstrap();

window.addEventListener('error', (event) => {
  logDebug('window:error', { message: event.message, filename: event.filename, lineno: event.lineno, colno: event.colno });
});

window.addEventListener('unhandledrejection', (event) => {
  logDebug('window:unhandledrejection', { reason: String(event.reason) });
});

async function bootstrap() {
  logDebug('bootstrap:start', { root: state.rootId });
  setStatus('Loading root…');
  try {
    const data = await fetchJSON('/api/root');
    if (!data) {
      setStatus('Failed to load root.');
      logDebug('bootstrap:error:empty-response');
      return;
    }
    state.rootId = data.id;
    logDebug('bootstrap:root-loaded', { id: data.id, path: data.path, childCount: data.children?.length ?? 0 });
    await applyDirectory(data);
    setStatus('Ready. Select wireframes to explore.');
    logDebug('bootstrap:ready');
  } catch (err) {
    console.error(err);
    setStatus('Failed to load web renderer.');
    logDebug('bootstrap:error', { error: String(err?.message ?? err) });
  }
}

async function fetchJSON(path) {
  logDebug('fetch:start', { path });
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    logDebug('fetch:http-error', { path, status: res.status, statusText: res.statusText });
    throw new Error(`${res.status} ${res.statusText}`);
  }
  const json = await res.json();
  logDebug('fetch:success', { path, keys: Object.keys(json ?? {}) });
  return json;
}

async function loadDirectory(id) {
  if (!id) {
    logDebug('loadDirectory:missing-id');
    return;
  }
  logDebug('loadDirectory:start', { id });
  setStatus('Loading…');
  const data = await fetchJSON(`/api/dir?id=${encodeURIComponent(id)}`);
  await applyDirectory(data);
  setStatus(`${data.children.length} astral node${data.children.length === 1 ? '' : 's'}.`);
  logDebug('loadDirectory:done', { id, childCount: data.children.length });
}

async function applyDirectory(data) {
  logDebug('applyDirectory:start', { id: data?.id, children: data?.children?.length });
  state.currentDir = data;
  state.hovered = null;
  state.selected = null;
  nodesGroup.clear();
  state.floatingGroups.length = 0;
  state.nodes.clear();

  if (data.children.length === 0) {
    setStatus('This chamber is empty.');
    logDebug('applyDirectory:empty');
  }

  data.children.forEach((child, idx) => {
    const group = createNodeGroup(child, idx);
    nodesGroup.add(group);
    state.nodes.set(child.id, group);
    state.floatingGroups.push(group);
    const link = createLinkColumn(group);
    if (link) {
      group.add(link);
    }
    logDebug('applyDirectory:node-added', { id: child.id, kind: child.kind, position: group.position });
  });

  updateBreadcrumbs(data.breadcrumbs ?? []);
  logDebug('applyDirectory:complete', { id: data.id, totalNodes: nodesGroup.children.length });
}

function createNodeGroup(node, index) {
  logDebug('createNodeGroup', { id: node.id, kind: node.kind, index });
  const group = new THREE.Group();
  const basePosition = computeNodePosition(node, index);
  group.position.copy(basePosition);

  const sizeSeed = hashFloat(node.id, 5);
  const width = 1.8 + sizeSeed * 1.2;
  const height = (node.kind === 'Directory' ? 5.2 : 3.0) + sizeSeed * (node.kind === 'Directory' ? 3.6 : 1.8);
  const geometry = new THREE.BoxGeometry(width, height, width);
  const color = new THREE.Color(kindColor(node.kind));

  const fillMaterial = new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 0.12,
    depthWrite: false,
  });
  const fillMesh = new THREE.Mesh(geometry, fillMaterial);
  fillMesh.position.y = height * 0.5;
  fillMesh.renderOrder = 0;
  group.add(fillMesh);

  const wireGeometry = new THREE.WireframeGeometry(geometry);
  const wireMaterial = new THREE.LineBasicMaterial({
    color,
    transparent: true,
    opacity: 0.9,
  });
  const wireframe = new THREE.LineSegments(wireGeometry, wireMaterial);
  wireframe.position.y = height * 0.5;
  wireframe.renderOrder = 1;
  group.add(wireframe);

  const billboard = createBillboard(node, height);
  group.add(billboard);

  const phase = hashFloat(node.id, 9) * Math.PI * 2;
  group.userData = {
    node,
    basePosition,
    floatPhase: phase,
    floatSpeed: 0.35 + hashFloat(node.id, 11) * 0.4,
    baseScale: 1,
    towerHeight: height,
    wireMaterial,
    fillMaterial,
  };
  return group;
}

function computeNodePosition(node, idx) {
  const t = node.transform?.position ?? { x: 0, y: 0, z: 0 };
  const px = t.x ?? 0;
  const pz = t.y ?? 0;
  const jitterX = (hashFloat(node.id, 17) - 0.5) * 1.2;
  const jitterZ = (hashFloat(node.id, 19) - 0.5) * 1.2;
  return new THREE.Vector3(px + jitterX, 0, pz + jitterZ);
}

function createBillboard(node, towerHeight = 3.2) {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 64;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = 'rgba(1,4,2,0.78)';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = 'rgba(10,255,157,0.35)';
  ctx.lineWidth = 2;
  ctx.strokeRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#0aff9d';
  ctx.font = '20px "IBM Plex Mono", monospace';
  ctx.fillText(node.name, 12, 28);
  ctx.font = '14px "IBM Plex Mono", monospace';
  ctx.fillStyle = 'rgba(10,255,157,0.7)';
  ctx.fillText(node.kind, 12, 48);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = renderer.capabilities.getMaxAnisotropy();

  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthWrite: false,
  });
  const sprite = new THREE.Sprite(material);
  sprite.position.set(0, towerHeight + 1.4, 0);
  sprite.scale.set(6.5, 1.8, 1);
  return sprite;
}

function createLinkColumn(group) {
  if (!group?.userData) return null;
  const height = group.userData.towerHeight ?? 3;
  const geometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(0, height, 0),
  ]);
  const material = new THREE.LineBasicMaterial({
    color: new THREE.Color(PALETTE.wire).multiplyScalar(0.9),
    transparent: true,
    opacity: 0.22,
    depthWrite: false,
  });
  const column = new THREE.Line(geometry, material);
  column.userData = { wireMaterial: material };
  if (!group.userData) group.userData = {};
  group.userData.columnMaterial = material;
  return column;
}

function createMatrixColumns(columnCount, radius, height) {
  const group = new THREE.Group();
  for (let i = 0; i < columnCount; i++) {
    const angle = (i / columnCount) * Math.PI * 2;
    const x = Math.cos(angle) * radius;
    const z = Math.sin(angle) * radius;
    const geometry = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(x, -height * 0.5, z),
      new THREE.Vector3(x, height * 0.5, z),
    ]);
    const baseOpacity = 0.08 + (i % 5) * 0.035;
    const material = new THREE.LineBasicMaterial({
      color: new THREE.Color(PALETTE.wire).multiplyScalar(0.6 + (i % 4) * 0.08),
      transparent: true,
      opacity: baseOpacity,
      depthWrite: false,
    });
    const line = new THREE.Line(geometry, material);
    line.userData = {
      pulseOffset: Math.random() * Math.PI * 2,
      pulseSpeed: 0.6 + Math.random() * 0.6,
      baseOpacity,
      material,
    };
    group.add(line);
  }
  return group;
}

function createMatrixRain(count) {
  const width = 180;
  const depth = 180;
  const height = 140;
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(count * 3);
  const speeds = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    positions[i * 3] = (Math.random() - 0.5) * width;
    positions[i * 3 + 1] = Math.random() * height;
    positions[i * 3 + 2] = (Math.random() - 0.5) * depth;
    speeds[i] = 14 + Math.random() * 18;
  }
  const positionAttr = new THREE.BufferAttribute(positions, 3);
  positionAttr.setUsage(THREE.DynamicDrawUsage);
  geometry.setAttribute('position', positionAttr);
  const material = new THREE.PointsMaterial({
    color: new THREE.Color(PALETTE.wire),
    size: 0.7,
    transparent: true,
    opacity: 0.55,
    depthWrite: false,
  });
  const points = new THREE.Points(geometry, material);
  points.userData = {
    width,
    depth,
    height,
    speeds,
  };
  points.frustumCulled = false;
  return points;
}

function updateMatrixRain(points, delta) {
  if (!points?.geometry?.attributes?.position) return;
  const speeds = points.userData?.speeds;
  const height = points.userData?.height ?? 120;
  const width = points.userData?.width ?? 160;
  const depth = points.userData?.depth ?? 160;
  if (!speeds) return;
  const positions = points.geometry.attributes.position;
  const array = positions.array;
  for (let i = 0; i < speeds.length; i++) {
    const idx = i * 3;
    array[idx + 1] -= speeds[i] * delta;
    if (array[idx + 1] < -height * 0.5) {
      array[idx + 1] = height * 0.5;
      array[idx] = (Math.random() - 0.5) * width;
      array[idx + 2] = (Math.random() - 0.5) * depth;
    }
  }
  positions.needsUpdate = true;
}

function kindColor(kind) {
  switch (kind) {
    case 'Directory': return PALETTE.dir;
    case 'File': return PALETTE.file;
    case 'Symlink': return PALETTE.link;
    case 'Container': return PALETTE.container;
    case 'NPC': return PALETTE.npc;
    default: return PALETTE.accent;
  }
}

function hashFloat(str, salt = 0) {
  let h = 2166136261 ^ salt;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return ((h >>> 0) / 4294967295) % 1;
}

function animate() {
  requestAnimationFrame(animate);
  const delta = state.clock.getDelta();
  const elapsed = state.clock.elapsedTime;
  if (!state.rootLogged) {
    logDebug('animate:tick', { elapsed });
    state.rootLogged = true;
  }

  verticalLines.rotation.y += delta * 0.08;
  verticalLines.children.forEach((line) => {
    const data = line.userData;
    if (!data?.material) return;
    const pulse = (Math.sin(elapsed * data.pulseSpeed + data.pulseOffset) + 1) * 0.5;
    data.material.opacity = data.baseOpacity * (0.7 + pulse * 0.6);
  });

  if (gridHelper.material) {
    gridHelper.material.opacity = 0.16 + Math.sin(elapsed * 0.25) * 0.04;
  }
  if (gridHelper.material2) {
    gridHelper.material2.opacity = 0.05 + Math.cos(elapsed * 0.22) * 0.02;
  }

  updateMatrixRain(matrixRain, delta);

  state.floatingGroups.forEach((group) => {
    const data = group.userData ?? {};
    const base = data.basePosition ?? new THREE.Vector3();
    const phase = data.floatPhase ?? 0;
    const speed = data.floatSpeed ?? 0.5;
    const flicker = (Math.sin(elapsed * speed + phase) + 1) * 0.5;
    group.position.copy(base);
    group.rotation.y = Math.sin(elapsed * 0.18 + phase) * 0.06;
    const scale = data.baseScale ?? 1;
    const hoverBoost = data.isHovered ? 1.35 : 1.0;
    group.scale.setScalar(scale * hoverBoost * (0.95 + flicker * 0.08));
    if (data.wireMaterial) {
      data.wireMaterial.opacity = (data.isHovered ? 0.65 : 0.4) + flicker * 0.35;
    }
    if (data.fillMaterial) {
      data.fillMaterial.opacity = 0.02 + flicker * 0.07;
    }
    if (data.columnMaterial) {
      data.columnMaterial.opacity = (data.isHovered ? 0.45 : 0.18) + flicker * 0.25;
    }
  });

  controls.update();
  renderer.render(scene, camera);
  if (!state.frameLogged) {
    logDebug('render:first-frame', { elapsed });
    state.frameLogged = true;
  }
}

function onResize() {
  const { innerWidth, innerHeight } = window;
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
}

function onPointerMove(event) {
  pointer.x = (event.clientX / renderer.domElement.clientWidth) * 2 - 1;
  pointer.y = -(event.clientY / renderer.domElement.clientHeight) * 2 + 1;

  raycaster.setFromCamera(pointer, camera);
  const intersects = raycaster.intersectObjects(nodesGroup.children, true);
  for (const hit of intersects) {
    const group = findNodeGroup(hit.object);
    if (group) {
      setHovered(group);
      return;
    }
  }
  setHovered(null);
}

function onPointerDown(event) {
  if (event.button !== 0) {
    return;
  }
  logDebug('pointer:down', { x: event.clientX, y: event.clientY });
  pointer.x = (event.clientX / renderer.domElement.clientWidth) * 2 - 1;
  pointer.y = -(event.clientY / renderer.domElement.clientHeight) * 2 + 1;

  raycaster.setFromCamera(pointer, camera);
  const intersects = raycaster.intersectObjects(nodesGroup.children, true);
  if (!intersects.length) {
    setSelected(null);
    infoPanel.classList.add('hidden');
    logDebug('pointer:down:no-hit');
    return;
  }
  const group = findNodeGroup(intersects[0].object);
  if (!group) return;
  const node = group.userData.node;
  logDebug('pointer:down:hit', { id: node.id, kind: node.kind });
  setSelected(group);
  if (node.kind === 'Directory') {
    loadDirectory(node.id);
  } else {
    showInfo(node);
  }
}

function onKey(event) {
  if (event.key === 'Escape') {
    infoPanel.classList.add('hidden');
    setSelected(null);
  }
}

function onSearchKey(event) {
  if (event.key !== 'Enter') {
    return;
  }
  const needle = event.target.value.trim();
  if (!needle) {
    infoPanel.classList.add('hidden');
    return;
  }
  runSearch(needle);
}

async function runSearch(needle) {
  setStatus(`Searching "${needle}"…`);
  try {
    const result = await fetchJSON(`/api/search?q=${encodeURIComponent(needle)}&limit=40`);
    setStatus(`${result.results.length} matches.`);
     logDebug('search:results', { needle, count: result.results.length });
    if (!result.results.length) {
      showSearchResults(needle, []);
    } else {
      showSearchResults(needle, result.results);
    }
  } catch (err) {
    console.error(err);
    setStatus('Search failed.');
    logDebug('search:error', { needle, error: String(err?.message ?? err) });
  }
}

function showSearchResults(needle, results) {
  infoPanel.classList.remove('hidden');
  const frag = document.createDocumentFragment();
  const title = document.createElement('h2');
  title.textContent = `Search: ${needle}`;
  frag.appendChild(title);
  if (!results.length) {
    const empty = document.createElement('p');
    empty.textContent = 'No astral echoes found.';
    frag.appendChild(empty);
  } else {
    const list = document.createElement('div');
    list.className = 'search-results';
    results.forEach((row) => {
      const item = document.createElement('div');
      item.className = 'search-item';
      item.textContent = `${row.kind} — ${row.path}`;
      item.addEventListener('click', () => {
        infoPanel.classList.add('hidden');
        const dirId = row.kind === 'Directory' ? row.id : row.parent;
        if (dirId) {
          loadDirectory(dirId);
        }
      });
      list.appendChild(item);
    });
    frag.appendChild(list);
  }
  infoContent.replaceChildren(frag);
}

function showInfo(node) {
  infoPanel.classList.remove('hidden');
  const frag = document.createDocumentFragment();
  const title = document.createElement('h2');
  title.textContent = node.name;
  frag.appendChild(title);

  const dl = document.createElement('dl');
  addPair(dl, 'Kind', node.kind);
  addPair(dl, 'Path', node.path);
  if (node.seed) {
    addPair(dl, 'Seed', node.seed);
  }
  if (node.theme) {
    addPair(dl, 'Theme', node.theme);
  }
  addPair(dl, 'Pinned', node.pinned ? 'yes' : 'no');
  if (node.parent && node.parent !== state.currentDir?.id) {
    const jump = document.createElement('div');
    jump.className = 'search-results';
    const btn = document.createElement('div');
    btn.className = 'search-item';
    btn.textContent = 'Reveal parent chamber';
    btn.addEventListener('click', () => {
      infoPanel.classList.add('hidden');
      loadDirectory(node.parent);
    });
    jump.appendChild(btn);
    frag.appendChild(jump);
  }
  frag.appendChild(dl);
  infoContent.replaceChildren(frag);
}

function addPair(dl, label, value) {
  const dt = document.createElement('dt');
  dt.textContent = label;
  const dd = document.createElement('dd');
  dd.textContent = value;
  dl.appendChild(dt);
  dl.appendChild(dd);
}

function updateBreadcrumbs(crumbs) {
  breadcrumbsEl.replaceChildren();
  crumbs.forEach((crumb, idx) => {
    const span = document.createElement('span');
    span.textContent = idx === 0 ? 'root' : crumb.name;
    if (idx === crumbs.length - 1) {
      span.style.opacity = '1';
    } else {
      span.addEventListener('click', () => loadDirectory(crumb.id));
    }
    breadcrumbsEl.appendChild(span);
    if (idx !== crumbs.length - 1) {
      const sep = document.createElement('span');
      sep.style.opacity = '0.45';
      sep.textContent = '／';
      breadcrumbsEl.appendChild(sep);
    }
  });
}

function findNodeGroup(object) {
  let current = object;
  while (current && current !== nodesGroup) {
    if (state.nodes.has(current.userData?.node?.id)) {
      return current;
    }
    current = current.parent;
  }
  return null;
}

function setHovered(group) {
  if (state.hovered === group) return;
  if (state.hovered?.userData) {
    state.hovered.userData.isHovered = false;
  }
  state.hovered = group ?? null;
  if (group?.userData) {
    group.userData.isHovered = true;
    setStatus(`${group.userData.node.kind}: ${group.userData.node.name}`);
  } else if (state.currentDir) {
    setStatus(`${state.currentDir.children.length} astral node${state.currentDir.children.length === 1 ? '' : 's'}.`);
  }
}

function setSelected(group) {
  state.selected = group;
}

function setStatus(text) {
  statusEl.textContent = text;
}

function resetCamera() {
  camera.position.set(0, 32, 54);
  controls.target.set(0, 0, 0);
  controls.update();
}
