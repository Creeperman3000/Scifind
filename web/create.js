/* eslint-disable no-undef */

(function() {
  'use strict';

  const $ = (id) => window.SFUtils.byId(id);
  const escapeHtml = (s) => window.SFUtils.escapeHtml(s);
  const t = (path, fallback) => window.SFUtils.t(path, fallback);
  const copyText = (text, label) => window.SFUtils.copyText(text, label);
  const slugify = (s) => window.SFUtils.slugify(s);
  // NOTE: SFUtils.isSlug intentionally not aliased (dead code, no callers).

  /* Paint KaTeX row symbols + auto-rendered math + icons in one call. */
  function paintMath(el) {
    if (typeof katex !== 'undefined' && el && el.querySelectorAll) {
      el.querySelectorAll('tr[data-symbol]').forEach((tr) => {
        const target = tr.querySelector('.qty-symbol');
        if (tr.dataset.symbol && target) {
          try { katex.render(tr.dataset.symbol, target, { displayMode: false, throwOnError: false }); } catch (e) {}
        }
      });
    }
    try {
      if (typeof renderMathInElement === 'function') renderMathInElement(el, { delimiters: [{ left: '$$', right: '$$', display: true }, { left: '$', right: '$', display: false }], macros: window._KATEX_MACROS || {} });
    } catch (e) {}
    if (typeof renderMathInContent === 'function') renderMathInContent();
    refreshIcons();
  }
  function setHTML(el, html) {
    el.innerHTML = typeof html === 'string' ? html : '';
    paintMath(el);
  }

  function loadTokenSidebar() {
    window.SFApi.getText('/create/token-sidebar').then((html) => {
      /* Drop late responses after SPA-navigating away (loadPage restores
         the filter sidebar; a stale write would re-hijack it). */
      if (window.location.pathname !== '/create') return;
      setHTML($('sidebar-left-inner'), html);
    });
  }
  function filterTokenSidebar(query) {
    const q = (query || '').toLowerCase().trim();
    $('sidebar-left-inner').querySelectorAll('.token-list').forEach((section) => {
      let visible = 0;
      section.querySelectorAll('.qty-result').forEach((el) => {
        const match = !q || (el.dataset.search || '').includes(q);
        el.style.display = match ? '' : 'none';
        if (match) visible++;
      });
      const empty = section.nextElementSibling;
      if (empty && empty.classList.contains('token-empty')) empty.style.display = (visible === 0 && section.dataset.collapsed !== '1') ? 'block' : 'none';
    });
  }

  /* ---- Live preview + variable overrides ---- */
  let previewSeq = 0, previewTimer = null, lastVariablesKey = '', _lastPreviewEq = null;
  const varKey = (v) => v.key || (v.id + '|' + (v.alias || ''));
  const variablesKey = (vars) => (vars || []).map(varKey).join(',');
  function collectOverrides() {
    const fd = new FormData();
    document.querySelectorAll('#var-overrides input[name^="override["]').forEach((inp) => { if (inp.value) fd.append(inp.name, inp.value); });
    return fd;
  }
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
    const cell = (field) => {
      const seed = (seeds && seeds[field]) || {};
      return '<td><input data-field="' + field + '" form="' + form + '" name="' + namePrefix + '[' + escapeHtml(key) + '][' + field + ']"'
        + ' placeholder="' + escapeHtml(seed.placeholder || '') + '"' + (seed.value ? ' value="' + escapeHtml(seed.value) + '"' : '') + ' class="text-field"></td>';
    };
    return '<tr data-symbol="' + escapeHtml(symbol) + '" data-key="' + escapeHtml(key) + '">'
      + '<td class="qty-sym-cell">' + (symbol ? '<span class="qty-symbol"></span> ' : '') + escapeHtml(displayName) + (alias ? '[' + escapeHtml(alias) + ']' : '')
      + (occ ? ' <span class="qty-occ">#' + occ + '</span>' : '') + '</td>' + cell('symbol') + cell('name') + '</tr>';
  }
  function varTable(rows) {
    const head = [t('detail.quantity'), t('create.column_symbol_override'), t('create.column_name_override')].map((h) => '<th>' + escapeHtml(h) + '</th>').join('');
    return '<table class="var-table var-overrides-table"><colgroup><col class="var-c1"><col class="var-c2"><col class="var-c3"></colgroup><thead><tr>' + head + '</tr></thead><tbody>' + rows + '</tbody></table>';
  }
  // Mirrors scifind_lib/i18n.py localise(value, locale).
  function localiseName(value, fallback) {
    const loc = (document.documentElement.lang || 'en-us').toLowerCase();
    if (value && typeof value === 'object') return value[loc] || value['en-us'] || fallback;
    if (!value || typeof value !== 'string' || !value.trim().startsWith('{')) return value || fallback;
    try {
      const obj = JSON.parse(value);
      return obj[loc] || obj['en-us'] || fallback;
    } catch (e) { return value; }
  }
  function renderOverrideTable(vars) {
    const wrap = $('var-overrides');
    if (!wrap) return;
    const real = vars && vars.length ? vars : [];
    const occ = occurrenceIndices(real);
    let rows = '';
    for (let i = 0; i < Math.max(3, real.length); i++) {
      const v = real[i];
      rows += v ? overrideRow(varKey(v), v.symbol || '', localiseName(v.name, v.id), v.alias, 'create-form', 'override', { name: { placeholder: t('create.placeholder_name') } }, occ[v.key])
        : '<tr class="qty-row-placeholder"><td class="qty-sym-cell">&nbsp;</td>' + '<td><input disabled class="text-field" placeholder=""></td>'.repeat(2) + '</tr>';
    }
    wrap.innerHTML = varTable(rows);
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
  function previewError(msg) {
    $('formula-math').innerHTML = '<span class="formula-error">' + escapeHtml(msg) + '</span>';
    $('formula-tex').textContent = '';
    $('dim-display').innerHTML = escapeHtml(t('detail.dimensions')) + ': <span class="dim-latex">$\\varnothing$</span>';
  }
  function previewOk(data, eq) {
    if (data.error) return previewError(data.error);
    if (!data.latex) return renderPreviewLaTeX('');
    renderPreviewLaTeX(data.latex);
    const dimEl = $('dim-display'), dimLatex = data.dim_latex || '\\varnothing';
    dimEl.innerHTML = escapeHtml(t('detail.dimensions')) + ': <span class="dim-latex"></span>';
    dimEl.style.opacity = (!eq.trim() || dimLatex === '\\varnothing') ? '0.6' : '';
    if (typeof katex !== 'undefined') katex.render(dimLatex, dimEl.querySelector('.dim-latex'), { displayMode: false, throwOnError: false });
  }
  function updatePreview(eq) {
    clearTimeout(previewTimer);
    const trimmed = (eq || '').trim();
    if (!trimmed) { previewSeq++; if (trimmed !== _lastPreviewEq) renderPreviewLaTeX(''); _lastPreviewEq = trimmed; return; }
    if (trimmed === _lastPreviewEq) return;
    const seq = ++previewSeq;
    previewTimer = setTimeout(() => {
      _lastPreviewEq = trimmed;
      const fd = collectOverrides();
      fd.set('equation', eq);
      window.SFApi.postJSON('/create/preview-render', fd).then((data) => {
        if (seq !== previewSeq) return;
        previewOk(data, eq);
        const newKey = variablesKey(data.variables);
        if (newKey !== lastVariablesKey) { lastVariablesKey = newKey; renderOverrideTable(data.variables || []); }
        paintMath(document);
      }, (err) => {
        if (seq !== previewSeq) return;
        showToast(window.SFApi.serverMessage(err, t('create.preview_failed', 'Preview failed')), 'error');
      });
    }, 200);
  }

  function insertAtCursor(text) {
    const ta = $('equation');
    const start = ta.selectionStart, end = ta.selectionEnd;
    const before = ta.value.substring(0, start), after = ta.value.substring(end);
    const isSep = (ch) => !ch || /\s/.test(ch) || '()[]'.includes(ch);
    const ins = ((!before.length || isSep(before[before.length - 1])) ? '' : ' ') + text + ((!after.length || isSep(after[0])) ? '' : ' ');
    ta.value = before + ins + after;
    ta.selectionStart = ta.selectionEnd = start + ins.length - ((!after.length || isSep(after[0])) ? 0 : 1);
    ta.focus();
    updatePreview(ta.value);
  }

  /* ---- Topic breadcrumb ---- */
  function selectTopic(id) {
    const hidden = $('topic');
    if (hidden) hidden.value = id || '';
    window.SFApi.getText('/create/breadcrumb' + (id ? '?topic=' + encodeURIComponent(id) : '')).then((html) => setHTML($('topic-bar'), html));
    const btn = document.getElementById('tree-select-all');
    if (btn) btn.classList.toggle('disabled', !id);
    if (typeof window._setTreeSelection === 'function') window._setTreeSelection(id);
  }

  /* ---- Wizard: pick → translate → sql ---- */
  const flow = { history: [], translations: {}, variables: [], issueUrl: null, availableLanguages: [] };
  const currentPage = () => flow.history[flow.history.length - 1] || null;
  function pushPage(page) { flow.history.push(page); renderPage(page); }
  function popPage() { if (flow.history.length > 1) { flow.history.pop(); renderPage(currentPage()); } }
  const langName = (code) => (flow.availableLanguages.find((l) => l.code === code) || {}).name || code;
  const resetFlow = () => { flow.history = []; flow.translations = {}; flow.variables = []; };
  function validateEnglishFields() {
    return [['name_en', 'create.name'], ['formula_id', 'create.formula_id'], ['topic', 'create.topic'], ['equation', 'create.equation']]
      .filter(([id]) => !(($(id) || {}).value || '').trim()).map(([, key]) => t(key).toLowerCase());
  }

  function closeModal() { window.SFUtils.setModal('sql-modal', false); resetFlow(); }
  const btn = (action, key, fb, primary) => '<button class="btn-' + (primary ? 'primary' : 'ghost') + ' btn-sm" type="button" data-action="' + action + '">' + escapeHtml(t(key, fb)) + '</button>';
  const backBtn = () => btn('flow-back', 'create.back', 'Back', false);
  const continueBtn = (action) => btn(action, 'create.continue', 'Continue', true);
  const RENDER = { pick: renderPickPage, translate: renderTranslatePage, sql: renderSqlPage };
  function renderPage(page) {
    if (!page) return;
    $('modal-step').dataset.kind = page.kind;
    RENDER[page.kind](page);
    $('modal-title').style.display = $('modal-title').textContent ? '' : 'none';
    refreshIcons();
  }

  function renderPickPage(page) {
    $('modal-title').textContent = t('create.pick_languages_heading', 'Translate this formula into how many languages?');
    const selected = new Set(page.selected || []);
    $('modal-step').innerHTML = '<p class="detail-desc">' + escapeHtml(t('create.pick_languages_hint', 'English is always included.')) + '</p>'
      + '<div class="lang-picker" id="lang-picker">' + flow.availableLanguages.map((lang) => {
        const isEn = lang.code === 'en-us';
        return '<label class="lang-row" for="lang-' + escapeHtml(lang.code) + '">'
          + '<input type="checkbox" id="lang-' + escapeHtml(lang.code) + '" data-lang-code="' + escapeHtml(lang.code) + '"'
          + ((isEn || selected.has(lang.code)) ? ' checked' : '') + (isEn ? ' disabled' : '') + '>'
          + '<span class="lang-cb"></span><span class="lang-name">' + escapeHtml(lang.name) + '</span>'
          + '<span class="lang-code">(' + escapeHtml(lang.code) + ')</span></label>';
      }).join('') + '</div>';
    $('modal-actions').innerHTML = continueBtn('flow-pick-langs-continue');
  }

  function renderTranslatePage(page) {
    const code = page.code;
    $('modal-title').textContent = t('create.translate_heading', 'Translate to {lang}').replace('{lang}', langName(code) + ' (' + code + ')');
    const prior = flow.translations[code] || {}, occ = occurrenceIndices(flow.variables);
    const qtyTable = flow.variables.length ? varTable(flow.variables.map((v) => {
      const key = varKey(v), priorOv = (prior.overrides && prior.overrides[key]) || {};
      return overrideRow(key, v.symbol || '', localiseName(v.name, v.id), v.alias, 'create-form', 'tr_overrides[' + code + ']',
        { symbol: { placeholder: v.symbol || '', value: priorOv.symbol || '' }, name: { placeholder: localiseName(v.name, v.id), value: priorOv.name || '' } }, occ[key]);
    }).join('')) : '';
    const fieldBlock = (field, control) =>
      '<div class="detail-desc"><div class="tr-label-row"><span>' + escapeHtml(t('create.' + field)) + '</span>'
      + '<button class="filter-btn" type="button" data-tr-copy="' + field + '" data-tr-copy-label="' + escapeHtml(t('create.' + field, field)) + '" title="'
      + escapeHtml(t('create.copy_from_english', 'Copy from English')) + '"><i data-lucide="copy" width="16" height="16"></i></button></div>' + control + '</div>';
    $('modal-step').innerHTML = '<div class="translate-form">'
      + fieldBlock('name', '<input data-tr-field="name" name="tr[' + code + '][name]" class="text-field" autocomplete="off" placeholder="' + escapeHtml(($('name_en').value || '').trim()) + '" value="' + escapeHtml(prior.name || '') + '">')
      + fieldBlock('description', '<textarea data-tr-field="description" name="tr[' + code + '][description]" class="text-field auto-grow" rows="2" spellcheck="false" placeholder="' + escapeHtml(($('description').value || '').trim()) + '">' + escapeHtml(prior.description || '') + '</textarea>')
      + qtyTable + '</div>';
    $('modal-actions').innerHTML = backBtn() + continueBtn('flow-translate-continue');
    $('modal-step').querySelectorAll('textarea').forEach(autoGrow);
    paintMath(document);
  }

  function renderSqlPage() {
    $('modal-title').textContent = '';
    $('modal-step').innerHTML = '';
    window.SFApi.postJSON('/create/build-sql', buildFinalFormData()).then((data) => {
      $('modal-step').innerHTML = data.html || '';
      $('modal-step').scrollTop = 0;
      refreshIcons();
      flow.issueUrl = buildIssueUrl();
      $('modal-actions').innerHTML = backBtn()
        + '<a class="btn-primary btn-sm" id="open-issue-link" target="_blank" rel="noopener noreferrer" href="' + escapeHtml(flow.issueUrl) + '">'
        + escapeHtml(t('create.translate_open_issue', 'Open GitHub issue')) + '</a>';
    }).catch((err) => {
      // postJSON throws enriched Error with server message; legacy HTML falls back to data-error.
      let msg = (err && err.message) || t('create.parse_error');
      if (err && err.html && !err.data) {
        const errEl = (new DOMParser().parseFromString(err.html, 'text/html')).querySelector('[data-error]');
        if (errEl) msg = errEl.dataset.error;
      }
      showToast(msg, 'error');
    });
  }

  function buildFinalFormData() {
    const fd = new FormData($('create-form'));
    for (const [loc, tr] of Object.entries(flow.translations)) {
      if (loc === 'en-us') continue;
      if (tr.name) fd.set('tr[' + loc + '][name]', tr.name);
      if (tr.description) fd.set('tr[' + loc + '][description]', tr.description);
      for (const [key, fields] of Object.entries(tr.overrides || {})) for (const [fld, val] of Object.entries(fields)) {
        if (val) fd.set('tr_overrides[' + loc + '][' + key + '][' + fld + ']', val);
      }
    }
    return fd;
  }
  function buildIssueUrl() {
    const repo = window._scifindRepo || 'Creeperman3000/Scifind';
    const parts = [];
    document.querySelectorAll('#modal-step pre').forEach((pre) => {
      parts.push('### ' + (pre.id === 'formula-sql' ? t('create.formula_sql', 'Formula SQL') : t('create.token_sql', 'Token SQL')));
      parts.push('```sql', pre.textContent, '```', '');
    });
    return 'https://github.com/' + repo + '/issues/new?title=' + encodeURIComponent(($('name_en').value || '').trim())
      + '&labels=' + encodeURIComponent('formula') + '&body=' + encodeURIComponent(parts.join('\n').trimEnd() + '\n');
  }

  function startCreateFlow() {
    const missing = validateEnglishFields();
    if (missing.length) { showToast(t('create.missing_required') + ' ' + missing.join(', '), 'error'); return; }
    const fd = collectOverrides();
    fd.set('equation', ($('equation').value || '').trim());
    window.SFApi.postJSON('/create/preview-render', fd).then((data) => {
      flow.variables = (data && data.variables) || [];
      return window.SFApi.getJSON('/create/languages');
    }).then((langs) => {
      flow.availableLanguages = (langs && langs.locales) || [];
      if (langs && langs.repo) window._scifindRepo = langs.repo;
      resetFlow();
      $('modal-step').innerHTML = '';
      $('modal-actions').innerHTML = '';
      pushPage({ kind: 'pick', selected: [] });
      window.SFUtils.setModal('sql-modal', true);
    }).catch((err) => showToast(window.SFApi.serverMessage(err, t('create.could_not_start', 'Could not start')), 'error'));
  }

  function nextTranslatePage(queue) {
    return queue.length ? { kind: 'translate', code: queue[0], queue: queue.slice(1) } : { kind: 'sql' };
  }
  function onPickLangsContinue() {
    const page = currentPage();
    if (!page || page.kind !== 'pick') return;
    const checked = [...document.querySelectorAll('#lang-picker input[type=checkbox]:checked:not([disabled])')].map((el) => el.dataset.langCode).filter(Boolean);
    page.selected = checked;
    pushPage(nextTranslatePage(checked));
  }
  function captureTranslationForm(code) {
    const step = $('modal-step'), entry = {}, overrides = {};
    step.querySelectorAll('tr[data-key]').forEach((tr) => {
      const fields = {};
      tr.querySelectorAll('input[data-field]').forEach((inp) => { if (inp.value) fields[inp.dataset.field] = inp.value; });
      if (Object.keys(fields).length) overrides[tr.dataset.key] = fields;
    });
    const name = (step.querySelector('[data-tr-field="name"]') || {}).value || '', desc = (step.querySelector('[data-tr-field="description"]') || {}).value || '';
    if (name.trim()) entry.name = name.trim();
    if (desc.trim()) entry.description = desc.trim();
    if (Object.keys(overrides).length) entry.overrides = overrides;
    if (Object.keys(entry).length) flow.translations[code] = entry;
    else delete flow.translations[code];
  }
  function onTranslateContinue() {
    const page = currentPage();
    if (!page || page.kind !== 'translate') return;
    captureTranslationForm(page.code);
    pushPage(nextTranslatePage(page.queue));
  }

  /* Document-level wiring runs once (deferred deps + SPA re-exec safe);
     element bindings re-run every init (SPA swaps the DOM). */
  const _actions = {
    'close-modal': closeModal,
    'continue-to-sql': startCreateFlow,
    'flow-pick-langs-continue': onPickLangsContinue,
    'flow-translate-continue': onTranslateContinue,
    'flow-back': () => {
      const page = currentPage();
      if (page && page.kind === 'translate') captureTranslationForm(page.code);
      popPage();
    },
    'toggle-token-section': (e, el) => {
      if (!el) return;
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
  function wireOnce() {
    // Persist across SPA re-execs (fresh IIFE each visit shares the singletons).
    if (window._sfCreateWired) return;
    window._sfCreateWired = true;
    window.SFUtils.registerActions(_actions);
    window.SFUtils.registerPreHandler(createPreHandle);
    window.SFUtils.installSingleClickListener();
    // Single overlay path: topic menus close via the central dispatcher,
    // same as settings/copy/sort menus (consistent click-outside behaviour).
    window.SFUtils.registerOverlayCloser((e) => { if ($('topic-bar') && !$('topic-bar').contains(e.target)) closeAllMenus(); });
    document.addEventListener('mouseover', (e) => { if (openSub && e.target.closest && e.target.closest('.topic-submenu') === openSub) clearTimeout(closeTimer); });
    document.addEventListener('mouseout', (e) => {
      if (!openSub || !openSub.contains(e.target)) return;
      const to = e.relatedTarget;
      if (to && (openSub.contains(to) || (openItem && openItem.contains(to)))) return;
      clearTimeout(closeTimer);
      closeTimer = setTimeout(closeSubmenuNow, 250);
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { closeAllMenus(); closeModal(); } });
  }

  /* ---- Delegated clicks + topic chrome ---- */
  function createPreHandle(e) {
    const tokenItem = e.target.closest('.qty-result[data-insert]');
    if (tokenItem) { insertAtCursor(tokenItem.dataset.insert); return true; }
    const topicItem = e.target.closest('.topic-menu-item[data-id]');
    if (topicItem) { e.preventDefault(); e.stopPropagation(); closeAllMenus(); selectTopic(topicItem.dataset.id); return true; }
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
      const target = document.querySelector('[data-tr-field="' + trCopy.dataset.trCopy + '"]');
      if (target) copyText(target.value || target.placeholder || '', trCopy.dataset.trCopyLabel || trCopy.dataset.trCopy);
      return true;
    }
    return false;
  }
  /* Hover-intent submenu: one open/close timer pair, viewport-clamped. */
  let openSub = null, openItem = null, openTimer = 0, closeTimer = 0;
  const clearHoverTimers = () => { clearTimeout(openTimer); clearTimeout(closeTimer); };
  function submenuFromEvent(e) {
    const item = e.target.closest('.topic-menu-item');
    return item && item.querySelector(':scope > .topic-submenu') ? { item, sub: item.querySelector(':scope > .topic-submenu') } : null;
  }
  function closeSubmenuNow() { if (openSub) openSub.style.display = ''; openSub = openItem = null; }
  function openSubmenuNow(item, sub) {
    if (!item || !openSub || !openSub.contains(item)) closeSubmenuNow();
    const rect = item.getBoundingClientRect();
    Object.assign(sub.style, { top: rect.top + 'px', left: rect.right + 'px', display: 'block' });
    const sr = sub.getBoundingClientRect();
    if (sr.right > window.innerWidth) sub.style.left = (rect.left - sr.width) + 'px';
    if (sr.bottom > window.innerHeight) sub.style.top = (window.innerHeight - sr.height - 4) + 'px';
    openSub = sub; openItem = item;
  }
  function closeAllMenus() {
    clearHoverTimers();
    openSub = openItem = null;
    const bar = $('topic-bar');
    if (!bar) return;
    bar.querySelectorAll('.topic-children-menu').forEach((m) => m.classList.remove('open'));
    bar.querySelectorAll('.topic-submenu').forEach((m) => m.style.display = '');
  }

  /* Grows to fit content; binds once so translate-page textareas reuse it. */
  function autoGrow(ta) {
    if (!ta) return;
    const grow = () => { ta.style.height = 'auto'; ta.style.height = ta.scrollHeight + 'px'; };
    if (!ta.dataset.bound) { ta.dataset.bound = '1'; ta.addEventListener('input', grow); }
    grow();
  }

  function init() {
    // Deferred core scripts (utils/api) run before DOMContentLoaded; on SPA
    // re-exec the DOM is new but the singletons persist, so re-init safely.
    if (!window.SFUtils || !window.SFApi) return;
    wireOnce();
    window._treeSelectionChanged = (id) => selectTopic(id);

    const sidebarLeft = $('sidebar-left-inner');
    if (sidebarLeft) sidebarLeft.addEventListener('input', (e) => { if (e.target.id === 'token-search') filterTokenSidebar(e.target.value); });
    const overrides = $('var-overrides');
    if (overrides) overrides.addEventListener('input', (e) => { if (e.target.name && e.target.name.startsWith('override[')) updatePreview($('equation').value); });

    const bar = $('topic-bar');
    if (bar) {
      bar.addEventListener('mouseover', (e) => {
        const found = submenuFromEvent(e);
        if (!found) return;
        clearTimeout(closeTimer);
        clearTimeout(openTimer);
        openTimer = setTimeout(() => openSubmenuNow(found.item, found.sub), 150);
      });
      bar.addEventListener('mouseout', (e) => {
        const found = submenuFromEvent(e);
        if (!found) return;
        const to = e.relatedTarget;
        if (to && (found.item.contains(to) || (openSub && openSub.contains(to)))) return;
        clearHoverTimers();
        closeTimer = setTimeout(closeSubmenuNow, 250);
      });
    }

    // Mirrors export.resolve_formula_id slug branch: collapse runs, strip ALL edges.
    const nameInput = $('name_en'), idInput = $('formula_id');
    if (nameInput && idInput) {
      nameInput.addEventListener('input', () => { if (!idInput.dataset.manual) idInput.value = slugify(nameInput.value); });
      idInput.addEventListener('input', () => { idInput.dataset.manual = idInput.value !== slugify(nameInput.value); });
    }

    const diffInput = $('difficulty'), diffFill = $('diff-fill-create'), diffDisplay = $('diff-display');
    const syncDiff = () => {
      if (!diffInput || !diffFill || !diffDisplay) return;
      diffDisplay.textContent = diffInput.value + '/10';
      diffFill.style.width = ((diffInput.value - diffInput.min) / (diffInput.max - diffInput.min)) * 100 + '%';
    };
    if (diffInput) diffInput.addEventListener('input', syncDiff);
    syncDiff();

    loadTokenSidebar();
    window.SFApi.getText('/create/breadcrumb').then((html) => {
      if (window.location.pathname !== '/create' || !$('topic-bar')) return;
      setHTML($('topic-bar'), html);
    });
    document.getElementById('tree-select-all')?.classList.add('disabled');
    renderOverrideTable([]);
    const eq = $('equation');
    if (eq) eq.addEventListener('input', (e) => updatePreview(e.target.value));
    [$('equation'), $('description'), $('links')].forEach(autoGrow);
    const sideRight = $('sidebar-right');
    if (sideRight) sideRight.addEventListener('click', (e) => {
      if (e.target.closest('#tree-select-all')) { e.stopImmediatePropagation(); e.preventDefault(); selectTopic(null); }
    }, true);
    refreshIcons();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
