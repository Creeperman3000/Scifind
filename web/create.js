/* eslint-disable no-undef */

(function() {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? '' : s)
    .replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const t = (path, fallback) => {
    const ui = window._localeUI || {};
    const parts = path.split('.');
    let cur = ui;
    for (const p of parts) { if (cur && typeof cur === 'object' && p in cur) cur = cur[p]; else return fallback; }
    return cur || fallback;
  };

  const renderMathIn = (el) => { try { renderMathInElement(el,{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],macros:window._KATEX_MACROS||{}}); } catch(e) {} };
  const refreshIcons = () => { if (typeof lucide !== 'undefined') lucide.createIcons(); };
  const refreshMath = () => { if (typeof renderMathInContent === 'function') renderMathInContent(); };
  const copyText = (text, label) => {
    if (!(navigator.clipboard && navigator.clipboard.writeText)) return;
    const copied = t('toast.copied', 'Copied');
    navigator.clipboard.writeText(text)
      .then(() => showToast(copied + ' ' + label, 'success'))
      .catch((e) => showToast(t('toast.copy_failed', 'Copy failed') + ': ' + e.message, 'error'));
  };
  function renderRowSymbols(root) {
    if (typeof katex === 'undefined') return;
    root.querySelectorAll('tr[data-symbol]').forEach((tr) => {
      const sym = tr.dataset.symbol;
      if (!sym) return;
      const target = tr.querySelector('.qty-symbol');
      if (target) katex.render(sym, target, { displayMode: false, throwOnError: false });
    });
  }
  const varTableHead = () => '<thead><tr>' +
    [t('detail.quantity'), t('create.column_symbol_override'), t('create.column_name_override'), t('create.column_label')]
      .map((h) => '<th>' + esc(h) + '</th>').join('') + '</tr></thead>';
  function setHTML(el, html) {
    el.innerHTML = typeof html === 'string' ? html : '';
    refreshMath();
    if (el) renderMathIn(el);
    refreshIcons();
  }

  function loadTokenSidebar() {
    fetch('/create/token-sidebar')
      .then((r) => r.text())
      .then((html) => setHTML($('sidebar-left-inner'), html));
  }

  function filterTokenSidebar(query) {
    const q = (query || '').toLowerCase().trim();
    $('sidebar-left-inner').querySelectorAll('.token-list').forEach((grid) => {
      let visible = 0;
      grid.querySelectorAll('.qty-result').forEach((el) => {
        const match = !q || (el.dataset.search || '').includes(q);
        el.style.display = match ? '' : 'none';
        if (match) visible++;
      });
      const empty = grid.nextElementSibling;
      const collapsed = grid.dataset.collapsed === '1';
      if (empty && empty.classList.contains('token-empty')) {
        empty.style.display = (visible === 0 && !collapsed) ? 'block' : 'none';
      }
    });
  }

  let previewSeq = 0, previewTimer = null;
  let lastVariablesKey = '';
  function collectOverrides() {
    const fd = new FormData();
    document.querySelectorAll('#var-overrides input[name^="override["]').forEach((inp) => {
      if (inp.value) fd.append(inp.name, inp.value);
    });
    return fd;
  }
  function variablesKey(vars) {
    return (vars || []).map((v) => v.key || (v.id + '|' + (v.alias || ''))).join(',');
  }
  function overrideRow(key, symbol, displayName, alias, form, namePrefix, opts, occ) {
    const symCell = symbol ? '<span class="qty-symbol"></span>' : '';
    const occTag = occ ? ' <span class="qty-occ">#' + occ + '</span>' : '';
    const cellBody = symCell + ' ' + esc(displayName) + (alias ? '[' + esc(alias) + ']' : '') + occTag;
    const input = (field) => {
      const seed = (opts && opts[field]) || {};
      return '<input data-field="' + field + '" form="' + form + '" name="' + namePrefix + '[' + esc(key) + '][' + field + ']"'
        + ' placeholder="' + esc(seed.placeholder || '') + '"'
        + (seed.value ? ' value="' + esc(seed.value) + '"' : '')
        + ' class="text-field">';
    };
    return '<tr data-symbol="' + esc(symbol) + '" data-key="' + esc(key) + '">'
      + '<td class="qty-sym-cell">' + cellBody + '</td>'
      + '<td>' + input('symbol') + '</td>'
      + '<td>' + input('name') + '</td>'
      + '<td>' + input('label') + '</td>'
      + '</tr>';
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
  function renderOverrideTable(vars) {
    const wrap = $('var-overrides');
    if (!wrap) return;
    const real = vars && vars.length ? vars : [];
    const totalRows = Math.max(3, real.length);
    const occ = occurrenceIndices(real);
    let rows = '';
    for (let i = 0; i < totalRows; i++) {
      const v = real[i];
      if (v) {
        rows += overrideRow(
          v.key || (v.id + '|' + (v.alias || '')),
          v.symbol || '',
          localiseName(v.name, v.id),
          v.alias,
          'create-form',
          'override',
          {
            symbol: { placeholder: t('unit.symbol') },
            name:   { placeholder: t('create.placeholder_name') },
            label:  { placeholder: t('create.placeholder_label') },
          },
          occ[v.key]
        );
      } else {
        rows += '<tr class="qty-row-placeholder">'
          + '<td class="qty-sym-cell">&nbsp;</td>'
          + '<td><input disabled class="text-field" placeholder=""></td>'.repeat(3)
          + '</tr>';
      }
    }
    wrap.innerHTML = '<table class="var-table">' + varTableHead() + '<tbody>' + rows + '</tbody></table>';
    renderRowSymbols(wrap);
    refreshMath();
  }
  function renderPreviewLaTeX(latex) {
    const mathEl = $('formula-math');
    const texEl = $('formula-tex');
    if (mathEl) {
      if (latex) {
        mathEl.classList.remove('formula-placeholder');
        mathEl.textContent = '$$' + latex + '$$';
      } else {
        mathEl.classList.add('formula-placeholder');
        mathEl.textContent = '$$F = ma$$';
      }
    }
    if (texEl) texEl.textContent = latex || 'F = ma';
  }
  function localiseName(value, fallback) {
    if (!value) return fallback;
    if (typeof value !== 'string' || !value.trim().startsWith('{')) return value;
    try {
      const obj = JSON.parse(value);
      const loc = (document.documentElement.lang || 'en-us').toLowerCase();
      return obj[loc] || obj['en-us'] || fallback;
    } catch (e) {
      return value;
    }
  }
  function updatePreview(eq) {
    clearTimeout(previewTimer);
    const seq = ++previewSeq;
    previewTimer = setTimeout(() => {
      const dimEl = $('dim-display');
      const fd = collectOverrides();
      fd.set('equation', eq);
      fetch('/create/preview-render', { method: 'POST', body: fd })
        .then((r) => r.json())
        .then((data) => {
          if (seq !== previewSeq) return;
          if (data.error) {
            $('formula-math').innerHTML = '<span class="formula-error">' + esc(data.error) + '</span>';
            $('formula-tex').textContent = '';
            dimEl.innerHTML = esc(t('detail.dimensions')) + ': <span class="dim-latex">$\\varnothing$</span>';
          } else if (data.latex) {
            renderPreviewLaTeX(data.latex);
            const dimLatex = data.dim_latex || '\\varnothing';
            const muted = !eq.trim() || dimLatex === '\\varnothing';
            dimEl.innerHTML = esc(t('detail.dimensions')) + ': <span class="dim-latex"></span>';
            dimEl.style.opacity = muted ? '0.6' : '';
            if (typeof katex !== 'undefined') katex.render(dimLatex, dimEl.querySelector('.dim-latex'), { displayMode: false, throwOnError: false });
          } else {
            renderPreviewLaTeX('');
          }
          const newKey = variablesKey(data.variables);
          if (newKey !== lastVariablesKey) {
            lastVariablesKey = newKey;
            renderOverrideTable(data.variables || []);
          }
          refreshMath();
        })
        .catch((err) => {
          if (seq !== previewSeq) return;
          console.error('preview failed:', err);
          showToast('Preview failed: ' + err.message, 'error');
        });
    }, 200);
  }

  function isSep(ch) { return !ch || /\s/.test(ch) || '()[]'.indexOf(ch) !== -1; }
  function insertAtCursor(text) {
    const ta = $('equation');
    const start = ta.selectionStart, end = ta.selectionEnd;
    const before = ta.value.substring(0, start);
    const after = ta.value.substring(end);
    const padL = before.length && !isSep(before[before.length - 1]);
    const padR = after.length && !isSep(after[0]);
    const ins = (padL ? ' ' : '') + text + (padR ? ' ' : '');
    ta.value = before + ins + after;
    const pos = start + ins.length - (padR ? 1 : 0);
    ta.selectionStart = ta.selectionEnd = pos;
    ta.focus();
    updatePreview(ta.value);
  }

  function syncTreeResetBtn(topicSelected) {
    const btn = document.getElementById('tree-select-all');
    if (btn) btn.classList.toggle('disabled', !topicSelected);
  }
  /* Tree clicks (radio mode, wired up by app.js) */
  window._treeSelectionChanged = function(id) { selectTopic(id); };
  function selectTopic(id) {
    const hidden = $('topic');
    if (hidden) hidden.value = id || '';
    loadBreadcrumb(id);
    syncTreeResetBtn(!!id);
    if (typeof window._setTreeSelection === 'function') window._setTreeSelection(id);
  }
  function loadBreadcrumb(topic) {
    const url = '/create/breadcrumb' + (topic ? '?topic=' + encodeURIComponent(topic) : '');
    fetch(url)
      .then((r) => r.text())
      .then((html) => setHTML($('topic-bar'), html));
  }

  function openModal() { $('sql-modal').classList.add('open'); }
  function closeModal() {
    $('sql-modal').classList.remove('open');
    flow.history = [];
    flow.translations = {};
    flow.variables = [];
  }

  const flow = {
    history: [],            // [{kind: 'pick' | 'translate' | 'sql', ...}, ...]
    translations: {},       // { 'cs-cz': { name, description, overrides } }
    variables: [],          // [{ id, alias, symbol, name, name_overwrite }, ...]
    issueUrl: null,         // populated on the SQL page
    availableLanguages: [], // [{code, name}, ...]
  };

  function currentPage() {
    return flow.history[flow.history.length - 1] || null;
  }
  function pushPage(page) {
    flow.history.push(page);
    renderPage(page);
  }
  function popPage() {
    if (flow.history.length <= 1) return; // can't pop the first page
    flow.history.pop();
    renderPage(currentPage());
  }
  function langName(code) {
    const e = flow.availableLanguages.find((l) => l.code === code);
    return e ? e.name : code;
  }
  function substituteTemplate(str, replacements) {
    return String(str).replace(/\{(\w+)\}/g, (m, k) => (k in replacements ? replacements[k] : m));
  }

  function validateEnglishFields() {
    const fields = [
      ['name_en', 'create.name'],
      ['formula_id', 'create.formula_id'],
      ['topic', 'create.topic'],
      ['equation', 'create.equation'],
    ];
    return fields
      .filter(([id]) => { const el = $(id); return !(el && (el.value || '').trim()); })
      .map(([, key]) => t(key).toLowerCase());
  }

  function renderPage(page) {
    if (!page) return;
    $('modal-step').dataset.kind = page.kind;
    if (page.kind === 'pick') renderPickPage(page);
    else if (page.kind === 'translate') renderTranslatePage(page);
    else if (page.kind === 'sql') renderSqlPage(page);
    refreshIcons();
  }

  function setTitle(text) { $('modal-title').textContent = text; }
  function setStep(html) { $('modal-step').innerHTML = html; }
  function setActions(html) { $('modal-actions').innerHTML = html; }
  function backButtonHtml() {
    return '<button class="btn-ghost btn-sm" type="button" data-action="flow-back">' +
      esc(t('create.back', 'Back')) + '</button>';
  }

  function renderPickPage(page) {
    setTitle(t('create.pick_languages_heading', 'Translate this formula into how many languages?'));
    const hint = t('create.pick_languages_hint', 'English is always included.');
    const selected = new Set(page.selected || []);
    let rows = '';
    for (const lang of flow.availableLanguages) {
      const isEn = lang.code === 'en-us';
      const id = 'lang-' + esc(lang.code);
      const checked = (isEn || selected.has(lang.code)) ? ' checked' : '';
      const disabled = isEn ? ' disabled' : '';
      rows +=
        '<label class="lang-row" for="' + id + '">' +
        '<input type="checkbox" id="' + id + '" data-lang-code="' + esc(lang.code) + '"' + checked + disabled + '>' +
        '<span class="lang-cb"></span>' +
        '<span class="lang-name">' + esc(lang.name) + '</span>' +
        '<span class="lang-code">(' + esc(lang.code) + ')</span>' +
        '</label>';
    }
    setStep(
      '<p class="detail-desc">' + esc(hint) + '</p>' +
      '<div class="lang-picker" id="lang-picker">' + rows + '</div>'
    );
    setActions(
      '<button class="btn-primary btn-sm" type="button" data-action="flow-pick-langs-continue">' +
        esc(t('create.continue', 'Continue')) +
      '</button>'
    );
  }

  function renderTranslatePage(page) {
    const code = page.code;
    setTitle(substituteTemplate(
      t('create.translate_heading', 'Translate to {lang}'),
      { lang: langName(code) + ' (' + code + ')' }
    ));
    const prior = flow.translations[code] || {};
    const occ = occurrenceIndices(flow.variables);
    let qtyRows = '';
    for (const v of flow.variables) {
      const key = v.key || (v.id + '|' + (v.alias || ''));
      const priorOv = (prior.overrides && prior.overrides[key]) || {};
      qtyRows += overrideRow(
        key,
        v.symbol || '',
        localiseName(v.name, v.id),
        v.alias,
        'create-form',
        'tr_overrides[' + code + ']',
        {
          symbol: { placeholder: v.symbol || '', value: priorOv.symbol || '' },
          name:   { placeholder: localiseName(v.name, v.id), value: priorOv.name || '' },
          label:  { placeholder: t('create.placeholder_label'), value: priorOv.label || '' },
        },
        occ[key]
      );
    }
    const qtyTable = qtyRows
      ? '<table class="var-table">' + varTableHead() + '<tbody>' + qtyRows + '</tbody></table>'
      : '';
    const enName = ($('name_en').value || '').trim();
    const enDesc = ($('description').value || '').trim();
    const copyBtn = (field) =>
      '<button class="filter-btn" type="button" data-tr-copy="' + field + '" data-tr-copy-label="' + esc(t('create.' + field, field)) + '" title="Copy from English">' +
      '<i data-lucide="copy" width="16" height="16"></i></button>';
    setStep(
      '<div class="translate-form">' +
        '<div class="detail-desc"><div class="tr-label-row"><span>' + esc(t('create.name')) + '</span>' + copyBtn('name') + '</div>' +
        '<input data-tr-field="name" name="tr[' + code + '][name]" class="text-field" autocomplete="off" placeholder="' + esc(enName) + '" value="' + esc(prior.name || '') + '">' +
        '</div>' +
        '<div class="detail-desc"><div class="tr-label-row"><span>' + esc(t('create.description')) + '</span>' + copyBtn('description') + '</div>' +
        '<textarea data-tr-field="description" name="tr[' + code + '][description]" class="text-field auto-grow" rows="2" spellcheck="false" placeholder="' + esc(enDesc) + '">' + esc(prior.description || '') + '</textarea>' +
        '</div>' +
        qtyTable +
      '</div>'
    );
    setActions(
      backButtonHtml() +
      '<button class="btn-primary btn-sm" type="button" data-action="flow-translate-continue">' +
        esc(t('create.continue', 'Continue')) +
      '</button>'
    );

    renderRowSymbols($('modal-step'));
    $('modal-step').querySelectorAll('textarea').forEach(bindAutoGrow);
    refreshMath();
  }

  function renderSqlPage(page) {
    setTitle('');
    setStep('<h3>' + esc(t('create.formula_insert')) + '</h3><div id="sql-formula-wrap"></div><h3>' + esc(t('create.token_inserts')) + '</h3><div id="sql-token-wrap"></div>');

    const fd = buildFinalFormData();
    fetch('/create/build-sql', { method: 'POST', body: fd })
      .then(async (r) => ({ ok: r.ok, body: await r.text() }))
      .then((out) => {
        if (!out.ok) {
          const errEl = (new DOMParser().parseFromString(out.body, 'text/html')).querySelector('[data-error]');
          showToast(errEl ? errEl.dataset.error : t('create.parse_error'), 'error');
          return;
        }
        const doc = new DOMParser().parseFromString(out.body, 'text/html');
        const blocks = doc.querySelectorAll('.sql-block');
        const wrapMap = { 'formula-sql': $('sql-formula-wrap'), 'token-sql': $('sql-token-wrap') };
        blocks.forEach((block) => {
          const pre = block.querySelector('pre');
          if (!pre) return;
          const wrap = wrapMap[pre.id];
          if (wrap) wrap.appendChild(block);
        });
        refreshIcons();
        flow.issueUrl = buildIssueUrl();
        setActions(
          backButtonHtml() +
          '<a class="btn-primary btn-sm" id="open-issue-link" target="_blank" rel="noopener noreferrer" href="' + esc(flow.issueUrl) + '" data-action="open-issue">' +
            esc(t('create.translate_open_issue', 'Open GitHub issue')) +
          '</a>'
        );
      })
      .catch((err) => showToast(t('create.parse_error', 'Build failed') + ': ' + err.message, 'error'));
  }

  function buildFinalFormData() {
    const fd = new FormData($('create-form'));
    for (const [loc, tr] of Object.entries(flow.translations)) {
      if (loc === 'en-us') continue;
      if (tr.name) fd.set('tr[' + loc + '][name]', tr.name);
      if (tr.description) fd.set('tr[' + loc + '][description]', tr.description);
      if (tr.overrides) {
        for (const [key, fields] of Object.entries(tr.overrides)) {
          for (const [fld, val] of Object.entries(fields)) {
            if (val) fd.set('tr_overrides[' + loc + '][' + key + '][' + fld + ']', val);
          }
        }
      }
    }
    return fd;
  }

  function buildIssueUrl() {
    const repo = (window._scifindRepo || 'Creeperman3000/Scifind');
    const title = ($('name_en').value || '').trim();
    const body = buildIssueBody();
    const params =
      '?title=' + encodeURIComponent(title) +
      '&labels=' + encodeURIComponent('formula') +
      '&body=' + encodeURIComponent(body);
    return 'https://github.com/' + repo + '/issues/new' + params;
  }
  function buildIssueBody() {
    const parts = [];
    const sqlBlocks = document.querySelectorAll('#modal-step pre');
    sqlBlocks.forEach((pre) => {
      const label = pre.id === 'formula-sql' ? 'Formula SQL' : 'Token SQL';
      parts.push('### ' + label);
      parts.push('```sql');
      parts.push(pre.textContent);
      parts.push('```');
      parts.push('');
    });
    return parts.join('\n').trimEnd() + '\n';
  }

  function startCreateFlow() {
    const missing = validateEnglishFields();
    if (missing.length) {
      showToast(t('create.missing_required') + ' ' + missing.join(', '), 'error');
      return;
    }
    const fd = collectOverrides();
    fd.set('equation', ($('equation').value || '').trim());
    fetch('/create/preview-render', { method: 'POST', body: fd })
      .then((r) => r.json())
      .then((data) => {
        flow.variables = (data && data.variables) || [];
        return fetch('/create/languages').then((r) => r.json());
      })
      .then((langs) => {
        flow.availableLanguages = (langs && langs.locales) || [];
        if (langs && langs.repo) window._scifindRepo = langs.repo;
        flow.history = [];
        flow.translations = {};
        $('modal-step').innerHTML = '';
        $('modal-actions').innerHTML = '';
        pushPage({ kind: 'pick', selected: [] });
        openModal();
      })
      .catch((err) => showToast('Could not start: ' + err.message, 'error'));
  }

  function onPickLangsContinue() {
    const page = currentPage();
    if (!page || page.kind !== 'pick') return;
    const checked = [...document.querySelectorAll('#lang-picker input[type=checkbox]:checked:not([disabled])')]
      .map((el) => el.dataset.langCode)
      .filter((c) => c);
    page.selected = checked;
    if (!checked.length) {
      pushPage({ kind: 'sql' });
      return;
    }
    pushPage({ kind: 'translate', code: checked[0], queue: checked.slice(1) });
  }

  function onTranslateContinue() {
    const page = currentPage();
    if (!page || page.kind !== 'translate') return;
    captureTranslationForm(page.code);
    const next = page.queue[0];
    if (next) {
      pushPage({ kind: 'translate', code: next, queue: page.queue.slice(1) });
    } else {
      pushPage({ kind: 'sql' });
    }
  }

  function captureTranslationForm(code) {
    const step = $('modal-step');
    const nameEl = step.querySelector('[data-tr-field="name"]');
    const descEl = step.querySelector('[data-tr-field="description"]');
    const overrides = {};
    step.querySelectorAll('tr[data-key]').forEach((tr) => {
      const key = tr.dataset.key;
      const fields = {};
      tr.querySelectorAll('input[data-field]').forEach((inp) => {
        if (inp.value) fields[inp.dataset.field] = inp.value;
      });
      if (Object.keys(fields).length) overrides[key] = fields;
    });
    const entry = {};
    if (nameEl && nameEl.value.trim()) entry.name = nameEl.value.trim();
    if (descEl && descEl.value.trim()) entry.description = descEl.value.trim();
    if (Object.keys(overrides).length) entry.overrides = overrides;
    if (Object.keys(entry).length) flow.translations[code] = entry;
    else delete flow.translations[code];
  }

  document.addEventListener('click', (e) => {
    const toggleEl = e.target.closest('[data-action="toggle-sidebar-left"], [data-action="toggle-sidebar-right"]');
    if (!toggleEl) return;
    e.stopImmediatePropagation();
    const side = toggleEl.dataset.action === 'toggle-sidebar-left' ? 'left' : 'right';
    if (typeof window.toggleSidebar === 'function') window.toggleSidebar(side);
  }, true);

  document.addEventListener('click', (e) => {
    const tokenItem = e.target.closest('.qty-result[data-insert]');
    if (tokenItem) { insertAtCursor(tokenItem.dataset.insert); return; }

    const topicItem = e.target.closest('.topic-menu-item[data-id]');
    if (topicItem) {
      e.preventDefault(); e.stopPropagation();
      closeAllMenus();
      selectTopic(topicItem.dataset.id);
      return;
    }

    const crumbNode = e.target.closest('.topic-current[data-id]');
    if (crumbNode && !crumbNode.classList.contains('has-menu')) {
      const bar = $('topic-bar');
      const parents = [...bar.querySelectorAll('.topic-current[data-id]')];
      const idx = parents.indexOf(crumbNode);
      const parent = parents[idx - 1];
      selectTopic(parent ? parent.dataset.id : '');
      return;
    }

    const trigger = e.target.closest('.topic-dropdown-trigger');
    if (trigger) {
      e.preventDefault(); e.stopPropagation();
      const menu = trigger.nextElementSibling;
      if (!menu) return;
      const wasOpen = menu.classList.contains('open');
      closeAllMenus();
      if (!wasOpen) menu.classList.add('open');
      return;
    }

    const action = e.target.closest('[data-action]');
    const trCopy = e.target.closest('[data-tr-copy]');
    if (trCopy) {
      const field = trCopy.dataset.trCopy;
      const target = document.querySelector('[data-tr-field="' + field + '"]');
      if (target) copyText(target.value || target.placeholder || '', trCopy.dataset.trCopyLabel || field);
      return;
    }
    if (!action) return;
    switch (action.dataset.action) {
      case 'close-modal': closeModal(); break;
      case 'continue-to-sql': startCreateFlow(); break;
      case 'flow-pick-langs-continue': onPickLangsContinue(); break;
      case 'flow-translate-continue': onTranslateContinue(); break;
      case 'flow-back': {
        const page = currentPage();
        if (page && page.kind === 'translate') captureTranslationForm(page.code);
        popPage();
        break;
      }
      case 'open-issue': {
        if (flow.issueUrl) window.open(flow.issueUrl, '_blank', 'noopener,noreferrer');
        break;
      }
      case 'copy-formula-sql':
      case 'copy-token-sql': {
        const pre = $(action.dataset.action === 'copy-formula-sql' ? 'formula-sql' : 'token-sql');
        if (pre) copyText(pre.textContent, 'SQL');
        break;
      }
      case 'toggle-token-section': {
        const list = $(action.dataset.target);
        if (!list) break;
        const collapsed = list.dataset.collapsed === '1';
        list.dataset.collapsed = collapsed ? '0' : '1';
        const icon = action.querySelector('.token-section-icon');
        if (icon) {
          icon.innerHTML = '<i data-lucide="' + (collapsed ? 'chevron-up' : 'chevron-down') + '" width="16" height="16"></i>';
          refreshIcons();
        }
        break;
      }
    }
  });

  $('sidebar-left-inner').addEventListener('input', (e) => {
    if (e.target.id === 'token-search') filterTokenSidebar(e.target.value);
  });

  $('var-overrides').addEventListener('input', (e) => {
    if (e.target.name && e.target.name.startsWith('override[')) {
      updatePreview($('equation').value);
    }
  });

  let openSub = null, openItem = null, openTimer = 0, closeTimer = 0;
  let pendingSub = null, pendingItem = null;
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
  function closeSubmenuNow() {
    if (openSub) openSub.style.display = '';
    openSub = openItem = null;
  }
  function scheduleOpen(item, sub) {
    clearTimeout(openTimer); clearTimeout(closeTimer);
    pendingItem = item; pendingSub = sub;
    openTimer = setTimeout(() => { if (pendingSub === sub) openSubmenuNow(item, sub); }, 150);
  }
  function scheduleClose() {
    clearTimeout(closeTimer);
    closeTimer = setTimeout(closeSubmenuNow, 250);
  }
  $('topic-bar').addEventListener('mouseover', (e) => {
    const item = e.target.closest('.topic-menu-item');
    if (!item) return;
    const sub = item.querySelector(':scope > .topic-submenu');
    if (!sub) return;
    if (pendingItem === item) { clearTimeout(closeTimer); return; }
    scheduleOpen(item, sub);
  });
  $('topic-bar').addEventListener('mouseout', (e) => {
    const item = e.target.closest('.topic-menu-item');
    if (!item) return;
    if (!item.querySelector(':scope > .topic-submenu')) return;
    const to = e.relatedTarget;
    if (to && (item.contains(to) || (openSub && openSub.contains(to)))) return;
    clearTimeout(openTimer);
    scheduleClose();
  });
  document.addEventListener('mouseover', (e) => {
    const sub = e.target.closest('.topic-submenu');
    if (!sub || sub !== openSub) return;
    clearTimeout(closeTimer);
  });
  document.addEventListener('mouseout', (e) => {
    if (!openSub) return;
    if (!openSub.contains(e.target)) return;
    const to = e.relatedTarget;
    if (to && openSub.contains(to)) return;
    if (to && openItem && openItem.contains(to)) return;
    if (to && pendingItem && pendingItem.contains(to)) return;
    scheduleClose();
  });

  function closeAllMenus() {
    clearTimeout(openTimer); clearTimeout(closeTimer);
    openSub = openItem = pendingSub = pendingItem = null;
    const bar = $('topic-bar');
    bar.querySelectorAll('.topic-children-menu').forEach((m) => m.classList.remove('open'));
    bar.querySelectorAll('.topic-submenu').forEach((m) => m.style.display = '');
  }
  document.addEventListener('click', (e) => {
    if (!$('topic-bar').contains(e.target)) closeAllMenus();
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { closeAllMenus(); closeModal(); } });

  const slugify = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
  const nameInput = $('name_en'), idInput = $('formula_id');
  nameInput.addEventListener('input', () => { if (!idInput.dataset.manual) idInput.value = slugify(nameInput.value); });
  idInput.addEventListener('input', () => { idInput.dataset.manual = idInput.value !== slugify(nameInput.value); });

  const diffInput = $('difficulty'), diffFill = $('diff-fill-create'), diffDisplay = $('diff-display');
  function updateDiffFill() {
    const pct = ((diffInput.value - diffInput.min) / (diffInput.max - diffInput.min)) * 100;
    diffFill.style.width = pct + '%';
  }
  diffInput.addEventListener('input', () => { diffDisplay.textContent = diffInput.value + '/10'; updateDiffFill(); });
  updateDiffFill();

  function autoGrow(ta) {
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = ta.scrollHeight + 'px';
  }
  function bindAutoGrow(ta) {
    if (!ta) return;
    autoGrow(ta);
    ta.addEventListener('input', () => autoGrow(ta));
  }

  function init() {
    if (typeof window.hasActiveFilters === 'function') {
      const baseHasActiveFilters = window.hasActiveFilters;
      window.hasActiveFilters = function() {
        const dimMin = document.getElementById('diff-min');
        const dimMax = document.getElementById('diff-max');
        if (!dimMin || !dimMax) return false;
        return baseHasActiveFilters();
      };
    }

    loadTokenSidebar();
    loadBreadcrumb('');
    syncTreeResetBtn(false);
    renderOverrideTable([]);
    $('equation').addEventListener('input', (e) => updatePreview(e.target.value));
    bindAutoGrow($('equation'));
    bindAutoGrow($('description'));
    bindAutoGrow($('links'));
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
