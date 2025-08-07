/* static/script.js – kiosk runtime (v4.7)  */

// Element cache
const controls = document.getElementById('controls');
const nextBtn  = document.getElementById('nextBtn');
const stopBtn  = document.getElementById('stopBtn');
const imgEl    = document.getElementById('stepImg');
const compNameEl = document.getElementById('compName');
const labelEl  = document.getElementById('stepLabel');
const statusEl = document.getElementById('stepCounter');

// Session state
let session = null;
let seq     = [];
let idx     = -1;

// Component data maps
let compImgMap = {};  // { id: 'image.png' }
let compNameMap = {}; // { id: 'Component Name' }

// Foot pedal / space bar listener
document.addEventListener('DOMContentLoaded', () => {
  let spacePressStart = null;
  let spaceHoldTimer  = null;
  document.addEventListener('keydown', e => {
    if (e.code === 'Space' && !spacePressStart) {
      spacePressStart = Date.now();
      spaceHoldTimer = setTimeout(() => {
        if (stopBtn && !stopBtn.disabled && !stopBtn.hidden) stopBtn.click();
      }, 10000);
    }
  });
  document.addEventListener('keyup', e => {
    if (e.code === 'Space') {
      if ((Date.now() - spacePressStart) < 10000) {
        if (nextBtn && !nextBtn.disabled && !nextBtn.hidden) nextBtn.click();
      }
      clearTimeout(spaceHoldTimer);
      spacePressStart = null;
    }
  });
});

/* ---------- Helpers --------------------------------------------------- */
const sleep  = ms => new Promise(r => setTimeout(r, ms));
const jFetch = (url, data) =>
  fetch(url, {
    method : 'POST',
    headers: { 'Content-Type':'application/json' },
    body   : JSON.stringify(data)
  });

/* ---------- Primary Application Flow ---------------------------------- */
async function waitForJob () {
  while (true) {
    const queue = await fetch('/api/pending').then(r => r.json());
    if (queue.length) {
      const sid  = queue[0].session_id;
      const resp = await jFetch('/api/claim', { session_id: sid });
      if (resp.ok) return resp.json();
    }
    await sleep(2000);
  }
}

function showStep(i) {
  const step = seq[i] ?? {};
  
  // Update component name, instruction label, and step counter
  compNameEl.textContent = compNameMap[step.comp] || '-';
  labelEl.textContent  = step.label ?? '';
  statusEl.textContent = `Step ${i + 1} / ${seq.length}`;

  // Update image
  const imgFile = compImgMap[step.comp];
  imgEl.src = imgFile ? `/comp_assets/${step.comp}/${imgFile}` : '';
  imgEl.hidden = !imgFile;

  nextBtn.textContent = (i === seq.length - 1) ? 'Review' : 'Next Step';
}

function send(action, extra = {}) {
  return jFetch('/api/progress', { action, session_id: session.session_id, ...extra });
}

async function advance() {
  idx++;
  if (idx < seq.length) {
    showStep(idx);
    await send('next', { component: seq[idx].comp });
  } else {
    nextBtn.disabled = stopBtn.disabled = true;
    labelEl.textContent = 'Preparing summary…';
    await send('finish');
    await sleep(200);
    location.href = `/session/${session.session_id}`;
  }
}

async function abort() {
  if (!confirm('Interrupt this assembly?')) return;
  nextBtn.disabled = stopBtn.disabled = true;
  labelEl.textContent = 'Aborting…';
  await send('abort', { step: idx });
  await sleep(300);
  location.reload();
}

/* ---------- Bootstrap on Page Load ------------------------------------ */
(async () => {
  // 1. Fetch component data first to build our lookup maps
  const components = await fetch('/components/json').then(r => r.json());
  compImgMap = Object.fromEntries(components.filter(c => c.image).map(c => [c.id, c.image]));
  compNameMap = Object.fromEntries(components.map(c => [c.id, c.name]));

  // 2. Wait for a session to be assigned
  const data = await waitForJob();
  session = data.session;
  seq     = data.sequence;

  // 3. Populate the structured header with session details
  document.getElementById('metaProject').textContent = session.project;
  document.getElementById('metaStack').textContent = session.stack_id;
  document.getElementById('metaOperator').textContent = session.operator;

  // 4. Show controls and wire up events
  controls.style.display = 'flex';
  nextBtn.addEventListener('click', advance);
  stopBtn.addEventListener('click', abort);

  // 5. Kick off the first step
  advance();
})();