() => {
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim().slice(0, 80);
  const text = (el) => clean(el.innerText || el.textContent);
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const labelFor = (el) => {
    if (el.id) {
      const l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (l) return text(l);
    }
    const w = el.closest('label');
    if (w) {
      const c = w.cloneNode(true);
      c.querySelectorAll('select,input,textarea,option').forEach((n) => n.remove());
      return text(c);
    }
    return '';
  };
  const forms = Array.from(document.forms);
  const selector = 'a[href],button,input:not([type=hidden]),select,textarea,[role=button],[role=link],[role=tab],[role=menuitem],[onclick],[data-testid]';
  const elements = [];
  const seen = new Set();
  document.querySelectorAll(selector).forEach((el) => {
    if (seen.has(el)) return;
    seen.add(el);
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || (tag === 'input' ? 'text' : '')).toLowerCase();
    const role = el.getAttribute('role') ||
      ({ a: 'link', button: 'button', select: 'combobox', textarea: 'textbox' })[tag] ||
      (tag === 'input' ? ({ checkbox: 'checkbox', radio: 'radio', submit: 'button', button: 'button', reset: 'button', range: 'slider' })[type] || 'textbox' : '');
    let kind = ({ a: 'link', button: 'button', select: 'select', textarea: 'textarea' })[tag];
    if (tag === 'input') kind = ['submit', 'button', 'reset'].includes(type) ? 'button' : (type === 'checkbox' ? 'checkbox' : (type === 'radio' ? 'radio' : 'input'));
    if (!kind) kind = role === 'button' ? 'button' : (role === 'link' ? 'link' : 'control');
    const form = el.form ? 'form-' + (forms.indexOf(el.form) + 1) : '';
    const handlers = {};
    Array.from(el.attributes).forEach((a) => { if (a.name.startsWith('on') && a.value) handlers[a.name] = a.value.slice(0, 80); });
    elements.push({
      kind, tag, role, type,
      id: el.id || '', name_attr: el.getAttribute('name') || '', placeholder: el.getAttribute('placeholder') || '',
      aria_label: el.getAttribute('aria-label') || '', title: el.getAttribute('title') || '',
      href: tag === 'a' ? (el.getAttribute('href') || '') : '', testid: el.getAttribute('data-testid') || '',
      required: el.hasAttribute('required'), disabled: el.hasAttribute('disabled') || el.disabled === true,
      pattern: el.getAttribute('pattern') || '', min: el.getAttribute('min') || '', max: el.getAttribute('max') || '',
      maxlength: el.getAttribute('maxlength') || '', handlers, form,
      text: ['a', 'button'].includes(tag) || role === 'button' || role === 'link' || role === 'tab' ? text(el) : '',
      label: ['input', 'select', 'textarea'].includes(tag) ? labelFor(el) : '',
      line: 0, options: tag === 'select' ? Array.from(el.options).map((o) => clean(o.text)) : [],
      visible: visible(el),
    });
  });
  return {
    title: document.title || '',
    headings: Array.from(document.querySelectorAll('h1,h2,h3')).map((h) => ({ level: Number(h.tagName[1]), text: text(h) })).filter((h) => h.text),
    elements,
    forms: forms.map((f, i) => ({ id: 'form-' + (i + 1), dom_id: f.id || '', action: f.getAttribute('action') || '', method: (f.getAttribute('method') || '').toLowerCase(), fields: [], submit: [], line: 0 })),
    tables: Array.from(document.querySelectorAll('table')).map((t, i) => ({ id: 'table-' + (i + 1), headers: Array.from(t.querySelectorAll('th')).map((h) => text(h)).filter(Boolean), line: 0 })),
    scripts: Array.from(document.scripts).map((s) => s.getAttribute('src') || '').filter(Boolean),
  };
}
