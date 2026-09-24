'use strict';
(function() {
  var MAX_IDS = 500;
  var ID_RE = /^[A-Za-z0-9_.\-]{1,80}$/;
  var SEL_KEYS = ['selected_formulas', 'selected_quantities', 'select_mode', 'show_selected'];

  function uniq(arr) {
    var seen = Object.create(null);
    return arr.filter(function(x) { if (seen[x]) return false; seen[x] = 1; return true; }).slice(0, MAX_IDS);
  }
  function param(name) {
    try { return new URL(location.href).searchParams.get(name) || ''; }
    catch (e) { return ''; }
  }
  function readIds(name) {
    return uniq(param(name).split(',').map(function(s) { return s.trim(); }).filter(function(s) { return ID_RE.test(s); }));
  }
  function getF() { return readIds('selected_formulas'); }
  function getQ() { return readIds('selected_quantities'); }
  function isSelectMode() { return param('select_mode') === '1'; }
  function isShowOnly() { return param('show_selected') === '1'; }
  function setParam(name, value) {
    var url = new URL(location.href);
    if (!value) url.searchParams.delete(name);
    else url.searchParams.set(name, value);
    try { history.replaceState({ url: url.toString() }, '', url); } catch (e) {}
    try { if (typeof window.syncViewTabLinks === 'function') window.syncViewTabLinks(); } catch (e2) {}
  }
  function updateSelection(key, arr) {
    setParam(key, uniq(arr).join(','));
    if (!getF().length && !getQ().length) setParam('show_selected', null);
    syncUI();
    if (isDialogOpen()) { refreshLists(); schedulePdf(true); }
  }
  function idOf(s) {
    var m = String(s || '').match(/^\/(formula|quantity)\/([^/?#]+)/);
    return m ? { kind: m[1], id: decodeURIComponent(m[2]) } : null;
  }
  function detailId() { return idOf(location.pathname); }
  function t(path, fb) {
    try { if (window.SFUtils && window.SFUtils.t) return window.SFUtils.t(path, fb); } catch (e) {}
    return fb;
  }
  function esc(s) {
    try { if (window.SFUtils && window.SFUtils.escapeHtml) return window.SFUtils.escapeHtml(s); } catch (e) {}
    return String(s).replace(/[&<>"']/g, function(c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function refreshIcons() { if (typeof window.refreshIcons === 'function') window.refreshIcons(); }
  function nav(url) {
    if (typeof window._navigateTo === 'function') window._navigateTo(url);
    else location.href = url;
  }
  function closest(e, sel) { return e.target && e.target.closest ? e.target.closest(sel) : null; }
  function setAttr(el, k, v) { if (el && el.getAttribute(k) !== v) el.setAttribute(k, v); }
  function idList(ids) { return ids.map(encodeURIComponent).join(','); }
  function selQuery() {
    var f = getF(), q = getQ(), parts = [];
    if (f.length) parts.push('selected_formulas=' + idList(f));
    if (q.length) parts.push('selected_quantities=' + idList(q));
    return parts.join('&');
  }
  function itemName(id, el) {
    var scope = el && el.closest ? (el.closest('.formula-card') || el.closest('tr')) : null;
    var nm = scope && (scope.querySelector('.formula-name') || scope.querySelector('a'));
    if (nm && nm.textContent.trim()) return nm.textContent.trim();
    var h = document.querySelector('#main-content h2');
    return (h && h.textContent.trim()) || id;
  }
  function toggleId(kind, id, name) {
    var key = kind === 'formula' ? 'selected_formulas' : 'selected_quantities';
    var arr = key === 'selected_formulas' ? getF() : getQ();
    var i = arr.indexOf(id);
    if (i === -1) arr.push(id);
    else arr.splice(i, 1);
    updateSelection(key, arr);
    if (window.showToast) window.showToast((i === -1 ? t('select.added', 'Added') : t('select.removed', 'Removed')) + ': ' + name, 'info');
  }
  function setSlotIcon(wrapId, icon, size) {
    var wrap = document.getElementById(wrapId);
    if (!wrap) return;
    var cur = wrap.querySelector('[data-lucide]');
    if (cur && cur.getAttribute('data-lucide') === icon) return;
    wrap.innerHTML = '<i data-lucide="' + icon + '" width="' + (size || 18) + '" height="' + (size || 18) + '"></i>';
    refreshIcons();
  }
  function setIcon(icon) { setSlotIcon('select-toggle-icon', icon, 18); }
  function syncUI() {
    var f = getF(), q = getQ(), total = f.length + q.length;
    var mode = isSelectMode(), showOnly = isShowOnly();
    document.body.classList.toggle('selecting', mode);
    var btn = document.getElementById('select-toggle');
    var slot = document.getElementById('context-select-btn');
    var detail = detailId();
    var onDetail = !!(detail && ID_RE.test(detail.id));
    if (slot) {
      if (onDetail && !mode) {
        slot.classList.add('hidden');
      } else if (onDetail) {
        var has = (detail.kind === 'formula' ? f : q).indexOf(detail.id) !== -1;
        setSlotIcon('context-select-icon', has ? 'bookmark-check' : 'bookmark-plus', 18);
        slot.classList.remove('hidden');
        slot.classList.toggle('active', has);
        setAttr(slot, 'aria-pressed', has ? 'true' : 'false');
        var dtip = detail.kind === 'formula'
          ? t(has ? 'tooltip.remove_this_formula' : 'tooltip.add_this_formula', has ? 'Remove this formula from selected' : 'Add this formula to selected')
          : t(has ? 'tooltip.remove_this_quantity' : 'tooltip.add_this_quantity', has ? 'Remove this quantity from selected' : 'Add this quantity to selected');
        if (slot.title !== dtip) slot.title = dtip;
        setAttr(slot, 'aria-label', dtip);
      } else {
        setSlotIcon('context-select-icon', 'check-check', 18);
        syncSelectAllBtn(slot);
      }
    }
    if (btn) {
      var tip = t('tooltip.select_mode', "Tick a card's checkbox to select it for printing");
      setIcon('list-checks');
      setAttr(btn, 'aria-pressed', mode ? 'true' : 'false');
      if (btn.title !== tip) btn.title = tip;
      setAttr(btn, 'aria-label', tip);
      btn.classList.toggle('active', mode);
    }
    var showBtn = document.getElementById('show-selected-toggle');
    if (showBtn) {
      if (!mode) {
        showBtn.classList.add('hidden');
      } else {
        showBtn.classList.remove('hidden');
        showBtn.disabled = total === 0;
        setSlotIcon('show-selected-icon', showOnly ? 'eye-off' : 'eye', 18);
        showBtn.classList.toggle('active', showOnly);
        setAttr(showBtn, 'aria-pressed', showOnly ? 'true' : 'false');
        var stip = showOnly
          ? t('tooltip.show_all', 'Show all (exit selected-only view)')
          : t('tooltip.show_selected', 'Show selected only');
        if (showBtn.title !== stip) showBtn.title = stip;
        setAttr(showBtn, 'aria-label', stip);
      }
    }
    var pb = document.getElementById('print-btn');
    if (pb) {
      pb.classList.toggle('hidden', !mode);
      pb.disabled = mode && total === 0;
    }
    document.querySelectorAll('.select-check[data-sel-href]').forEach(function(el) {
      var info = idOf(el.getAttribute('data-sel-href'));
      if (!info || !ID_RE.test(info.id)) return;
      setAttr(el, 'aria-pressed', (info.kind === 'formula' ? f : q).indexOf(info.id) !== -1 ? 'true' : 'false');
    });
  }
  function listView() {
    var p = location.pathname;
    return (p === '/formulas' || p === '/quantities') ? p.slice(1) : null;
  }
  var selAll = { key: null, ids: null, loading: false, pendingKey: null, stale: false, after: null };
  function selectAllKey(view) {
    var url = new URL(location.href);
    SEL_KEYS.concat(['page', 'per_page', 'sort']).forEach(function(k) { url.searchParams.delete(k); });
    return view + '?' + url.searchParams.toString();
  }
  function ensureFilteredIds(view, after) {
    var key = selectAllKey(view);
    if (selAll.key === key && selAll.ids !== null) { if (after) after(selAll.ids); return; }
    if (selAll.loading) {
      if (key !== selAll.pendingKey) selAll.stale = true;
      if (after) selAll.after = { key: key, cb: after };
      return;
    }
    selAll.loading = true;
    selAll.pendingKey = key;
    var url = new URL(location.href);
    SEL_KEYS.concat(['page', 'per_page', 'sort']).forEach(function(k) { url.searchParams.delete(k); });
    url.searchParams.set('view', view);
    window.SFApi.getJSON('/api/filter-ids?' + url.searchParams.toString()).then(function(data) {
      selAll.loading = false;
      selAll.pendingKey = null;
      selAll.key = key;
      selAll.ids = ((data && data.ids) || []).filter(function(id) { return ID_RE.test(id); }).slice(0, MAX_IDS);
      var w = selAll.after;
      selAll.after = null;
      syncSelectAllBtn(document.getElementById('context-select-btn'));
      if (after) after(selAll.ids);
      if (w && w.cb !== after && w.key === key) w.cb(selAll.ids);
      if (selAll.stale) {
        selAll.stale = false;
        var lv = listView();
        if (lv && isSelectMode()) ensureFilteredIds(lv);
      }
    }).catch(function() { selAll.loading = false; selAll.pendingKey = null; selAll.after = null; });
  }
  function syncSelectAllBtn(btn) {
    if (!btn) return;
    var view = listView();
    if (!isSelectMode() || !view) { btn.classList.add('hidden'); return; }
    btn.classList.remove('hidden');
    setSlotIcon('context-select-icon', 'check-check', 18);
    var addAllTip = t('print.add_all', 'Add all');
    if (btn.title !== addAllTip) btn.title = addAllTip;
    setAttr(btn, 'aria-label', addAllTip);
    ensureFilteredIds(view);
    var ids = (selAll.key === selectAllKey(view) && selAll.ids !== null) ? selAll.ids : null;
    var cur = view === 'formulas' ? getF() : getQ();
    var all = !!ids && ids.length > 0 && ids.every(function(id) { return cur.indexOf(id) !== -1; });
    btn.classList.toggle('active', all);
    setAttr(btn, 'aria-pressed', all ? 'true' : 'false');
  }
  function onSelectAll() {
    var view = listView();
    if (!view || !isSelectMode() || !window.SFApi) return;
    ensureFilteredIds(view, function(ids) {
      if (!ids.length) return;
      var key = view === 'formulas' ? 'selected_formulas' : 'selected_quantities';
      var cur = key === 'selected_formulas' ? getF() : getQ();
      var all = ids.every(function(id) { return cur.indexOf(id) !== -1; });
      if (all) {
        updateSelection(key, []);
        if (window.showToast) window.showToast(t('select.removed', 'Removed') + ': ' + cur.length, 'info');
      } else {
        var add = ids.filter(function(id) { return cur.indexOf(id) === -1; });
        if (!add.length) return;
        updateSelection(key, cur.concat(add));
        if (window.showToast) window.showToast(t('select.added', 'Added') + ': ' + add.length, 'info');
      }
    });
  }
  function onToggle() {
    setParam('select_mode', isSelectMode() ? null : '1');
    syncUI();
  }
  function onShowToggle() {
    if (!isSelectMode()) return;
    if (isShowOnly()) {
      var url = new URL(location.href);
      url.searchParams.delete('show_selected');
      nav(url.pathname + (url.searchParams.toString() ? '?' + url.searchParams.toString() : ''));
      return;
    }
    var f = getF(), q = getQ();
    if (!f.length && !q.length) return;
    var here = location.pathname;
    if (here !== '/formulas' && here !== '/quantities') here = f.length ? '/formulas' : '/quantities';
    nav(here + '?select_mode=1&' + selQuery() + '&show_selected=1');
  }
  function onContextSelect() {
    var d = detailId();
    if (d && ID_RE.test(d.id)) { toggleId(d.kind, d.id, itemName(d.id, null)); return; }
    onSelectAll();
  }

  document.addEventListener('click', function(e) {
    var check = closest(e, '.select-check[data-sel-href]');
    if (check) {
      e.preventDefault();
      e.stopPropagation();
      var info = idOf(check.getAttribute('data-sel-href'));
      if (info && ID_RE.test(info.id)) toggleId(info.kind, info.id, itemName(info.id, check));
      return;
    }
    var seg = closest(e, '#print-layout-seg button[data-playout]');
    if (seg) { dlg.layout = seg.getAttribute('data-playout'); syncDlgControls(); schedulePdf(); return; }
    var pvt = closest(e, '#dlg-preview-toggle');
    if (pvt) {
      var layout = document.getElementById('print-layout');
      var on = layout ? !layout.classList.contains('show-preview') : false;
      if (layout) layout.classList.toggle('show-preview', on);
      setPreviewToggle(pvt, on);
      return;
    }
    if (closest(e, '#print-add-all')) {
      var boxes = document.querySelectorAll('#print-qlist input[data-print-check]');
      var off = document.querySelectorAll('#print-qlist input[data-print-check]:not(:checked)');
      if (boxes.length && !off.length) updateSelection('selected_quantities', []);
      else {
        var news = ((dlg.data && dlg.data.in_formula_new) || []).map(function(x) { return x.id; }).filter(function(id) { return ID_RE.test(id) && getQ().indexOf(id) === -1; });
        if (news.length) updateSelection('selected_quantities', getQ().concat(news));
      }
      return;
    }
    var pcoll = closest(e, '[data-print-collapse]');
    if (pcoll) {
      var plist = document.getElementById(pcoll.getAttribute('data-print-collapse'));
      if (plist) {
        var expanding = plist.getAttribute('data-collapsed') === '1';
        if (expanding) plist.removeAttribute('data-collapsed');
        else plist.setAttribute('data-collapsed', '1');
        pcoll.setAttribute('aria-expanded', expanding ? 'true' : 'false');
        var pic = pcoll.querySelector('.token-section-icon');
        if (pic) {
          pic.innerHTML = '<i data-lucide="' + (expanding ? 'chevron-up' : 'chevron-down') + '" width="16" height="16"></i>';
          refreshIcons();
        }
      }
      return;
    }
    var ov = dlgEl();
    if (ov && ov.classList.contains('open') && e.target === ov) closeDialog();
  }, true);

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && isDialogOpen()) { e.stopPropagation(); closeDialog(); return; }
    if (e.ctrlKey || e.metaKey || e.altKey || detailId() || !isSelectMode()) return;
    if (e.key !== ' ' && e.key !== 'x' && e.key !== 'X') return;
    var ae = document.activeElement;
    if (ae && ae.tagName && /^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(ae.tagName)) return;
    var main = document.getElementById('main-content');
    var cur = main && main.querySelector('.kb-current');
    if (!cur) return;
    var a = cur.tagName === 'A' ? cur : cur.querySelector('a[href*="/formula/"], a[href*="/quantity/"]');
    var ci = a ? idOf(a.getAttribute('href')) : null;
    if (!ci || !ID_RE.test(ci.id)) return;
    e.preventDefault();
    e.stopPropagation();
    toggleId(ci.kind, ci.id, itemName(ci.id, cur));
  }, true);

  var dlg = { layout: 'l2', cols: 4, rows: 16, borders: true, paper: null, area: 'paper', cw: 210, ch: 297, data: null, loading: false, pendingRefresh: false, knownF: {}, knownQ: {} };
  var pdfTimer = null, pdfObjectUrl = null, pdfSeq = 0;
  function clamp(v, fb, lo, hi) {
    v = parseInt(v, 10);
    return isNaN(v) ? fb : Math.min(hi, Math.max(lo, v));
  }
  function dlgEl() { return document.getElementById('print-dialog'); }
  function isDialogOpen() { var el = dlgEl(); return !!(el && el.classList.contains('open')); }
  function setSlider(id, fillId, valId, value) {
    var inp = document.getElementById(id);
    if (inp && value !== undefined) inp.value = value;
    if (!inp) return;
    var out = document.getElementById(valId);
    if (out) out.textContent = inp.value;
    var fill = document.getElementById(fillId);
    if (fill) fill.style.width = (((parseFloat(inp.value) - parseFloat(inp.min)) / (parseFloat(inp.max) - parseFloat(inp.min))) * 100) + '%';
  }
  function setVal(id, v) { var el = document.getElementById(id); if (el) el.value = v; }
  function syncDlgControls() {
    var seg = document.getElementById('print-layout-seg');
    if (seg) seg.querySelectorAll('button').forEach(function(b) {
      b.classList.toggle('active', b.getAttribute('data-playout') === dlg.layout);
    });
    setSlider('print-cols', 'print-cols-fill', 'print-cols-val', dlg.cols);
    setSlider('print-rows', 'print-rows-fill', 'print-rows-val', dlg.rows);
    var bd = document.getElementById('print-borders');
    if (bd) bd.checked = dlg.borders;
    setVal('print-paper', dlg.paper);
    setVal('print-area', dlg.area);
    setVal('print-cw', String(dlg.cw));
    setVal('print-ch', String(dlg.ch));
    var cwrap = document.getElementById('print-custom-wrap');
    if (cwrap) cwrap.hidden = dlg.area !== 'custom';
  }
  function openDialog() {
    if (!getF().length && !getQ().length) {
      if (window.showToast) window.showToast(t('print.empty', 'Nothing selected yet.'), 'error');
      return;
    }
    var el = dlgEl();
    if (!el) return;
    if (!dlg.paper) {
      var opts = document.getElementById('print-options');
      dlg.paper = opts && opts.getAttribute('data-unit-system') === 'Imperial' ? 'letter' : 'a4';
    }
    syncDlgControls();
    var layout = document.getElementById('print-layout');
    if (layout) layout.classList.remove('show-preview');
    var pt = document.getElementById('dlg-preview-toggle');
    if (pt) setPreviewToggle(pt, false);
    dlg.knownF = {};
    dlg.knownQ = {};
    ['print-flist', 'print-qlist'].forEach(function(id) {
      var l = document.getElementById(id);
      if (l) l.setAttribute('data-collapsed', '1');
    });
    document.querySelectorAll('[data-print-collapse]').forEach(function(b) {
      b.setAttribute('aria-expanded', 'false');
      var ic = b.querySelector('.token-section-icon');
      if (ic) ic.innerHTML = '<i data-lucide="chevron-down" width="16" height="16"></i>';
    });
    el.classList.add('open');
    pdfState(false, false);
    refreshIcons();
    refreshLists();
    schedulePdf(true);
  }
  function closeDialog() {
    pdfSeq++;
    var el = dlgEl();
    if (el) el.classList.remove('open');
  }
  function setPreviewToggle(btn, on) {
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    btn.classList.toggle('active', on);
    btn.innerHTML = '<i data-lucide="' + (on ? 'arrow-left' : 'eye') + '" width="14" height="14"></i> ' +
      esc(on ? t('create.back', 'Back') : t('print.preview', 'Preview'));
    refreshIcons();
  }
  function refreshLists() {
    if (!isDialogOpen() || !window.SFApi) return;
    if (dlg.loading) { dlg.pendingRefresh = true; return; }
    dlg.loading = true;
    var done = function() {
      dlg.loading = false;
      if (dlg.pendingRefresh) { dlg.pendingRefresh = false; refreshLists(); }
    };
    var fids = getF(), qids = getQ();
    var q = [(fids.length ? 'selected_formulas=' + idList(fids) : ''), (qids.length ? 'selected_quantities=' + idList(qids) : '')].filter(Boolean).join('&');
    try {
      window.SFApi.getJSON('/api/selection-preview?' + q).then(function(data) {
        dlg.data = data;
        renderLists();
        done();
      }).catch(done);
    } catch (e) { done(); }
  }
  function setList(listId, wrapId, html) {
    var list = document.getElementById(listId);
    if (list) list.innerHTML = html;
    var wrap = document.getElementById(wrapId);
    if (wrap) wrap.style.display = html ? '' : 'none';
  }
  function nameOf(cache, id) { return cache[id] || { id: id, name: id }; }
  function checkRow(kind, entry, checked) {
    var sym = (kind === 'q' && entry.symbol)
      ? '<span class="print-row-sym"><span class="latex-observe" data-latex="' + esc(entry.symbol) + '"></span></span>' : '';
    return '<li><label class="opt-check print-row' + (checked ? '' : ' is-off') + '">' +
      '<input type="checkbox" data-print-check="' + kind + ':' + esc(entry.id) + '"' + (checked ? ' checked' : '') + '>' +
      '<span class="box" aria-hidden="true"></span>' + sym +
      '<span class="print-row-name">' + esc(entry.name) + '</span></label></li>';
  }
  function renderLists() {
    if (!dlg.data) return;
    syncDlgControls();
    // Merge server data into the session caches so unchecked rows stay visible
    // until the dialog is reopened (they are no longer stored in the URL).
    var i, entry, id;
    var fD = dlg.data.formulas || [], qD = dlg.data.quantities || [], sD = dlg.data.in_formula_new || [];
    for (i = 0; i < fD.length; i++) { entry = fD[i]; dlg.knownF[entry.id] = { id: entry.id, name: entry.name }; }
    for (i = 0; i < qD.length; i++) { entry = qD[i]; dlg.knownQ[entry.id] = { id: entry.id, name: entry.name, symbol: entry.symbol }; }
    for (i = 0; i < sD.length; i++) { entry = sD[i]; if (!dlg.knownQ[entry.id]) dlg.knownQ[entry.id] = { id: entry.id, name: entry.name, symbol: entry.symbol }; }
    var fsel = getF(), qsel = getQ(), seen = Object.create(null), html = '';
    var focusKey = null;
    try {
      var ae = document.activeElement;
      if (ae && ae.matches && ae.matches('input[data-print-check]')) focusKey = ae.getAttribute('data-print-check');
    } catch (err) {}
    for (i = 0; i < fD.length; i++) { entry = fD[i]; if (fsel.indexOf(entry.id) !== -1) { seen[entry.id] = 1; html += checkRow('f', entry, true); } }
    for (i = 0; i < fsel.length; i++) { id = fsel[i]; if (!seen[id]) { seen[id] = 1; html += checkRow('f', nameOf(dlg.knownF, id), true); } }
    Object.keys(dlg.knownF).forEach(function(k) { if (!seen[k]) html += checkRow('f', dlg.knownF[k], false); });
    setList('print-flist', 'print-fwrap', html);
    seen = Object.create(null); html = '';
    for (i = 0; i < qD.length; i++) { entry = qD[i]; if (qsel.indexOf(entry.id) !== -1) { seen[entry.id] = 1; html += checkRow('q', entry, true); } }
    for (i = 0; i < qsel.length; i++) { id = qsel[i]; if (!seen[id]) { seen[id] = 1; html += checkRow('q', nameOf(dlg.knownQ, id), true); } }
    // Quantities used in the selected formulas live in the same list as
    // unchecked suggestions instead of their own section.
    for (i = 0; i < sD.length; i++) { entry = sD[i]; if (!seen[entry.id]) { seen[entry.id] = 1; html += checkRow('q', entry, false); } }
    Object.keys(dlg.knownQ).forEach(function(k) { if (!seen[k]) html += checkRow('q', dlg.knownQ[k], false); });
    setList('print-qlist', 'print-qwrap', html);
    if (focusKey) {
      var next = document.querySelector('input[data-print-check="' + focusKey + '"]');
      if (next && next.focus) { try { next.focus({ preventScroll: true }); } catch (err2) {} }
    }
    var addAll = document.getElementById('print-add-all');
    if (addAll) {
      var allBoxes = document.querySelectorAll('#print-qlist input[data-print-check]');
      var openBoxes = document.querySelectorAll('#print-qlist input[data-print-check]:not(:checked)');
      var allOn = allBoxes.length > 0 && openBoxes.length === 0;
      addAll.classList.toggle('active', allOn);
      setAttr(addAll, 'aria-pressed', allOn ? 'true' : 'false');
    }
    var opts = document.getElementById('print-options');
    if (opts && window.renderLatexIn) window.renderLatexIn(opts);
  }
  function schedulePdf(immediate) {
    if (!isDialogOpen()) return;
    if (pdfTimer) clearTimeout(pdfTimer);
    pdfTimer = setTimeout(refreshPdf, immediate ? 50 : 600);
  }
  function pdfState(load, ready) {
    var l = document.getElementById('pdf-loading');
    if (l) l.hidden = !load;
    var b = document.querySelector('[data-action="print-now"]');
    if (b) b.disabled = !ready;
  }
  function refreshPdf() {
    pdfTimer = null;
    var pv = document.getElementById('print-preview');
    if (!pv || !isDialogOpen()) return;
    if (!getF().length && !getQ().length) { closeDialog(); return; }
    var mySeq = ++pdfSeq;
    pdfState(true, false);
    var headers = { 'Content-Type': 'application/json', 'Accept': 'application/pdf' };
    try { if (window._csrfToken) headers['X-CSRF-Token'] = window._csrfToken; } catch (e) {}
    fetch('/api/print-pdf', { method: 'POST', headers: headers, body: JSON.stringify(
      { selected_formulas: getF(), selected_quantities: getQ(), layout: dlg.layout, cols: dlg.cols, rows: dlg.rows,
        borders: dlg.borders, paper: dlg.paper, area: dlg.area, cw: dlg.cw, ch: dlg.ch }) })
      .then(function(r) {
        if (!r.ok) throw new Error('pdf-' + r.status);
        return r.blob();
      }).then(function(blob) {
        if (mySeq !== pdfSeq || !isDialogOpen()) return;
        if (pdfObjectUrl) { try { URL.revokeObjectURL(pdfObjectUrl); } catch (e) {} }
        pdfObjectUrl = URL.createObjectURL(blob);
        pv.innerHTML = '';
        var fr = document.createElement('iframe');
        fr.id = 'print-pdf-frame';
        fr.title = t('print.title', 'Print preview');
        fr.src = pdfObjectUrl;
        pv.appendChild(fr);
        pdfState(false, true);
      }).catch(function() {
        if (mySeq !== pdfSeq) return;
        pdfState(false, false);
        if (pv) pv.innerHTML = '<p class="print-hint">' + esc(t('print.failed', 'PDF compilation failed.')) + '</p>';
        if (window.showToast) window.showToast(t('print.failed', 'PDF compilation failed.'), 'error');
      });
  }
  document.addEventListener('input', function(e) {
    if (e.target && (e.target.id === 'print-cols' || e.target.id === 'print-rows'))
      setSlider(e.target.id, e.target.id === 'print-cols' ? 'print-cols-fill' : 'print-rows-fill',
        e.target.id === 'print-cols' ? 'print-cols-val' : 'print-rows-val');
  });
  document.addEventListener('change', function(e) {
    if (!e.target) return;
    if (e.target.matches && e.target.matches('input[data-print-check]')) {
      var parts = (e.target.getAttribute('data-print-check') || '').split(':');
      var kind = parts[0], pid = parts.slice(1).join(':');
      if (!ID_RE.test(pid)) return;
      var key = kind === 'f' ? 'selected_formulas' : 'selected_quantities';
      var cur = key === 'selected_formulas' ? getF() : getQ();
      if (e.target.checked) {
        if (cur.indexOf(pid) === -1) updateSelection(key, cur.concat([pid]));
      } else {
        updateSelection(key, cur.filter(function(x) { return x !== pid; }));
      }
      // updateSelection re-renders async; flip the row state right away so the
      // item visibly stays (unchecked) instead of vanishing on toggle.
      var row = e.target.closest ? e.target.closest('label.print-row') : null;
      if (row) row.classList.toggle('is-off', !e.target.checked);
      return;
    }
    if (e.target.id === 'print-cols') { dlg.cols = clamp(e.target.value, 4, 1, 32); schedulePdf(); }
    else if (e.target.id === 'print-rows') { dlg.rows = clamp(e.target.value, 16, 1, 32); schedulePdf(); }
    else if (e.target.id === 'print-borders') { dlg.borders = !!e.target.checked; schedulePdf(); }
    else if (e.target.id === 'print-paper') { dlg.paper = e.target.value; schedulePdf(); }
    else if (e.target.id === 'print-area') {
      dlg.area = e.target.value;
      var cwrap = document.getElementById('print-custom-wrap');
      if (cwrap) cwrap.hidden = dlg.area !== 'custom';
      schedulePdf();
    }
    else if (e.target.id === 'print-cw' || e.target.id === 'print-ch') {
      var v = Math.min(1200, Math.max(10, parseFloat(e.target.value) || 0));
      if (e.target.id === 'print-cw') dlg.cw = v; else dlg.ch = v;
      e.target.value = v;
      schedulePdf();
    }
  });

  window.SFUtils.registerActions({
    'toggle-select-mode': function(e) { e.stopPropagation(); onToggle(); },
    'toggle-show-selected': function(e) { e.stopPropagation(); onShowToggle(); },
    'context-select': function(e) { e.stopPropagation(); onContextSelect(); },
    'goto-print': function(e) { e.stopPropagation(); openDialog(); },
    'close-print': function(e) { e.stopPropagation(); closeDialog(); },
    'print-now': function(e) {
      e.stopPropagation();
      var fr = document.getElementById('print-pdf-frame');
      if (fr && fr.contentWindow) {
        try { fr.contentWindow.focus(); fr.contentWindow.print(); return; } catch (err) {}
      }
      if (window.showToast) window.showToast(t('print.compiling', 'Compiling preview…'), 'info');
    }
  });

  new MutationObserver(syncUI).observe(document.getElementById('main-content') || document.documentElement, { childList: true, subtree: true });
  window.addEventListener('popstate', function() { syncUI(); if (isDialogOpen()) { refreshLists(); schedulePdf(true); } });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', syncUI);
  else syncUI();
})();
