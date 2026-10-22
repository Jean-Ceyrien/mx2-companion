'use strict';

let currentStep = 0;
let currentView = 'setup';
let lastState = null;
let polling = false;
let stopRequested = false;
let quitting = false;
let quitPollTimer = null;
const $ = id => document.getElementById(id);
const api = () => window.pywebview?.api;

function toast(message) {
  $('toast').textContent = message;
  $('toast').hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { $('toast').hidden = true; }, 6500);
}

function view(name) {
  if (!['setup', 'reference', 'audio'].includes(name)) return;
  currentView = name;
  document.querySelectorAll('.view').forEach(el => { el.hidden = el.id !== name; });
  document.querySelectorAll('.nav').forEach(el => {
    const active = el.dataset.view === name;
    el.classList.toggle('active', active);
    if (active) el.setAttribute('aria-current', 'page');
    else el.removeAttribute('aria-current');
  });
  if (name === 'reference') $('cheat-frame').focus();
}

function step(index) {
  if (index < 0 || index > 2) return;
  currentStep = index;
  view('setup');
  document.querySelectorAll('[data-copy]').forEach(el => {
    el.hidden = Number(el.dataset.copy) !== index;
  });
  document.querySelectorAll('[data-step]').forEach(el => {
    const active = Number(el.dataset.step) === index;
    el.classList.toggle('current', active);
    if (active) el.setAttribute('aria-current', 'step');
    else el.removeAttribute('aria-current');
  });
}

async function call(name, ...args) {
  if (!api()) {
    toast('Open MX2 Companion to use connection controls. This is a visual preview.');
    return null;
  }
  try {
    const result = await api()[name](...args);
    if (result?.message) toast(result.message);
    await poll();
    return result;
  } catch (error) {
    toast('The app could not complete this action. Try again.');
    return null;
  }
}

function render(state) {
  lastState = state;
  const hardware = state.hardware || {};
  const bridge = state.bridge || {};
  const selectedMode = state.connection_mode === 'midi' ? 'midi' : 'native';
  const connected = Boolean(hardware.connected);
  let kind = 'offline';
  let title = 'MX2 not connected';
  let mode = 'USB disconnected';
  let instruction = 'Connect your controller';
  let detail = 'Plug in your MX2 and turn it on.';

  if (connected) {
    kind = hardware.mode === 'native' ? 'native' : hardware.mode === 'midi' ? 'midi' : 'unknown';
    title = 'MX2 connected';
    mode = hardware.mode === 'native' ? 'Native mode' : hardware.mode === 'midi' ? 'MIDI mode' : 'Mode not confirmed';
    instruction = hardware.mode === selectedMode ? (mode + ' confirmed') : hardware.mode === 'unknown' || hardware.stale ? 'Move a control to confirm mode' : 'Switch the MX2 to ' + selectedMode.toUpperCase();
    detail = hardware.mode === selectedMode ? 'The controller matches the selected bridge mode.' : hardware.mode === 'unknown' || hardware.stale ? 'Waiting for live input. No mode change is sent by this app.' : 'Press both SHIFT buttons together once.';
    if (hardware.stale && hardware.last_observed_mode) {
      detail = 'Last confirmed: ' + (hardware.last_observed_mode === 'native' ? 'Native' : 'MIDI') + '. Move a control to confirm the current mode.';
    }
  }
  if (hardware.error && !connected) {
    instruction = 'Device monitor needs attention';
    detail = hardware.error;
  }

  $('connection-title').textContent = title;
  $('mode').textContent = mode;
  $('device-instruction').textContent = instruction;
  $('device-detail').textContent = detail;
  $('photo-state').textContent = connected ? mode : 'Waiting for USB';
  for (const id of ['connection-dot', 'inline-dot', 'photo-dot']) {
    $(id).className = 'status-dot ' + kind;
  }

  if (!bridge.running) stopRequested = false;
  $('bridge-status').textContent = bridge.running
    ? (stopRequested ? 'Stopping bridge…' : bridge.ready ? 'Bridge running' : 'Starting bridge…')
    : 'Bridge stopped';
  $('bridge-status').classList.toggle('on', bridge.running && bridge.ready);
  $('start').disabled = bridge.running;
  $('stop').disabled = !bridge.running;
  document.querySelectorAll('input[name="connection-mode"]').forEach(input => {
    input.checked = input.value === selectedMode;
    input.disabled = bridge.running || (input.value === 'midi' && !state.midi_available);
  });
  $('import').textContent = state.mapping?.installed ? 'Mapping installed' : 'Install djay mapping';
  $('footer-status').textContent = bridge.running
    ? (bridge.fresh ? 'Live status · bridge connected' : 'Waiting for bridge status')
    : 'Device monitor active · bridge stopped';
  $('monitor-note').textContent = state.platform === 'win32'
    ? 'Windows preview: create the loopMIDI port “MX2 for djay” before starting.'
    : 'Device monitoring stays on, even when the bridge is stopped.';
  $('version').textContent = 'Version ' + state.version;
  document.querySelector('[data-step="0"]').classList.toggle('done', connected && hardware.mode === selectedMode);
  document.querySelector('[data-step="1"]').classList.toggle('done', state.mapping_opened && bridge.running);
  if (state.mapping?.installed) {
    $('mapping-hint').innerHTML = 'Mapping installed. In djay, select <b>MX2 for djay</b> and <b id="mapping-name"></b>. Keep the direct <b>Traktor MX2</b> connection disabled.';
  } else if (state.mapping_opened) {
    $('mapping-hint').innerHTML = 'Mapping opened. Finish importing, then <b>quit and reopen djay</b> once. Select <b id="mapping-name"></b> for <b>MX2 for djay</b>.';
  } else {
    $('mapping-hint').innerHTML = 'After the first import, quit and reopen djay. Then choose <b>MX2 for djay</b> and <b id="mapping-name"></b>. Disable the direct Traktor MX2 MIDI connection.';
  }
  $('mapping-name').textContent = state.platform === 'win32' ? 'Traktor MX2 – Windows RGB' : selectedMode === 'midi' ? 'Traktor MX2 – Visual Complete' : 'Traktor MX2 – Native RGB';
  if (state.error && state.error !== render.lastError) {
    toast(state.error);
    render.lastError = state.error;
  }
}

