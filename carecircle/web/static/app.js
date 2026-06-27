/* CareCircle front-end logic — vanilla JS, no build step. */

// --- Screen navigation ---
const navBtns = document.querySelectorAll('.nav-btn');
const screens = document.querySelectorAll('.screen');
navBtns.forEach(btn => btn.addEventListener('click', () => {
  navBtns.forEach(b => b.classList.remove('active'));
  screens.forEach(s => s.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(btn.dataset.target).classList.add('active');
  if (btn.dataset.target === 'screen-dashboard') loadDashboard();
  if (btn.dataset.target === 'screen-history') loadHistory();
}));

// --- Camera capture (uses device camera where available) ---
const cameraBtn = document.getElementById('cameraBtn');
const cameraFeed = document.getElementById('cameraFeed');
cameraBtn.addEventListener('click', async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
    const video = document.createElement('video');
    video.autoplay = true; video.playsInline = true; video.srcObject = stream;
    video.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:cover;border-radius:22px;';
    cameraFeed.prepend(video);
    appendTranscript('📷 Visual snapshot captured.');
  } catch (e) {
    appendTranscript('📷 Camera unavailable on this device — continuing with notes only.');
  }
});

// --- Voice input via Web Speech API ---
const micBtn = document.getElementById('micBtn');
const transcriptEl = document.getElementById('transcript');
let recognition = null;
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SR) {
  recognition = new SR();
  recognition.continuous = true; recognition.interimResults = true; recognition.lang = 'en-US';
  recognition.onresult = (ev) => {
    let txt = '';
    for (let i = ev.resultIndex; i < ev.results.length; i++) txt += ev.results[i][0].transcript;
    transcriptEl.textContent = txt;
  };
  recognition.onend = () => micBtn.classList.remove('recording');
}
let recording = false;
micBtn.addEventListener('click', () => {
  if (!recognition) { appendTranscript(' (Voice not supported on this browser.) '); return; }
  recording = !recording;
  if (recording) { transcriptEl.textContent=''; recognition.start(); micBtn.classList.add('recording'); }
  else { recognition.stop(); micBtn.classList.remove('recording'); }
});
function appendTranscript(t){
  if (transcriptEl.textContent.startsWith('Tap the microphone')) transcriptEl.textContent = '';
  transcriptEl.textContent += (transcriptEl.textContent ? ' ' : '') + t;
}

// --- Analyze (Capture -> agents) ---
document.getElementById('analyzeBtn').addEventListener('click', async () => {
  const btn = document.getElementById('analyzeBtn');
  btn.textContent = 'Thinking…'; btn.disabled = true;
  const transcript = transcriptEl.textContent.startsWith('Tap the microphone') ? '' : transcriptEl.textContent;
  try {
    const res = await fetch('/api/analyze', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ transcript })
    });
    const data = await res.json();
    if (data.guard && !data.guard.safe) {
      alert('⚠️ Safety guard blocked unsafe input. The note was not sent to the agents.');
    }
    fillNotification(data);
    document.querySelector('[data-target="screen-notify"]').click();
  } catch(e) { alert('Error: ' + e); }
  btn.textContent = 'Analyze with CareCircle'; btn.disabled = false;
});

// --- Today (dashboard) ---
async function loadDashboard(){
  const res = await fetch('/api/dashboard');
  const data = await res.json();
  const pill = document.getElementById('scorePill');
  pill.textContent = `CareScore ${data.care_score} · ${data.band}`;
  pill.className = 'score-pill ' + (data.band||'').toLowerCase();
  const list = document.getElementById('suggestionList');
  list.innerHTML = '';
  (data.suggestions || []).forEach(s => { const li=document.createElement('li'); li.textContent=s; list.appendChild(li); });
  renderCalendar(data.calendar || []);
}
function renderCalendar(events){
  const body = document.getElementById('calBody');
  const cells = ['','','','','','',''];
  events.forEach(ev => {
    const d = new Date((ev.when||'').replace(' ', 'T'));
    if (!isNaN(d)) cells[d.getDay()] += `<div>• ${(ev.title||'').split('—')[0].slice(0,16)}</div>`;
  });
  body.innerHTML = '<tr>' + cells.map(c=>`<td>${c}</td>`).join('') + '</tr>';
}

// --- Summary / notification ---
function fillNotification(d){
  const med = d.vita ? `${d.vita.adherence_pct}% adherence`
      + (d.vita.missed_doses && d.vita.missed_doses.length ? ` · missed ${d.vita.missed_doses.join(', ')}` : '')
      : '—';
  const wx = d.weather ? `${d.weather.temp_c}°C, ${d.weather.condition}. ${d.weather.risk}` : '—';
  document.getElementById('n-score').textContent = `${d.care_score}/100 (${d.band})`;
  document.getElementById('n-med').textContent = med;
  document.getElementById('n-act').textContent = d.explanation || '—';
  document.getElementById('n-sleep').textContent = d.risk_window || '—';
  document.getElementById('n-weather').textContent = wx;
  document.getElementById('n-cal').textContent = 'See the Today tab';
  document.getElementById('n-notes').textContent = d.message || '—';
}

document.getElementById('sendBtn').addEventListener('click', async () => {
  const status = document.getElementById('sentStatus');
  status.textContent = 'Sending…';
  const res = await fetch('/api/send-summary', {
    method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ transcript:'' })
  });
  const data = await res.json();
  status.textContent = data.send && data.send.mode === 'telegram'
    ? '✅ Sent to your family on Telegram'
    : '✅ Summary generated (Telegram not configured — printed to server console)';
});

// --- History ---
async function loadHistory(){
  const res = await fetch('/api/profile');
  const data = await res.json();
  const p = data.profile || {};
  const e = data.elder || {};
  document.getElementById('h-name').textContent = e.name || '—';
  document.getElementById('h-age').textContent = p.age != null ? `${p.age} yrs` : '—';
  document.getElementById('h-gender').textContent = p.gender || '—';
  document.getElementById('h-weight').textContent = p.weight_kg != null ? `${p.weight_kg} kg` : '—';
  document.getElementById('h-height').textContent = p.height_cm != null ? `${p.height_cm} cm` : '—';
  document.getElementById('h-blood').textContent = p.blood_type || '—';

  fillTags('h-conditions', p.conditions);
  fillTags('h-allergies', p.allergies);
  fillTags('h-injuries', p.injuries);
  fillTags('h-meds', (data.medications || []).map(m => `${m.name} ${m.dose||''}`.trim()));

  document.getElementById('h-notes').textContent = p.history_notes || '—';
  document.getElementById('h-doctor').textContent = p.primary_doctor || '—';
  document.getElementById('h-emergency').textContent = p.emergency_note || '—';
}
function fillTags(id, arr){
  const el = document.getElementById(id);
  el.innerHTML = '';
  (arr && arr.length ? arr : ['None recorded']).forEach(t => {
    const span = document.createElement('span'); span.textContent = t; el.appendChild(span);
  });
}