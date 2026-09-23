// Mobile menu
const toggle = document.querySelector('.nav-toggle');
const links = document.getElementById('nav-links');
toggle.addEventListener('click', () => {
  const open = links.classList.toggle('open');
  toggle.setAttribute('aria-expanded', open);
});
links.addEventListener('click', (e) => {
  if (e.target.tagName === 'A') {
    links.classList.remove('open');
    toggle.setAttribute('aria-expanded', 'false');
  }
});

document.getElementById('year').textContent = new Date().getFullYear();

// Share button: native share sheet on phones, copy link elsewhere
const shareBtn = document.getElementById('share-btn');
const shareNote = document.getElementById('share-note');
shareBtn.addEventListener('click', async () => {
  const url = location.href.split('#')[0];
  const shareData = {
    title: 'Your Backup Plan',
    text: 'Reliable, flexible help for businesses, schools and busy people in the South Hills & Washington County. Call or text Ashley at 412-401-3208.',
    url,
  };
  try {
    if (navigator.share) {
      await navigator.share(shareData);
      return;
    }
    await navigator.clipboard.writeText(url);
    shareNote.textContent = 'Link copied! Paste it in a text or post. Thank you!';
  } catch (err) {
    if (err && err.name === 'AbortError') return;
    shareNote.textContent = `Copy this link to share: ${url}`;
  }
});

// Contact form.
// With no FORM_ENDPOINT set, the form opens the visitor's email app with the
// request filled in. To receive submissions directly (no email app needed),
// create a free form at https://formspree.io and paste its URL below.
const FORM_ENDPOINT = '';
const TO_EMAIL = 'yourbackupplan.ashley@gmail.com';

const form = document.getElementById('contact-form');
const note = document.getElementById('form-note');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(form));

  let ok = true;
  for (const name of ['name', 'email']) {
    const field = form.elements[name];
    const valid = field.value.trim() && field.checkValidity();
    field.classList.toggle('invalid', !valid);
    if (!valid) ok = false;
  }
  if (!ok) {
    note.textContent = 'Please add your name and a valid email so I can get back to you.';
    return;
  }

  if (FORM_ENDPOINT) {
    note.textContent = 'Sending…';
    try {
      const res = await fetch(FORM_ENDPOINT, {
        method: 'POST',
        headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error(res.status);
      form.reset();
      note.textContent = 'Thank you! Your request is on its way. I’ll be in touch soon. ♥';
    } catch {
      note.textContent = 'Something went wrong. Please call or text 412-401-3208.';
    }
    return;
  }

  const subject = `Help request: ${data.type} (${data.length})`;
  const lines = [
    `Name: ${data.name}`,
    data.org && `Business / organization: ${data.org}`,
    data.phone && `Phone: ${data.phone}`,
    `Email: ${data.email}`,
    `Type of help: ${data.type}`,
    `How long: ${data.length}`,
    data.when && `When: ${data.when}`,
  ].filter(Boolean);
  const body = data.message ? `${lines.join('\n')}\n\n${data.message}` : lines.join('\n');

  window.location.href = `mailto:${TO_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  note.textContent = 'Your email app should open with your request ready to send.';
});