async function poll() {
  if (quitting || polling || !api()) return;
  polling = true;
  try { render(await api().get_state()); }
  catch (error) { $('footer-status').textContent = 'Waiting for the companion service'; }
  finally { polling = false; }
}

function renderQuitProgress(state) {
  const percent = Math.max(0, Math.min(100, Number(state.percent) || 0));
  $('quit-message').textContent = state.message || 'Fermeture en cours…';
  $('quit-progress').setAttribute('aria-valuenow', String(percent));
  $('quit-progress-fill').style.width = percent + '%';
  const current = {bridge: 0, monitor: 1, final: 2, done: 3, error: 3}[state.stage] ?? 0;
  ['bridge', 'monitor', 'final'].forEach((stage, index) => {
    const item = $('quit-step-' + stage);
    item.classList.toggle('active', index === current);
    item.classList.toggle('done', index < current);
  });
  $('quit-dialog').classList.toggle('error', state.stage === 'error');
}

async function pollQuitProgress() {
  if (!quitting || !api()) return;
  try { renderQuitProgress(await api().get_quit_progress()); }
  catch (error) { $('quit-message').textContent = 'Attente du service de fermeture…'; }
}

function resetQuit() {
  quitting = false;
  clearInterval(quitPollTimer);
  quitPollTimer = null;
  $('quit-overlay').hidden = true;
  $('quit-app').disabled = false;
  $('quit-app').textContent = 'Stop & quit';
}

async function quitApp() {
  if (quitting) return;
  if (!api()) {
    toast('Open MX2 Companion to stop the bridge and quit.');
    return;
  }
  quitting = true;
  $('quit-overlay').hidden = false;
  $('quit-app').disabled = true;
  $('quit-app').textContent = 'Fermeture…';
  try {
    const result = await api().quit_app();
    if (result?.ok) {
      quitPollTimer = setInterval(pollQuitProgress, 180);
      await pollQuitProgress();
      return;
    }
    resetQuit();
    toast(result?.message || 'The app could not quit. Try again.');
  } catch (error) {
    resetQuit();
    toast('The app could not quit. Try again.');
  }
}

document.querySelectorAll('[data-view]').forEach(el => el.addEventListener('click', () => view(el.dataset.view)));
document.querySelectorAll('[data-step]').forEach(el => el.addEventListener('click', () => step(Number(el.dataset.step))));
document.querySelectorAll('[data-next]').forEach(el => el.addEventListener('click', () => step(Number(el.dataset.next))));
$('quick-reference').onclick = () => view('reference');
$('finish').onclick = () => view('reference');
$('sound-confirmed').onchange = event => document.querySelector('[data-step="2"]').classList.toggle('done', event.target.checked);
document.querySelectorAll('input[name="connection-mode"]').forEach(input => {
  input.onchange = async () => {
    if (!input.checked) return;
    const result = await call('set_connection_mode', input.value);
    if (!result?.ok && lastState) render(lastState);
  };
});
$('start').onclick = () => { stopRequested = false; call('start_bridge'); };
$('stop').onclick = () => { stopRequested = true; call('stop_bridge'); };
$('import').onclick = () => call('import_mapping');
$('open-target').onclick = () => call('open_target');
$('open-reference-browser').onclick = () => call('open_cheat_sheet');
$('reference-fullscreen').onclick = async () => {
  const result = await call('toggle_controls_fullscreen');
  if (!result?.ok) return;
  const button = $('reference-fullscreen');
  button.setAttribute('aria-pressed', String(result.fullscreen));
  button.innerHTML = result.fullscreen
    ? 'Exit full screen <span aria-hidden="true">⤡</span>'
    : 'Full screen <span aria-hidden="true">⤢</span>';
};
$('quit-app').onclick = quitApp;
document.addEventListener('keydown', event => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    view(currentView === 'reference' ? 'setup' : 'reference');
  }
});
window.addEventListener('pywebviewready', poll);
setInterval(poll, 650);
poll();
setTimeout(() => {
  if (!api()) {
    $('connection-title').textContent = 'Visual preview';
    $('mode').textContent = 'Open the app for live status';
    $('device-instruction').textContent = 'Live detection runs inside the app';
    $('device-detail').textContent = 'The guide and control reference work here without a device.';
  }
}, 1500);
