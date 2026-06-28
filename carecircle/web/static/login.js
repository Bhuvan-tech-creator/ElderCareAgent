/* CareCircle login + registration logic. */

// --- Tab switching ---
const tabLogin = document.getElementById('tab-login');
const tabRegister = document.getElementById('tab-register');
const loginCard = document.getElementById('login-card');
const registerCard = document.getElementById('register-card');

function setMode(mode){
  const isLogin = mode === 'login';
  tabLogin.classList.toggle('active', isLogin);
  tabRegister.classList.toggle('active', !isLogin);
  loginCard.classList.toggle('hidden', !isLogin);
  registerCard.classList.toggle('hidden', isLogin);
}
tabLogin.addEventListener('click', () => setMode('login'));
tabRegister.addEventListener('click', () => setMode('register'));

// --- Helpers ---
function splitList(value, fallbackPlaceholder){
  // If the user typed nothing, fall back to the example placeholder values.
  const v = (value || '').trim();
  const source = v || fallbackPlaceholder;
  return source.split(',').map(s => s.trim()).filter(Boolean);
}
function numOr(value, fallback){
  const n = parseInt(value, 10);
  return isNaN(n) ? fallback : n;
}
function valOr(value, fallback){
  const v = (value || '').trim();
  return v || fallback;
}

// --- Login ---
document.getElementById('login-btn').addEventListener('click', async () => {
  const msg = document.getElementById('login-msg');
  const btn = document.getElementById('login-btn');
  msg.textContent = ''; btn.disabled = true; btn.textContent = 'Signing in…';
  try {
    const res = await fetch('/api/login', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        username: document.getElementById('login-username').value,
        password: document.getElementById('login-password').value,
      })
    });
    const data = await res.json();
    if (data.ok) { window.location.href = '/'; }
    else { msg.textContent = data.error || 'Sign in failed.'; msg.className = 'auth-msg error'; }
  } catch(e){ msg.textContent = 'Error: ' + e; msg.className = 'auth-msg error'; }
  btn.disabled = false; btn.textContent = 'Sign in';
});

// --- Register ---
document.getElementById('register-btn').addEventListener('click', async () => {
  const msg = document.getElementById('register-msg');
  const btn = document.getElementById('register-btn');
  msg.textContent = ''; btn.disabled = true; btn.textContent = 'Creating…';

  // If a field is left blank, we use its example placeholder so nothing is empty.
  const profile = {
    name:       valOr(document.getElementById('p-name').value, 'Grandma Devi'),
    age:        numOr(document.getElementById('p-age').value, 74),
    gender:     valOr(document.getElementById('p-gender').value, 'Female'),
    weight_kg:  numOr(document.getElementById('p-weight').value, 62),
    height_cm:  numOr(document.getElementById('p-height').value, 158),
    blood_type: valOr(document.getElementById('p-blood').value, 'B+'),
    language:   valOr(document.getElementById('p-language').value, 'English'),
    conditions: splitList(document.getElementById('p-conditions').value, 'Type 2 Diabetes, Hypertension'),
    allergies:  splitList(document.getElementById('p-allergies').value, 'Penicillin, Peanuts'),
    injuries:   splitList(document.getElementById('p-injuries').value, 'Hip fracture (2021, healed), Mild arthritis in knees'),
    history_notes:  valOr(document.getElementById('p-notes').value, 'Cataract surgery in 2019. No history of heart attack or stroke.'),
    primary_doctor: valOr(document.getElementById('p-doctor').value, 'Dr. Mehta (Cardiology)'),
    emergency_note: valOr(document.getElementById('p-emergency').value, 'Keeps glucose tablets in bedside drawer.'),
  };

  try {
    const res = await fetch('/api/register', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        username: document.getElementById('reg-username').value,
        password: document.getElementById('reg-password').value,
        profile,
      })
    });
    const data = await res.json();
    if (data.ok) { window.location.href = '/'; }
    else { msg.textContent = data.error || 'Could not create account.'; msg.className = 'auth-msg error'; }
  } catch(e){ msg.textContent = 'Error: ' + e; msg.className = 'auth-msg error'; }
  btn.disabled = false; btn.textContent = 'Create account & continue';
});