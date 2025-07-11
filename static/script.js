/*  static/script.js – kiosk runtime (v4.6)  */

const controls = document.getElementById('controls');
const nextBtn  = document.getElementById('nextBtn');
const stopBtn  = document.getElementById('stopBtn');
const imgEl    = document.getElementById('stepImg');
const labelEl  = document.getElementById('stepLabel');
const statusEl = document.getElementById('status');

let session = null;          // filled after /api/claim
let seq     = [];            // project steps
let idx     = -1;            // current step index

/* ---------- helpers --------------------------------------------------- */
const sleep  = ms => new Promise(r => setTimeout(r, ms));
const jFetch = (url, data) =>
  fetch(url, {
    method : 'POST',
    headers: { 'Content-Type':'application/json' },
    body   : JSON.stringify(data)
  });

async function waitForJob () {
  while (true) {
    const queue = await fetch('/api/pending').then(r => r.json());
    if (queue.length) {
      const sid  = queue[0].session_id;            // oldest pending
      const resp = await jFetch('/api/claim', { session_id: sid });
      if (resp.ok) return resp.json();             // success!
    }
    await sleep(2000);
  }
}

/* ---------- component → preview map  --------------------------------- */
let compImg = {};          // { compId : fileName }
(async () => {
  compImg = await fetch('/components/json')
                    .then(r => r.json())
                    .then(arr =>
                      Object.fromEntries(arr
                        .filter(c => c.image)
                        .map(c => [c.id, c.image]))
                    );
  console.debug('[DBG] component images', compImg);
})();

/* ---------- step display --------------------------------------------- */
function showStep(i) {
  const step = seq[i] ?? {};
  console.debug('[DBG] showStep()', i, step);

  labelEl.textContent  = step.label ?? '';
  statusEl.textContent = `Step ${i + 1} / ${seq.length}`;

  const imgFile = compImg[step.comp];
  if (imgFile) {
    imgEl.src = `/comp_assets/${step.comp}/${imgFile}`;
    imgEl.hidden = false;
  } else {
    imgEl.hidden = true;
  }

  nextBtn.textContent = (i === seq.length - 1) ? 'Review' : 'Next Step';
}

function send(action, extra = {}) {
  return jFetch('/api/progress', {
    action,
    session_id: session.session_id,
    ...extra                      // e.g. {step: idx} or {component: …}
  });
}

/* ---------- flow ------------------------------------------------------ */
async function advance() {
  idx += 1;

  if (idx < seq.length) {               // still inside sequence
    const step = seq[idx];
    showStep(idx);
    await send('next', { component: step.comp });
  } else {                              // last step done → review page
    nextBtn.disabled = stopBtn.disabled = true;
    statusEl.textContent = 'Preparing summary…';
    await send('finish');                // record final step
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

/* ---------- bootstrap ------------------------------------------------- */
(async () => {
  // 1) wait until supervisor enqueues something
  const data = await waitForJob();
  session = data.session;
  seq     = data.sequence;

  console.debug('[DBG] claimed session', session);
  console.debug('[DBG] sequence', seq);

  // 2) fill header & show controls
  document.querySelector('.meta').textContent =
        `Project ${session.project} | `
      + `Stack ${session.stack_id} | `
      + `Operator ${session.operator}`;

  controls.style.display = 'flex';       // show buttons
  nextBtn.addEventListener('click', advance);
  stopBtn.addEventListener('click', abort);

  // 3) kick off first step
  advance();
})();
