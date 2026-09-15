/* eslint-disable no-undef */

(function() {
  'use strict';

  const $ = (id) => window.SFUtils.byId(id);
  function escapeHtml(s) { return window.SFUtils.escapeHtml(s); }
  const t = (path, fallback) => window.SFUtils.t(path, fallback);

  /* Local math paint + global content/icons refresh in one call. */
  function paintMath(el) {
    try {
      if (typeof renderMathInElement === 'function') renderMathInElement(el, { delimiters: [{ left: '$$', right: '$$', display: true }, { left: '$', right: '$', display: false }], macros: window._KATEX_MACROS || {} });
    } catch (e) {}
    if (typeof renderMathInContent === 'function') renderMathInContent();
    refreshIcons();
  }
  const copyText = (text, label) => window.SFUtils.copyText(text, label);
  function renderRowSymbols(root) {
    if (typeof katex === 'undefined') return;
    root.querySelectorAll('tr[data-symbol]').forEach((tr) => {
      if (!tr.dataset.symbol) return;
      const target = tr.querySelector('.qty-symbol');
      if (target) katex.render(tr.dataset.symbol, target, { displayMode: false, throwOnError: false });
    });
  }
  function setHTML(el, html) {
    el.innerHTML = typeof html === 'string' ? html : '';
    paintMath(el);
  }

  function loadTokenSidebar() {
    window.SFApi.getText('/create/token-sidebar').then(function(html) { setHTML($('sidebar-left-inner'), html); });
  }

  function filterTokenSidebar(query) {
    var q = (query || '').toLowerCase().trim();
    $('sidebar-left-inner').querySelectorAll('.token-list').forEach(function(section) {
      var visible = 0;
      section.querySelectorAll('.qty-result').forEach(function(el) {
        var match = !q || (el.dataset.search || '').includes(q);
        el.style.display = match ? '' : 'none';
        if (match) visible++;
      });
      var empty = section.nextElementSibling;
      if (empty && empty.classList.contains('token-empty')) {
        empty.style.display = (visible === 0 && section.dataset.collapsed !== '1') ? 'block' : 'none';
      }
    });
  }

  let previewSeq = 0, previewTimer = null, lastVariablesKey = '';
  function collectOverrides() {
    const fd = new FormData();
    document.querySelectorAll('#var-overrides input[name^="override["]').forEach((inp) => {
      if (inp.value) fd.append(inp.name, inp.value);
    });
    return fd;
  }
  const varKey = (v) => v.key || (v.id + '|' + (v.alias || ''));
  const variablesKey = (vars) => (vars || []).map(varKey).join(',');
  function occurrenceIndices(vars) {
    const counts = {}, seen = {}, idx = {};
    for (const v of (vars || [])) {
      const k = v.id + '|' + (v.alias || '');
      counts[k] = (counts[k] || 0) + 1;
      if (counts[k] > 1) { seen[k] = (seen[k] || 0) + 1; idx[v.key] = seen[k]; }
    }
    return idx;
  }
  /* One row builder shared by the live overrides table and every translate page. */
  function overrideRow(key, symbol, displayName, alias, form, namePrefix, seeds, occ) {
    const fields = ['symbol', 'name'];
    let cells = '';
    for (const field of fields) {
      const seed = (seeds && seeds[field]) || {};
      cells += '<td><input data-field="' + field + '" form="' + form + '" name="' + namePrefix + '[' + escapeHtml(key) + '][' + field + ']"'
        + ' placeholder="' + escapeHtml(seed.placeholder || '') + '"'
        + (seed.value ? ' value="' + escapeHtml(seed.value) + '"' : '')
        + ' class="text-field"></td>';
    }
    return '<tr data-symbol="' + escapeHtml(symbol) + '" data-key="' + escapeHtml(key) + '">'
      + '<td class="qty-sym-cell">' + (symbol ? '<span class="qty-symbol"></span> ' : '')
      + escapeHtml(displayName) + (alias ? '[' + escapeHtml(alias) + ']' : '')
      + (occ ? ' <span class="qty-occ">#' + occ + '</span>' : '') + '</td>'
      + cells + '</tr>';
  }
  function varTable(rows) {
    const head = [t('detail.quantity'), t('create.column_symbol_override'), t('create.column_name_override')]
      .map((h) => '<th>' + escapeHtml(h) + '</th>').join('');
    return '<table class="var-table"><thead><tr>' + head + '</tr></thead><tbody>' + rows + '</tbody></table>';
  }
  function renderOverrideTable(vars) {
    const wrap = $('var-overrides');
    if (!wrap) return;
    const real = vars && vars.length ? vars : [];
    const occ = occurrenceIndices(real);
    let rows = '';
    for (let i = 0; i < Math.max(3, real.length); i++) {
      const v = real[i];
      rows += v ? overrideRow(varKey(v), v.symbol || '', localiseName(v.name, v.id), v.alias,
          'create-form', 'override', { name: { placeholder: t('create.placeholder_name') } }, occ[v.key])
        : '<tr class="qty-row-placeholder"><td class="qty-sym-cell">&nbsp;</td>'
          + '<td><input disabled class="text-field" placeholder=""></td>'.repeat(2) + '</tr>';
    }
    wrap.innerHTML = varTable(rows);
    renderRowSymbols(wrap);
    paintMath(wrap);
  }
  function renderPreviewLaTeX(latex) {
    const mathEl = $('formula-math'), texEl = $('formula-tex');
    if (mathEl) {
      mathEl.classList.toggle('formula-placeholder', !latex);
      mathEl.textContent = latex ? '$$' + latex + '$$' : '$$F = ma$$';
    }
    if (texEl) texEl.textContent = latex || 'F = ma';
  }
  // Mirrors scifind_lib/i18n.py localise(value, locale, default="en-us"):
  // accepts a JSON blob string, a dict, or plain text.
  function localiseName(value, fallback) {
    if (value && typeof value === 'object') {
      const loc = (document.documentElement.lang || 'en-us').toLowerCase();
      return value[loc] || value['en-us'] || fallback;
    }
    if (!value || typeof value !== 'string' || !value.trim().startsWith('{')) return value || fallback;
    try {
      const obj = JSON.parse(value);
      const loc = (document.documentElement.lang || 'en-us').toLowerCase();
      return obj[loc] || obj['en-us'] || fallback;
    } catch (e) {
      return value;
    }
  }
  function previewError(msg) {
    $('formula-math').innerHTML = '<span class="formula-error">' + escapeHtml(msg) + '</span>';
    $('formula-tex').textContent = '';
    $('dim-display').innerHTML = escapeHtml(t('detail.dimensions')) + ': <span class="dim-latex">$\\varnothing$</span>';
  }
  function previewOk(data, eq) {
    if (data.error) { previewError(data.error); return; }
    if (!data.latex) { renderPreviewLaTeX(''); return; }
    renderPreviewLaTeX(data.latex);
    const dimEl = $('dim-display');
    const dimLatex = data.dim_latex || '\\varnothing';
    dimEl.innerHTML = escapeHtml(t('detail.dimensions')) + ': <span class="dim-latex"></span>';
    dimEl.style.opacity = (!eq.trim() || dimLatex === '\\varnothing') ? '0.6' : '';
    if (typeof katex !== 'undefined') katex.render(dimLatex, dimEl.querySelector('.dim-latex'), { displayMode: false, throwOnError: false });
  }
  let _lastPreviewEq = null;
  function updatePreview(eq) {
    clearTimeout(previewTimer);
    const trimmed = (eq || '').trim();
    if (!trimmed || trimmed === _lastPreviewEq) {
      if (!trimmed) { previewSeq++; renderPreviewLaTeX(''); }
      return;
    }
    const seq = ++previewSeq;
    previewTimer = setTimeout(() => {
      _lastPreviewEq = trimmed;
      const fd = collectOverrides();
      fd.set('equation', eq);
      function gotPreview(data) {
        if (seq !== previewSeq) return;
        previewOk(data, eq);
        const newKey = variablesKey(data.variables);
        if (newKey !== lastVariablesKey) {
          lastVariablesKey = newKey;
          renderOverrideTable(data.variables || []);
        }
        paintMath(document);
      }
      function previewFail(err) {
        if (seq !== previewSeq) return;
        showToast(window.SFApi.serverMessage(err, t('create.preview_failed', 'Preview failed')), 'error');
      }
      window.SFApi.postJSON('/create/preview-render', fd).then(gotPreview, previewFail);
    }, 200);
  }

  function insertAtCursor(text) {
    const ta = $('equation');
    const start = ta.selectionStart, end = ta.selectionEnd;
    const before = ta.value.substring(0, start), after = ta.value.substring(end);
    const isSep = (ch) => !ch || /\s/.test(ch) || '()[]'.indexOf(ch) !== -1;
    const ins = (before.length && !isSep(before[before.length - 1]) ? ' ' : '') + text + (after.length && !isSep(after[0]) ? ' ' : '');
    ta.value = before + ins + after;
    ta.selectionStart = ta.selectionEnd = start + ins.length - ((after.length && !isSep(after[0])) ? 1 : 0);
    ta.focus();
    updatePreview(ta.value);
  }

  window._treeSelectionChanged = function(id) { selectTopic(id); };
  function loadBreadcrumb(topic) {
    var url = '/create/breadcrumb' + (topic ? '?topic=' + encodeURIComponent(topic) : '');
    window.SFApi.getText(url).then(function(html) { setHTML($('topic-bar'), html); });
  }
  function selectTopic(id) {
    const hidden = $('topic');
    if (hidden) hidden.value = id || '';
    loadBreadcrumb(id);
    const btn = document.getElementById('tree-select-all');
    if (btn) btn.classList.toggle('disabled', !id);
    if (typeof window._setTreeSelection === 'function') window._setTreeSelection(id);
  }

  function openModal() { window.SFUtils.setModal('sql-modal', true); }
  function closeModal() {
    window.SFUtils.setModal('sql-modal', false);
    flow.history = [];
    flow.translations = {};
    flow.variables = [];
  }

  const flow = {
    history: [],            // [{kind: 'pick' | 'translate' | 'sql', ...}]
    translations: {},       // { 'cs-cz': { name, description, overrides } }
    variables: [],          // [{ id, alias, symbol, name, name_overwrite }, ...]
    issueUrl: null,
    availableLanguages: [], // [{code, name}, ...]
  };

  const currentPage = () => flow.history[flow.history.length - 1] || null;
  function pushPage(page) { flow.history.push(page); renderPage(page); }
  function popPage() {
    if (flow.history.length <= 1) return;
    flow.history.pop();
    renderPage(currentPage());
  }
  const langName = (code) => (flow.availableLanguages.find((l) => l.code === code) || {}).name || code;
  function validateEnglishFields() {
    return [['name_en', 'create.name'], ['formula_id', 'create.formula_id'], ['topic', 'create.topic'], ['equation', 'create.equation']]
      .filter(([id]) => { const el = $(id); return !(el && (el.value || '').trim()); })
      .map(([, key]) => t(key).toLowerCase());
  }

  const backBtn = () => '<button class="btn-ghost btn-sm" type="button" data-action="flow-back">' + escapeHtml(t('create.back', 'Back')) + '</button>';
  const continueBtn = (action) => '<button class="btn-primary btn-sm" type="button" data-action="' + action + '">' + escapeHtml(t('create.continue', 'Continue')) + '</button>';
  function renderPage(page) {
    if (!page) return;
    $('modal-step').dataset.kind = page.kind;
    if (page.kind === 'pick') renderPickPage(page);
    else if (page.kind === 'translate') renderTranslatePage(page);
    else if (page.kind === 'sql') renderSqlPage(page);
    refreshIcons();
  }

  function renderPickPage(page) {
    $('modal-title').textContent = t('create.pick_languages_heading', 'Translate this formula into how many languages?');
    const selected = new Set(page.selected || []);
    const rows = flow.availableLanguages.map((lang) => {
      const isEn = lang.code === 'en-us';
      const id = 'lang-' + escapeHtml(lang.code);
      const state = (isEn || selected.has(lang.code) ? ' checked' : '') + (isEn ? ' disabled' : '');
      return '<label class="lang-row" for="' + id + '">'
        + '<input type="checkbox" id="' + id + '" data-lang-code="' + escapeHtml(lang.code) + '"' + state + '>'
        + '<span class="lang-cb"></span><span class="lang-name">' + escapeHtml(lang.name) + '</span>'
        + '<span class="lang-code">(' + escapeHtml(lang.code) + ')</span></label>';
    }).join('');
    $('modal-step').innerHTML = '<p class="detail-desc">' + escapeHtml(t('create.pick_languages_hint', 'English is always included.')) + '</p>'
      + '<div class="lang-picker" id="lang-picker">' + rows + '</div>';
    $('modal-actions').innerHTML = continueBtn('flow-pick-langs-continue');
  }

  function renderTranslatePage(page) {
    const code = page.code;
    $('modal-title').textContent = t('create.translate_heading', 'Translate to {lang}').replace('{lang}', langName(code) + ' (' + code + ')');
    const prior = flow.translations[code] || {};
    const occ = occurrenceIndices(flow.variables);
    const qtyTable = flow.variables.length ? varTable(flow.variables.map((v) => {
      const key = varKey(v);
      const priorOv = (prior.overrides && prior.overrides[key]) || {};
      return overrideRow(key, v.symbol || '', localiseName(v.name, v.id), v.alias, 'create-form', 'tr_overrides[' + code + ']',
        { symbol: { placeholder: v.symbol || '', value: priorOv.symbol || '' }, name: { placeholder: localiseName(v.name, v.id), value: priorOv.name || '' } }, occ[key]);
    }).join('')) : '';
    const copyBtn = (field) =>
      '<button class="filter-btn" type="button" data-tr-copy="' + field + '" data-tr-copy-label="' + escapeHtml(t('create.' + field, field)) + '" title="' + escapeHtml(t('create.copy_from_english', 'Copy from English')) + '">'
      + '<i data-lucide="copy" width="16" height="16"></i></button>';
    const fieldBlock = (field, control) =>
      '<div class="detail-desc"><div class="tr-label-row"><span>' + escapeHtml(t('create.' + field)) + '</span>' + copyBtn(field) + '</div>' + control + '</div>';
    $('modal-step').innerHTML = '<div class="translate-form">'
      + fieldBlock('name', '<input data-tr-field="name" name="tr[' + code + '][name]" class="text-field" autocomplete="off" placeholder="' + escapeHtml(($('name_en').value || '').trim()) + '" value="' + escapeHtml(prior.name || '') + '">')
      + fieldBlock('description', '<textarea data-tr-field="description" name="tr[' + code + '][description]" class="text-field auto-grow" rows="2" spellcheck="false" placeholder="' + escapeHtml(($('description').value || '').trim()) + '">' + escapeHtml(prior.description || '') + '</textarea>')
      + qtyTable + '</div>';
    $('modal-actions').innerHTML = backBtn() + continueBtn('flow-translate-continue');
    renderRowSymbols($('modal-step'));
    $('modal-step').querySelectorAll('textarea').forEach(autoGrow);
    paintMath(document);
  }

  function renderSqlPage() {
    $('modal-title').textContent = '';
    $('modal-step').innerHTML = '<h3>' + escapeHtml(t('create.formula_insert')) + '</h3><div id="sql-formula-wrap"></div><h3>' + escapeHtml(t('create.token_inserts')) + '</h3><div id="sql-token-wrap"></div>';
    function renderHtml(body) {
      const wrapMap = { 'formula-sql': $('sql-formula-wrap'), 'token-sql': $('sql-token-wrap') };
      (new DOMParser().parseFromString(body, 'text/html')).querySelectorAll('.sql-block').forEach((block) => {
        const pre = block.querySelector('pre');
        const wrap = pre && wrapMap[pre.id];
        if (wrap) wrap.appendChild(block);
      });
      refreshIcons();
      flow.issueUrl = buildIssueUrl();
      $('modal-actions').innerHTML = backBtn()
        + '<a class="btn-primary btn-sm" id="open-issue-link" target="_blank" rel="noopener noreferrer" href="' + escapeHtml(flow.issueUrl) + '">'
        + escapeHtml(t('create.translate_open_issue', 'Open GitHub issue')) + '</a>';
    }
    function failToast(err) {
      // postJSON throws enriched Error with server message; legacy HTML falls back to data-error.
      var msg = err && err.message ? err.message : t('create.parse_error');
      if (err && err.html && !err.data) {
        const errEl = (new DOMParser().parseFromString(err.html, 'text/html')).querySelector('[data-error]');
        msg = errEl ? errEl.dataset.error : msg;
      }
      showToast(msg, 'error');
    }
    window.SFApi.postJSON('/create/build-sql', buildFinalFormData())
      .then((data) => renderHtml(data.html || ''))
      .catch(failToast);
  }

  function buildFinalFormData() {
    const fd = new FormData($('create-form'));
    for (const [loc, tr] of Object.entries(flow.translations)) {
      if (loc === 'en-us') continue;
      if (tr.name) fd.set('tr[' + loc + '][name]', tr.name);
      if (tr.description) fd.set('tr[' + loc + '][description]', tr.description);
      for (const [key, fields] of Object.entries(tr.overrides || {})) {
        for (const [fld, val] of Object.entries(fields)) {
          if (val) fd.set('tr_overrides[' + loc + '][' + key + '][' + fld + ']', val);
        }
      }
    }
    return fd;
  }

  function buildIssueUrl() {
    const repo = window._scifindRepo || 'Creeperman3000/Scifind';
    const labels = document.querySelectorAll('#modal-step pre');
    const parts = [];
    labels.forEach((pre) => {
      parts.push('### ' + (pre.id === 'formula-sql' ? t('create.formula_sql', 'Formula SQL') : t('create.token_sql', 'Token SQL')));
      parts.push('```sql', pre.textContent, '```', '');
    });
    return 'https://github.com/' + repo + '/issues/new?title=' + encodeURIComponent(($('name_en').value || '').trim())
      + '&labels=' + encodeURIComponent('formula') + '&body=' + encodeURIComponent(parts.join('\n').trimEnd() + '\n');
  }

  function startCreateFlow() {
    const missing = validateEnglishFields();
    if (missing.length) {
      showToast(t('create.missing_required') + ' ' + missing.join(', '), 'error');
      return;
    }
    const fd = collectOverrides();
    fd.set('equation', ($('equation').value || '').trim());
    function gotPreview(data) {
      flow.variables = (data && data.variables) || [];
      return window.SFApi.getJSON('/create/languages');
    }
    function started(langs) {
      flow.availableLanguages = (langs && langs.locales) || [];
      if (langs && langs.repo) window._scifindRepo = langs.repo;
      flow.history = [];
      flow.translations = {};
      $('modal-step').innerHTML = '';
      $('modal-actions').innerHTML = '';
      pushPage({ kind: 'pick', selected: [] });
      openModal();
    }
    function startFail(err) {
      showToast(window.SFApi.serverMessage(err, t('create.could_not_start', 'Could not start')), 'error');
    }
    window.SFApi.postJSON('/create/preview-render', fd).then(gotPreview).then(started, startFail).catch(startFail);
  }

  function onPickLangsContinue() {
    const page = currentPage();
    if (!page || page.kind !== 'pick') return;
    const checked = [...document.querySelectorAll('#lang-picker input[type=checkbox]:checked:not([disabled])')]
      .map((el) => el.dataset.langCode).filter(Boolean);
    page.selected = checked;
    pushPage(checked.length ? { kind: 'translate', code: checked[0], queue: checked.slice(1) } : { kind: 'sql' });
  }

  function onTranslateContinue() {
    const page = currentPage();
    if (!page || page.kind !== 'translate') return;
    captureTranslationForm(page.code);
    const next = page.queue[0];
    pushPage(next ? { kind: 'translate', code: next, queue: page.queue.slice(1) } : { kind: 'sql' });
  }

  function captureTranslationForm(code) {
    const step = $('modal-step');
    const entry = {}, overrides = {};
    const nameEl = step.querySelector('[data-tr-field="name"]'), descEl = step.querySelector('[data-tr-field="description"]');
    step.querySelectorAll('tr[data-key]').forEach((tr) => {
      const fields = {};
      tr.querySelectorAll('input[data-field]').forEach((inp) => {
        if (inp.value) fields[inp.dataset.field] = inp.value;
      });
      if (Object.keys(fields).length) overrides[tr.dataset.key] = fields;
    });
    if (nameEl && nameEl.value.trim()) entry.name = nameEl.value.trim();
    if (descEl && descEl.value.trim()) entry.description = descEl.value.trim();
    if (Object.keys(overrides).length) entry.overrides = overrides;
    if (Object.keys(entry).length) flow.translations[code] = entry;
    else delete flow.translations[code];
  }

  const flowActions = {
    'close-modal': closeModal,
    'continue-to-sql': startCreateFlow,
    'flow-pick-langs-continue': onPickLangsContinue,
    'flow-translate-continue': onTranslateContinue,
    'flow-back': () => {
      const page = currentPage();
      if (page && page.kind === 'translate') captureTranslationForm(page.code);
      popPage();
    },
    'copy-formula-sql': () => window.SFUtils.copyPreById('formula-sql', 'SQL'),
    'copy-token-sql': () => window.SFUtils.copyPreById('token-sql', 'SQL'),
    'toggle-token-section': (el) => {
      const list = $(el.dataset.target);
      if (!list) return;
      const collapsed = list.dataset.collapsed === '1';
      list.dataset.collapsed = collapsed ? '0' : '1';
      const icon = el.querySelector('.token-section-icon');
      if (icon) {
        icon.innerHTML = '<i data-lucide="' + (collapsed ? 'chevron-up' : 'chevron-down') + '" width="16" height="16"></i>';
        refreshIcons();
      }
    },
  };
  window.SFUtils.registerActions(flowActions);

  function createPreHandle(e) {
    const tokenItem = e.target.closest('.qty-result[data-insert]');
    if (tokenItem) { insertAtCursor(tokenItem.dataset.insert); return true; }

    const topicItem = e.target.closest('.topic-menu-item[data-id]');
    if (topicItem) {
      e.preventDefault(); e.stopPropagation();
      closeAllMenus();
      selectTopic(topicItem.dataset.id);
      return true;
    }

    const crumbNode = e.target.closest('.topic-current[data-id]');
    if (crumbNode && !crumbNode.classList.contains('has-menu')) {
      const parents = [...$('topic-bar').querySelectorAll('.topic-current[data-id]')];
      const parent = parents[parents.indexOf(crumbNode) - 1];
      selectTopic(parent ? parent.dataset.id : '');
      return true;
    }

    const trigger = e.target.closest('.topic-dropdown-trigger');
    if (trigger) {
      e.preventDefault(); e.stopPropagation();
      const menu = trigger.nextElementSibling;
      if (!menu) return true;
      const wasOpen = menu.classList.contains('open');
      closeAllMenus();
      if (!wasOpen) menu.classList.add('open');
      return true;
    }

    const trCopy = e.target.closest('[data-tr-copy]');
    if (trCopy) {
      const field = trCopy.dataset.trCopy;
      const target = document.querySelector('[data-tr-field="' + field + '"]');
      if (target) copyText(target.value || target.placeholder || '', trCopy.dataset.trCopyLabel || field);
      return true;
    }
    return false;
  }
  window.SFUtils.registerPreHandler(createPreHandle);
  window.SFUtils.installSingleClickListener();

  $('sidebar-left-inner').addEventListener('input', (e) => {
    if (e.target.id === 'token-search') filterTokenSidebar(e.target.value);
  });

  $('var-overrides').addEventListener('input', (e) => {
    if (e.target.name && e.target.name.startsWith('override[')) updatePreview($('equation').value);
  });

  /* Hover-intent submenu: one open/close timer pair, viewport-clamped. */
  let openSub = null, openItem = null, openTimer = 0, closeTimer = 0;
  function closeSubmenuNow() {
    if (openSub) openSub.style.display = '';
    openSub = openItem = null;
  }
  function openSubmenuNow(item, sub) {
    if (!item || !openSub || !openSub.contains(item)) closeSubmenuNow();
    const rect = item.getBoundingClientRect();
    sub.style.top = rect.top + 'px';
    sub.style.left = rect.right + 'px';
    sub.style.display = 'block';
    const sr = sub.getBoundingClientRect();
    if (sr.right > window.innerWidth) sub.style.left = (rect.left - sr.width) + 'px';
    if (sr.bottom > window.innerHeight) sub.style.top = (window.innerHeight - sr.height - 4) + 'px';
    openSub = sub; openItem = item;
  }
  const clearHoverTimers = () => { clearTimeout(openTimer); clearTimeout(closeTimer); };
  function submenuFromEvent(e) {
    const item = e.target.closest('.topic-menu-item');
    return item && item.querySelector(':scope > .topic-submenu') ? { item, sub: item.querySelector(':scope > .topic-submenu') } : null;
  }
  $('topic-bar').addEventListener('mouseover', (e) => {
    const found = submenuFromEvent(e);
    if (!found) return;
    clearTimeout(closeTimer);
    clearTimeout(openTimer);
    openTimer = setTimeout(() => openSubmenuNow(found.item, found.sub), 150);
  });
  $('topic-bar').addEventListener('mouseout', (e) => {
    const found = submenuFromEvent(e);
    if (!found) return;
    const to = e.relatedTarget;
    if (to && (found.item.contains(to) || (openSub && openSub.contains(to)))) return;
    clearTimeout(openTimer);
    clearTimeout(closeTimer);
    closeTimer = setTimeout(closeSubmenuNow, 250);
  });
  document.addEventListener('mouseover', (e) => {
    const sub = e.target.closest && e.target.closest('.topic-submenu');
    if (sub && sub === openSub) clearTimeout(closeTimer);
  });
  document.addEventListener('mouseout', (e) => {
    if (!openSub || !openSub.contains(e.target)) return;
    const to = e.relatedTarget;
    if (to && (openSub.contains(to) || (openItem && openItem.contains(to)))) return;
    clearTimeout(closeTimer);
    closeTimer = setTimeout(closeSubmenuNow, 250);
  });

  function closeAllMenus() {
    clearHoverTimers();
    openSub = openItem = null;
    const bar = $('topic-bar');
    if (!bar) return;
    bar.querySelectorAll('.topic-children-menu').forEach((m) => m.classList.remove('open'));
    bar.querySelectorAll('.topic-submenu').forEach((m) => m.style.display = '');
  }
  // Single overlay path: topic menus close via the central dispatcher,
  // same as settings/copy/sort menus (consistent click-outside behaviour).
  window.SFUtils.registerOverlayCloser((e) => {
    if ($('topic-bar') && !$('topic-bar').contains(e.target)) closeAllMenus();
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { closeAllMenus(); closeModal(); } });

  // Mirrors export.resolve_formula_id slug branch: collapse runs, strip ALL edges.
  const slugify = (s) => window.SFUtils.slugify(s);
  const isSlug = (s) => window.SFUtils.isSlug(s);
  const nameInput = $('name_en'), idInput = $('formula_id');
  nameInput.addEventListener('input', () => { if (!idInput.dataset.manual) idInput.value = slugify(nameInput.value); });
  idInput.addEventListener('input', () => { idInput.dataset.manual = idInput.value !== slugify(nameInput.value); });

  const diffInput = $('difficulty'), diffFill = $('diff-fill-create'), diffDisplay = $('diff-display');
  diffInput.addEventListener('input', () => {
    diffDisplay.textContent = diffInput.value + '/10';
    diffFill.style.width = ((diffInput.value - diffInput.min) / (diffInput.max - diffInput.min)) * 100 + '%';
  });
  diffFill.style.width = ((diffInput.value - diffInput.min) / (diffInput.max - diffInput.min)) * 100 + '%';

  /* Grows to fit content; binds once so translate-page textareas reuse it. */
  function autoGrow(ta) {
    if (!ta) return;
    const grow = () => { ta.style.height = 'auto'; ta.style.height = ta.scrollHeight + 'px'; };
    if (!ta.dataset.bound) {
      ta.dataset.bound = '1';
      ta.addEventListener('input', grow);
    }
    grow();
  }

  function init() {
    loadTokenSidebar();
    loadBreadcrumb('');
    const resetBtn = document.getElementById('tree-select-all');
    if (resetBtn) resetBtn.classList.add('disabled');
    renderOverrideTable([]);
    $('equation').addEventListener('input', (e) => updatePreview(e.target.value));
    [$('equation'), $('description'), $('links')].forEach(autoGrow);
    const sidebarRight = $('sidebar-right');
    if (sidebarRight) sidebarRight.addEventListener('click', (e) => {
      if (e.target.closest('#tree-select-all')) {
        e.stopImmediatePropagation();
        e.preventDefault();
        selectTopic(null);
      }
    }, true);
    refreshIcons();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
