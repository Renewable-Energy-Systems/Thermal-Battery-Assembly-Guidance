/*  static/script.js – kiosk runtime (v6.1)  */

/* ---------- DOM refs ------------------------------------------------ */
const controls  = document.getElementById('controls');
const nextBtn   = document.getElementById('nextBtn');
const stopBtn   = document.getElementById('stopBtn');
const imgEl     = document.getElementById('stepImg');
const compEl    = document.getElementById('compName');   // <h2> in card
const labelEl   = document.getElementById('stepLabel');
const statusEl  = document.getElementById('status');
const prevGhost = document.getElementById('prevCard');
const nextGhost = document.getElementById('nextCard');

/* ---------- runtime state ------------------------------------------ */
let session = null;
let seq     = [];
let idx     = -1;

const compName = Object.create(null);   // id → human name
const compImg  = Object.create(null);   // id → preview filename

/* ---------- helpers ------------------------------------------------ */
const sleep  = ms => new Promise(r => setTimeout(r, ms));
const jFetch = (url, data) =>
  fetch(url, {
    method : 'POST',
    headers: { 'Content-Type':'application/json' },
    body   : JSON.stringify(data)
  });

function stepId(step) {                 // tolerate old/new field name
  return step.component ?? step.comp ?? null;
}

/* ---------- preload component list (names + preview img) ------------ */
(async () => {
  try {
    const list = await fetch('/components/json').then(r => r.json());
    for (const c of list) {
      compName[c.id] = c.name;
      if (c.image) compImg[c.id] = c.image;
    }
  } catch { /* optional – page still works without */ }
})();

/* ---------- queue handling ----------------------------------------- */
async function waitForJob() {
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

/* ---------- display a single step ---------------------------------- */
function showStep(i) {
  console.debug('[DBG] compImg map', compImg); 
  const step = seq[i] ?? {};

  /* component name */
  const cid  = stepId(step);
  const cname = cid ? (compName[cid] ?? cid) : '';
  compEl.textContent = cname;
  compEl.style.display = cname ? 'block' : 'none';

  /* instruction label */
  labelEl.textContent  = step.label ?? '';
  statusEl.textContent = `Step ${i + 1} / ${seq.length}`;

  /* image: project-specific first, else component preview */
  let src = null;
  if (step.img) {
    src = `/proj_assets/${session.project}/${step.img}`;
  } else if (cid && compImg[cid]) {
    src = `/comp_assets/${cid}/${compImg[cid]}`;
  }
console.debug('[DBG] chosen image', src);
  if (src) {
    imgEl.src = src;
    imgEl.hidden = false;
  } else {
    imgEl.hidden = true;
  }

  /* ghost cards */
  prevGhost.textContent      = seq[i - 1]?.label ?? '';
  nextGhost.textContent      = seq[i + 1]?.label ?? '';
  prevGhost.style.visibility = i > 0              ? 'visible' : 'hidden';
  nextGhost.style.visibility = i < seq.length - 1 ? 'visible' : 'hidden';

  nextBtn.textContent = (i === seq.length - 1) ? 'Review' : 'Next Step';
}

/* shorthand to talk to backend */
function send(action, extra = {}) {
  return jFetch('/api/progress', {
    action,
    session_id: session.session_id,
    ...extra
  });
}

/* ---------- flow --------------------------------------------------- */
async function advance() {
  idx += 1;

  if (idx < seq.length) {
    const step = seq[idx] ?? {};
    showStep(idx);

    const cid = stepId(step);
    await send('next', cid ? { component: cid } : {});
  } else {
    nextBtn.disabled = stopBtn.disabled = true;
    statusEl.textContent = 'Preparing summary…';
    await send('next');
    await sleep(200);
    location.href = `/session/${session.session_id}`;
  }
}

async function abort() {
  if (!confirm('Interrupt this assembly?')) return;
  nextBtn.disabled = stopBtn.disabled = true;
  statusEl.textContent = 'Aborting…';
  await send('abort', { step: idx });
  await sleep(300);
  location.reload();
}

/* ---------- bootstrap --------------------------------------------- */
(async () => {
  const data = await waitForJob();
  session = data.session;
  seq     = data.sequence;

  document.querySelector('.meta').textContent =
        `Project ${session.project} | `
      + `Stack ${session.stack_id} | `
      + `Operator ${session.operator}`;

  controls.style.display = 'flex';
  nextBtn.addEventListener('click', advance);
  stopBtn.addEventListener('click', abort);

  advance();           // first step
})();
