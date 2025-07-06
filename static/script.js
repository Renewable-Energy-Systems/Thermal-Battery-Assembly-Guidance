/* Guidance-step runtime logic (v3) */

const seq      = window.sequence || [];
const nextBtn  = document.getElementById('nextBtn');
const stopBtn  = document.getElementById('stopBtn');
const imgEl    = document.getElementById('stepImg');
const labelEl  = document.getElementById('stepLabel');
const statusEl = document.getElementById('status');

// -------- poll for queued job -------------------------------------------
async function awaitJob () {
  while (true) {
    const r = await fetch('/kiosk/poll').then(r=>r.json());
    if (r.pending) return r.job;            // got one – exit loop
    await new Promise(res=>setTimeout(res, 2000));   // wait 2 s
  }
}

if (!window.sequence) {           // means page loaded with no session
  document.querySelector('.meta').textContent = 'Waiting for supervisor…';
  awaitJob().then(job => location.reload()); // reload => / will render
  throw 'waiting';                // stop script below from executing
}


let idx = -1;                       // start before first
const pid = document.querySelector('.meta').dataset.pid;   // folder name

function showStep(i) {
  const step = seq[i];
  labelEl.textContent = step?.label ?? '';

  if (step?.img) {
    imgEl.src = `/proj_assets/${pid}/${step.img}`;
    imgEl.style.display = 'block';
  } else {
    imgEl.style.display = 'none';
  }
  statusEl.textContent = `Step ${i + 1} of ${seq.length}`;
}

/* normal advance */
function advance() {
  idx += 1;

  if (idx < seq.length) {
    showStep(idx);
    fetch('/next', { method: 'POST' });
    if (idx === seq.length - 1) nextBtn.textContent = 'Finish';
  } else {
    finishSequence();
  }
}

/* finish */
function finishSequence() {
  statusEl.textContent = 'Sequence complete.';
  nextBtn.disabled = true;
  stopBtn.disabled = true;
  imgEl.style.display = 'none';
  fetch('/finish', { method: 'POST' })
      .then(() => window.location.href = '/select');
}

/* abort */
function abortSequence() {
  if (!confirm('Interrupt this assembly? Progress will be logged.')) return;

  nextBtn.disabled = true;
  stopBtn.disabled = true;
  statusEl.textContent = 'Aborting…';

  fetch('/abort', {
      method : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body   : JSON.stringify({ step: idx })
  }).then(() => window.location.href = '/select');
}

/* event hooks */
nextBtn.addEventListener('click', advance);
stopBtn.addEventListener('click', abortSequence);

/* auto-start or block if empty */
if (seq.length === 0) {
  statusEl.textContent = 'No sequence configured for this project.';
  nextBtn.disabled = stopBtn.disabled = true;
} else {
  advance();
}
function finishSequence() {
  statusEl.textContent = 'Sequence complete.';
  nextBtn.disabled = true;
  stopBtn.disabled = true;
  imgEl.style.display = 'none';
  fetch('/finish', { method: 'POST' })
      .then(() => window.location.href = '/summary');   // ← was /select
}
