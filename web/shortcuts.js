/* eslint-disable no-undef */
'use strict';

(function() {
  function $(id) { return window.SFUtils.byId(id); }
  function qsa(sel, root) { return window.SFUtils.bySel(sel, root); }
  function vis(sel, root) { return qsa(sel, root).filter(function(el) { return el.offsetParent !== null; }); }
  function reveal(el) { if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest' }); return el; }
  function t(path, fallback) { return window.SFUtils.t(path, fallback); }
  function escapeHtml(s) { return window.SFUtils.escapeHtml(s); }

  var SEQ_MS = 5000;
  var pending = null, pendingAt = 0, pendingTimer = null, lastFocus = null;
  var sortMode = { openedMenu: false };
  var treeMode = { active: false, hl: null };

  /* Pure modifier presses must never dismiss (or trigger) a pending prefix:
     holding Shift for f R / f D / f Q would otherwise cancel the sequence. */
  var MODIFIER_KEYS = { Shift: 1, Control: 1, Alt: 1, Meta: 1, AltGraph: 1, CapsLock: 1 };
  function isModifierKey(e) { return !!(e && MODIFIER_KEYS[e.key]); }

  function isEditable(el) {
    if (!el || !el.tagName) return false;
    var tag = el.tagName.toLowerCase();
    if (tag === 'textarea' || tag === 'select') return true;
    if (tag === 'input') {
      var type = (el.type || 'text').toLowerCase();
      return ['hidden', 'checkbox', 'radio', 'button', 'submit', 'reset', 'file', 'image'].indexOf(type) === -1;
    }
    return !!el.isContentEditable;
  }

  var LIST_VIEWS = ['/formulas', '/quantities', '/search'];
  function isListView() { return LIST_VIEWS.indexOf(window.location.pathname) !== -1; }
  var DETAIL_RE = /^\/(formula|quantity|constant|unit)\//;
  function isDetailView() { return DETAIL_RE.test(window.location.pathname); }

  function clickFirst(sel, onlyIfEnabled) {
    var el = sel.charAt(0) === '#' ? $(sel.slice(1)) : document.querySelector(sel);
    if (!el || (onlyIfEnabled && el.classList.contains('disabled'))) return false;
    el.click();
    return true;
  }
  function clickAction(action) { return clickFirst('[data-action="' + action + '"]'); }
  function clickId(id, onlyIfEnabled) { return clickFirst('#' + id, onlyIfEnabled); }
  function focusEl(el) {
    if (!el) return false;
    var tag = (el.tagName || '').toUpperCase();
    if (!el.hasAttribute('tabindex') && ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A'].indexOf(tag) === -1) el.setAttribute('tabindex', '-1');
    try { el.focus({ preventScroll: true }); } catch (e) { el.focus(); }
    reveal(el);
    if (typeof el.select === 'function' && (tag === 'INPUT' || tag === 'TEXTAREA')) { try { el.select(); } catch (err) {} }
    return true;
  }
  function focusLink(el) {
    if (!el) return false;
    focusEl(el);
    setNavHighlight(el);
    return true;
  }
  function focusBody() {
    var ae = document.activeElement;
    if (ae && ae !== document.body && typeof ae.blur === 'function') ae.blur();
  }

  function navTo(url) {
    hidePending();
    if (typeof window._navigateTo === 'function') window._navigateTo(url);
    else window.location.href = url;
  }
  function gotoView(view) { navTo(window.SFUtils.viewUrl(view, true)); }
  function gotoCreate() { navTo('/create'); }
  function gotoHome() {
    var logo = document.querySelector('.topbar-logo');
    if (logo) { hidePending(); logo.click(); return; }
    navTo('/formulas');
  }

  function sidebarClosed(side) { return !window.SFUtils.sidebarOpenAttr(side); }
  function ensureSidebar(side, fn) {
    if (!sidebarClosed(side)) { fn(); return; }
    clickAction(side === 'left' ? 'toggle-sidebar-left' : 'toggle-sidebar-right');
    requestAnimationFrame(function() { requestAnimationFrame(fn); });
  }
  function focusSearch() {
    var topbar = document.querySelector('.topbar');
    if (topbar && window.innerWidth < 768 && !topbar.classList.contains('expand-search')) clickAction('dock-toggle-search');
    focusEl(document.querySelector('.topbar-search input[name="q"]'));
  }

  /* ---- Result list + detail navigation (.kb-current container model) ---- */
  var LIST_LINK_SEL = '#main-content .formula-grid .formula-card a, #main-content tbody[data-list-container] a';

  function listLinks() { return vis(LIST_LINK_SEL); }
  function moveListFocus(dir) {
    var links = listLinks();
    if (!links.length) return false;
    var idx = links.indexOf(document.activeElement);
    return focusLink(links[idx === -1 ? (dir > 0 ? 0 : links.length - 1) : (idx + dir + links.length) % links.length]);
  }

  function navContainers() {
    var p = window.location.pathname;
    if (p === '/quantities') return vis('#main-content tbody[data-list-container] tr');
    if (p === '/formulas') return vis('#main-content .formula-grid .formula-card');
    return null; /* /search keeps legacy linear link navigation */
  }
  function gridCols(cards) {
    if (!cards.length) return 1;
    var top = cards[0].offsetTop, n = 0;
    while (n < cards.length && Math.abs(cards[n].offsetTop - top) < 2) n++;
    return Math.max(1, n);
  }
  function navHighlightEl() { return document.querySelector('.kb-current'); }
  function navContainer(link) {
    if (!link || !link.closest) return null;
    return link.closest('.formula-card') || link.closest('tr') || link.closest('.link-list li') || link;
  }
  function setNavHighlight(link) {
    clearNavHighlight();
    var c = navContainer(link);
    if (c) c.classList.add('kb-current');
  }
  function clearNavHighlight(root) { qsa('.kb-current', root).forEach(function(el) { el.classList.remove('kb-current'); }); }
  function linkModeActive() {
    var cur = navHighlightEl(), ae = document.activeElement;
    return !!(cur && ae && ae !== document.body && ae.closest && ae.closest('a') && cur.contains(ae));
  }
  function demoteNavLink() {
    if (!linkModeActive()) return false;
    document.activeElement.blur();
    return true;
  }
  function gotoContainer(el) {
    if (!el) return false;
    focusBody();
    setNavHighlight(el);
    reveal(el);
    return true;
  }
  function leaveNav(toBottom) {
    clearNavHighlight();
    focusBody();
    var scroller = $('main-content'), y = toBottom && scroller ? scroller.scrollHeight : 0;
    if (scroller) {
      if (typeof scroller.scrollTo === 'function') { try { scroller.scrollTo(0, y); } catch (e) { scroller.scrollTop = y; } }
      else scroller.scrollTop = y;
    }
    try { window.scrollTo(0, y); } catch (e) {}
    return true;
  }
  function clampStep(len, idx, dir) { return dir > 0 ? Math.min(len - 1, idx + 1) : Math.max(0, idx - 1); }
  function stepTo(list, idx, next, dir, axis) {
    if (axis !== 'horizontal' && idx !== -1 && next === idx) return leaveNav(dir > 0);
    return gotoContainer(list[next]);
  }
  /* Shared grid step: vertical jumps a full row, horizontal stays in-row. */
  function gridStep(list, idx, dir, axis, cols) {
    if (axis === 'vertical') return dir > 0 ? Math.min(list.length - 1, idx + cols) : Math.max(0, idx - cols);
    var col = idx % cols;
    if (dir < 0) return col > 0 ? idx - 1 : idx;
    return (col < cols - 1 && idx + 1 < list.length) ? idx + 1 : idx;
  }
  function moveContainer(dir, axis) {
    var list = navContainers();
    if (!list || !list.length) return window.location.pathname === '/search' ? moveListFocus(dir) : false;
    var idx = list.indexOf(navHighlightEl()), next;
    if (idx === -1) next = dir > 0 ? 0 : list.length - 1;
    else if (window.location.pathname === '/formulas' && axis !== 'horizontal') next = gridStep(list, idx, dir, axis, gridCols(list));
    else if (axis === 'horizontal') next = gridStep(list, idx, dir, axis, gridCols(list));
    else next = clampStep(list.length, idx, dir);
    return stepTo(list, idx, next, dir, axis);
  }

  document.addEventListener('focusin', function(e) {
    var tg = e.target;
    if (!tg || tg === document.body || tg === document || !tg.closest) return;
    var link = tg.closest('.formula-card a') || tg.closest('tbody[data-list-container] a') ||
      tg.closest('#main-content .detail-section table tbody tr a') || tg.closest('#main-content .detail-section .link-list a');
    if (link) setNavHighlight(link);
    else clearNavHighlight();
  });

  /* ---- Detail-page navigation: one flat stream in DOM order ---- */
  var DETAIL_SELS = ['#main-content .detail-section table tbody tr', '#main-content .detail-section .formula-grid .formula-card', '#main-content .detail-section .link-list li'];
  function detailContainers() {
    var found = [];
    DETAIL_SELS.forEach(function(sel) { vis(sel).forEach(function(el) { found.push(el); }); });
    found.sort(function(a, b) {
      if (a === b) return 0;
      var pos = a.compareDocumentPosition(b);
      if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
      if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
      return 0;
    });
    return found;
  }
  function detailFocusable(container, sel) {
    if (!container || !container.querySelector) return null;
    return container.tagName === 'A' ? container : container.querySelector(sel);
  }
  function detailAllLinks() {
    var out = [];
    detailContainers().forEach(function(c) { vis('a', c).forEach(function(a) { out.push(a); }); });
    return out;
  }
  /* Advance focus through an ordered link list; fall back to body at the ends. */
  function stepLinks(links, dir, fromEl) {
    var li = links.indexOf(fromEl || document.activeElement);
    if (li !== -1 && li + dir >= 0 && li + dir < links.length) focusLink(links[li + dir]);
    else focusBody();
    return true;
  }
  function moveDetail(dir, axis) {
    var list = detailContainers();
    if (!list.length) return false;
    var idx = list.indexOf(navHighlightEl());
    if (idx === -1) return gotoContainer(list[dir > 0 ? 0 : list.length - 1]);
    var cur = list[idx], grid = cur.closest ? cur.closest('.formula-grid') : null;
    if (grid && cur.classList.contains('formula-card')) {
      var cards = vis('.formula-card', grid), pos = cards.indexOf(cur), cols = gridCols(cards);
      if (axis === 'vertical') {
        var v = pos + dir * cols;
        if (v >= 0 && v < cards.length) return gotoContainer(cards[v]);
      } else if (pos + dir >= 0 && pos + dir < cards.length && Math.abs(cards[pos + dir].offsetTop - cur.offsetTop) < 2) {
        return gotoContainer(cards[pos + dir]);
      }
      var edge = dir > 0 ? list.indexOf(cards[cards.length - 1]) + 1 : list.indexOf(cards[0]) - 1;
      if (edge >= 0 && edge < list.length) return gotoContainer(list[edge]);
      return axis === 'horizontal' ? true : leaveNav(dir > 0);
    }
    return stepTo(list, idx, clampStep(list.length, idx, dir), dir, axis);
  }
  function detailDrillOrNext() {
    var cur = navHighlightEl();
    if (!cur) return false;
    if (linkModeActive()) return stepLinks(detailAllLinks(), 1);
    var first = detailFocusable(cur, 'a, button:not([disabled])');
    return first ? focusLink(first) : moveDetail(1, 'horizontal');
  }
  function focusSiBaseUnit(toggleRow) {
    var table = toggleRow.closest ? toggleRow.closest('table') : null;
    if (!table || !table.classList.contains('si-expanded')) return;
    var base = table.querySelector('tbody tr[data-exp="0"]') || table.querySelector('tbody tr:not(.si-toggle-row)');
    if (base && base.offsetParent !== null) gotoContainer(base);
  }
  function loadMore() {
    var btn = document.querySelector('[data-load-more-btn]');
    if (btn && btn.offsetParent !== null && !btn.dataset.loading) { btn.click(); return true; }
    return false;
  }

  /* ---- Filter (f-prefix): focus targets + AND/OR toggles (f D / f Q) ---- */
  function toggleDimMode() { if (isListView()) clickId('dim-mode-toggle'); }
  function toggleQtyMode() { if (isListView()) clickId('qty-mode-toggle'); }
  /* Mirrors the sidebar AND/OR button titles (mode_switched holds 'dim'/'fml' when OR is on). */
  function isOrMode(key) {
    try {
      var parts = typeof getSwitched === 'function'
        ? getSwitched(new URL(window.location))
        : (new URL(window.location).searchParams.get('mode_switched') || '').split(',').filter(Boolean);
      return parts.indexOf(key) !== -1;
    } catch (e) { return false; }
  }
  function modeToggleLabel(isDim) {
    var or = isOrMode(isDim ? 'dim' : 'fml');
    return t(isDim ? (or ? 'filter.dim_mode_or' : 'filter.dim_mode_and') : (or ? 'filter.qty_mode_or' : 'filter.qty_mode_and'),
      isDim ? 'Dimension AND/OR' : 'Quantity AND/OR');
  }
  function handleFilterKey(k) {
    if (!isListView()) return true;
    var lk = (k || '').toLowerCase();
    if (k === 'q') ensureSidebar('left', function() {
      var inp = $('qty-search');
      if (!inp) return;
      focusEl(inp);
      if (typeof window.renderQtyResults === 'function') window.renderQtyResults(inp.value);
    });
    else if (k === 'Q') toggleQtyMode();
    else if (k === 'd') ensureSidebar('left', function() { enterDimMode(); });
    else if (k === 'D') toggleDimMode();
    else if (lk === 's') ensureSidebar('left', function() { enterSortMode(); });
    else if (k === 'r') enterDiffMode(false);
    else if (k === 'R') enterDiffMode(true);
    else if (lk === 't') enterTreeMode();
    return true;
  }

  /* ---- Difficulty range (f r / f R …): digit sets bound, 0 means 10 ---- */
  function diffDigitToVal(k) {
    if (!/^[0-9]$/.test(k || '')) return null;
    var n = parseInt(k, 10);
    return n === 0 ? 10 : n;
  }
  function enterDiffMode(isMax) {
    if (!isListView()) return;
    clearPending();
    setPending(isMax ? 'fR' : 'fr');
  }
  function setDiffBound(isMax, k) {
    if (!isListView()) return true;
    var v = diffDigitToVal(k);
    if (v === null) { setPending(isMax ? 'fR' : 'fr'); return true; } /* unknown key: stay in picker mode */
    var minEl = $('diff-min'), maxEl = $('diff-max');
    if (!minEl || !maxEl) return true;
    (isMax ? maxEl : minEl).value = v;
    if (typeof syncDiff === 'function') syncDiff();
    else {
      var raw1 = parseFloat(minEl.value), raw2 = parseFloat(maxEl.value);
      if (raw1 > raw2) { minEl.value = raw2; maxEl.value = raw1; }
    }
    (isMax ? maxEl : minEl).dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }

  function clearHints() {
    qsa('.kb-hint').forEach(function(el) { el.remove(); });
    if (sortMode.openedMenu) {
      sortMode.openedMenu = false;
      var menu = $('sort-menu');
      if (menu) {
        if (menu._morphCtrl && menu._morphCtrl.isOpen()) menu._morphCtrl.close();
        else menu.classList.remove('open');
      }
    }
  }
  function badgeRow(row, text) {
    if (!row || row.querySelector('.kb-hint')) return;
    var badge = document.createElement('kbd');
    badge.className = 'kb-hint';
    badge.textContent = text;
    row.appendChild(badge);
  }

  /* ---- Dimension picker (f d …) ---- */
  var DIM_LETTERS = { m: 'M', l: 'L', t: 'T', i: 'I', n: 'N', j: 'J' };
  var DIM_OPS = { l: 'leq', g: 'geq', e: 'eq' };
  var pendingDimOp = null;
  function dimRows() { return qsa('.filter-dim-row'); }
  function dimRowLetters() {
    var taken = {};
    var out = dimRows().map(function(row) { return { row: row, letter: null }; });
    out.forEach(function(entry) {
      var sym = (entry.row.getAttribute('data-dim') || '').toUpperCase();
      Object.keys(DIM_LETTERS).some(function(L) {
        if (DIM_LETTERS[L] === sym && !taken[L]) { entry.letter = L; taken[L] = true; return true; }
        return false;
      });
      if (!entry.letter && !taken.h) { entry.letter = 'h'; taken.h = true; }
    });
    return out;
  }
  /* One chip per row grouping both keys: "m/1", "l/2", … */
  function dimGroupedOptions() {
    return dimRowLetters().map(function(entry, i) {
      var nameEl = entry.row.querySelector('.dim-name');
      return [entry.letter ? entry.letter + '/' + (i + 1) : String(i + 1),
        ((nameEl ? nameEl.textContent.trim() : '') || entry.row.getAttribute('data-dim') || '')];
    });
  }
  function dimRowFor(k) {
    if (/^[1-9]$/.test(k)) return dimRows()[parseInt(k, 10) - 1] || null;
    var found = null;
    dimRowLetters().forEach(function(entry) { if (entry.letter === k) found = found || entry.row; });
    return found;
  }
  function enterDimMode() { pendingDimOp = null; clearPending(); setPending('fd'); }
  function handleDimKey(k, shifted, state) {
    if (state === 'fde') {
      setPending(DIM_OPS[k] ? (pendingDimOp = DIM_OPS[k], 'fdo') : 'fde');
      return true;
    }
    if (k === 'f' || k === 'b') {
      pendingDimOp = null;
      clearPending();
      if (isListView()) clickId(k === 'f' ? 'dim-fill-zeros' : 'dim-base-qty', true);
      return true;
    }
    if (state === 'fd' && k === 'e' && !shifted) { setPending('fde'); return true; }
    var row = dimRowFor(k);
    if (!row) { setPending(state); return true; } /* unknown key: stay in picker mode */
    var op = state === 'fdo' ? pendingDimOp : null;
    pendingDimOp = null;
    ensureSidebar('left', function() {
      if (op) setDimOperator(row, op);
      focusEl(row.querySelector('.dim-val') || row);
    });
    clearPending();
    return true;
  }
  function setDimOperator(row, op) {
    var sel = row.querySelector('.dim-op');
    if (!sel) return false;
    sel.value = op;
    var label = row.querySelector('.cselect .cselect-label');
    if (label && sel.options && sel.selectedIndex >= 0 && sel.options[sel.selectedIndex]) label.textContent = sel.options[sel.selectedIndex].textContent.trim();
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }

  /* ---- Sort picker (f s …): r/q/i/n/d/D/t/T (case-sensitive) ---- */
  var SORT_LETTERS = { r: 'relevance', q: 'qty', i: 'id', n: 'name', d: 'diff_asc', D: 'diff_desc', t: 'topic_tree', T: 'topic_alpha' };
  function sortLetterOptions() {
    var allowed = window._availableSorts || [], labels = (window._localeUI && window._localeUI.sort) || {};
    return Object.keys(SORT_LETTERS).filter(function(L) { return allowed.indexOf(SORT_LETTERS[L]) !== -1; })
      .map(function(L) { return [L, labels[SORT_LETTERS[L]] || SORT_LETTERS[L]]; });
  }
  function enterSortMode() {
    clearPending();
    sortMode.openedMenu = false;
    var menu = $('sort-menu');
    if (menu && !menu.classList.contains('open') && clickId('sort-trigger')) sortMode.openedMenu = true;
    setPending('fs');
  }
  function handleSortKey(L) {
    var key = SORT_LETTERS[L];
    if (!key || (window._availableSorts || []).indexOf(key) === -1) enterSortMode();
    else {
      var btn = document.querySelector('#sort-menu [data-sort="' + key + '"]');
      if (btn) btn.click(); /* absent == already selected */
      clearPending();
    }
    return true;
  }

  /* ---- Topic-tree navigator (f t): 1-9 drills, Enter toggles, d deselects, Esc exits ---- */
  function treeApi() {
    var T = window._topicTree;
    if (!T || window._topicTreeMode !== 'checkbox' || !document.getElementById('science-tree')) return null;
    return T;
  }
  function treeVisibleRows() { return vis('#science-tree .tree-row'); }
  function treeRowById(id) {
    var rows = treeVisibleRows();
    for (var i = 0; i < rows.length; i++) if (rows[i].getAttribute('data-id') === id) return rows[i];
    return null;
  }
  function treeRowDepth(row) { return parseInt(row.getAttribute('data-depth') || '0', 10) || 0; }
  function treeChildrenOf(row, rows) {
    rows = rows || treeVisibleRows();
    var out = [], depth = treeRowDepth(row), started = false;
    for (var i = 0; i < rows.length; i++) {
      if (rows[i] === row) { started = true; continue; }
      if (!started) continue;
      if (treeRowDepth(rows[i]) <= depth) break;
      if (treeRowDepth(rows[i]) === depth + 1) out.push(rows[i]);
    }
    return out;
  }
  function treeSiblingsOf(row, rows) {
    rows = rows || treeVisibleRows();
    var depth = treeRowDepth(row), idx = rows.indexOf(row), out = [row], i = idx;
    while (i - 1 >= 0 && treeRowDepth(rows[i - 1]) >= depth) { i--; if (treeRowDepth(rows[i]) === depth) out.unshift(rows[i]); }
    i = idx;
    while (i + 1 < rows.length && treeRowDepth(rows[i + 1]) >= depth) { i++; if (treeRowDepth(rows[i]) === depth) out.push(rows[i]); }
    return out;
  }
  function treeCandidates() {
    var rows = treeVisibleRows();
    if (!treeMode.hl) return rows.filter(function(r) { return treeRowDepth(r) === 0; });
    var hlRow = treeRowById(treeMode.hl);
    if (!hlRow) return [];
    var kids = treeChildrenOf(hlRow, rows);
    return kids.length ? kids : treeSiblingsOf(hlRow, rows);
  }
  function isBranchNode(node) {
    if (!node) return false;
    return typeof node.hasChildren === 'function' ? node.hasChildren() : (node.children || []).length > 0;
  }
  function setTreeAll(open) {
    var T = treeApi();
    if (!T) return;
    var root = T.getRootNode(), stack = (root && root.children ? root.children.slice() : []);
    while (stack.length) {
      var node = stack.pop();
      if (!isBranchNode(node)) continue;
      if (node.state && ((open && !node.state.open) || (!open && node.state.open))) {
        if (open) T.openNode(node); else T.closeNode(node);
      }
      var kids = node.children || [];
      for (var i = kids.length - 1; i >= 0; i--) stack.push(kids[i]);
    }
  }
  function refreshTreeHints() {
    clearHints();
    clearNavHighlight($('science-tree'));
    var hlRow = treeMode.hl ? treeRowById(treeMode.hl) : null;
    if (hlRow) hlRow.classList.add('kb-current');
    treeCandidates().slice(0, 9).forEach(function(row, i) { badgeRow(row, String(i + 1)); });
  }
  function enterTreeMode() {
    if (!treeApi()) { ensureSidebar('right', function() { focusEl($('science-tree')); }); return; }
    clearPending();
    ensureSidebar('right', function() {
      treeMode.active = true;
      treeMode.hl = null;
      setTreeAll(false);
      refreshTreeHints();
      showPending('ft');
    });
  }
  function exitTreeMode(reexpand) {
    if (!treeMode.active) return;
    treeMode.active = false;
    treeMode.hl = null;
    clearHints();
    clearNavHighlight($('science-tree'));
    hidePending();
    if (reexpand) setTreeAll(true);
  }
  function treeDigit(n) {
    var row = treeCandidates()[n - 1];
    if (!row) return;
    var T = treeApi(), id = row.getAttribute('data-id'), node = T && T.getNodeById(id);
    if (node && isBranchNode(node) && node.state && !node.state.open) T.openNode(node);
    treeMode.hl = id;
    refreshTreeHints();
    showPending('ft');
    reveal(treeRowById(treeMode.hl));
  }
  function treeCommit() {
    var T = treeApi();
    if (treeMode.hl && T) {
      var node = T.getNodeById(treeMode.hl);
      if (node) T.checkNode(node); /* toggles; fires checkNode -> applyFilters */
    }
    exitTreeMode(true);
  }
  function handleTreeKey(e) {
    if (e.key === 'Enter') treeCommit();
    else if (e.key.length === 1 && e.key >= '1' && e.key <= '9') treeDigit(parseInt(e.key, 10));
    else if (e.key.length === 1 && e.key.toLowerCase() === 'd') {
      exitTreeMode(true);
      if (isListView()) clickId('tree-deselect-all', true);
    }
  }

  /* ---- Copy & clear (c-prefix): one table drives buttons, pending menu, dialog ---- */
  var COPY_FORMATS = { l: ['latex', 'LaTeX'], u: ['unicode', 'Unicode'], p: ['png', 'PNG'], v: ['svg', 'SVG'] };
  var CLEAR_DEFS = {
    a: { ids: ['dim-reset', 'qty-reset', 'diff-reset', 'tree-select-all'], key: 'heading.all', fb: 'All' },
    q: { ids: ['qty-reset'], key: 'detail.quantity', fb: 'Quantity' },
    d: { ids: ['dim-reset'], key: 'filter.dimension', fb: 'Dimension' },
    r: { ids: ['diff-reset'], key: 'detail.difficulty', fb: 'Difficulty' },
    t: { ids: ['tree-select-all'], key: 'nav.tree', fb: 'Tree' },
  };
  function clearFilters(which) {
    if (!isListView() || !CLEAR_DEFS[which]) return;
    CLEAR_DEFS[which].ids.forEach(function(id) { clickId(id); });
  }
  function handleCopyKey(k) {
    if (COPY_FORMATS[k]) {
      if ($('formula-tex') && typeof copyFormula === 'function') copyFormula(COPY_FORMATS[k][0]);
    } else if (k === 's') {
      if ($('formula-sql-modal')) {
        var m = $('formula-copy-menu');
        if (m) m.classList.remove('open');
        window.SFUtils.setModal('formula-sql-modal', true);
      }
    } else if (CLEAR_DEFS[k]) clearFilters(k);
    return true;
  }

  /* ---- Pending-prefix indicator ---- */
  var PENDING_STATIC = {
    g: [['f', 'nav.formulas', 'Formulas'], ['q', 'detail.quantities', 'Quantities'], ['c', 'settings.create', 'Create'], ['h', 'shortcut.go_home', 'Home']],
  };
  function filterPendingOptions() {
    return [['q', t('detail.quantity', 'Quantity')], ['Q', modeToggleLabel(false)],
      ['d', t('filter.dimension', 'Dimension')], ['D', modeToggleLabel(true)],
      ['s', t('sort.section', 'Sort')], ['r', t('detail.difficulty_min', 'Minimum difficulty')],
      ['R', t('detail.difficulty_max', 'Maximum difficulty')], ['t', t('nav.tree', 'Tree')]];
  }
  function filterOpSymbol(op) {
    var map = window._filterOpSymbols || {};
    return map[op] || op;
  }
  function dimOpPendingOptions() {
    return [['l', filterOpSymbol('leq')], ['g', filterOpSymbol('geq')], ['e', filterOpSymbol('eq')]];
  }
  function dimOpHint() {
    return [filterOpSymbol('eq'), filterOpSymbol('leq'), filterOpSymbol('geq')].join('/');
  }
  function copyPendingOptions() {
    var opts = [];
    if ($('formula-tex') && typeof copyFormula === 'function') Object.keys(COPY_FORMATS).forEach(function(k) { opts.push([k, COPY_FORMATS[k][1]]); });
    if ($('formula-sql-modal')) opts.push(['s', 'SQL']);
    if (isListView()) Object.keys(CLEAR_DEFS).forEach(function(k) { opts.push([k, t(CLEAR_DEFS[k].key, CLEAR_DEFS[k].fb)]); });
    return opts;
  }
  function diffPendingOptions(isMax) {
    var label = t(isMax ? 'detail.difficulty_max' : 'detail.difficulty_min',
      isMax ? 'Maximum difficulty' : 'Minimum difficulty');
    return [['0-9', label + ' (0 = 10)']];
  }
  function treePendingOptions() {
    var n = treeCandidates().slice(0, 9).length;
    return [[n > 1 ? '1–' + n : '1', t('shortcut.tree_pick', 'expand / highlight')],
      ['Enter', t('shortcut.tree_toggle', 'toggle checkbox')],
      ['d', t('filter.deselect_all', 'Deselect all topics')],
      ['Esc', t('shortcut.tree_exit', 're-expand & exit')]];
  }
  /* Dot menu (.): context-aware top-level keys in the same bottom panel. */
  function dotMenuOptions() {
    var list = isListView(), nav = list || isDetailView(), horiz = nav && window.location.pathname !== '/search';
    var opts = [['/', t('tooltip.focus_search', 'Search')], ['?', t('shortcut.help_toggle', 'Shortcuts')],
      ['[', t('tooltip.toggle_sidebar', 'Sidebar')], [']', t('tooltip.toggle_tree', 'Tree')], ['g', t('shortcut.dot_go', 'Go…')]];
    if (list) opts.push(['f', t('shortcut.section_filters', 'Filter…')]);
    if ($('formula-tex')) opts.push(['c', t('shortcut.section_copy', 'Copy…')]);
    else if (list) opts.push(['c', t('shortcut.section_clear', 'Clear…')]);
    if (nav) {
      opts.push(['j/k', t('shortcut.list_move', 'Move')]);
      if (horiz) opts.push(['h/l', t('shortcut.list_horizontal', 'Left/right')]);
      opts.push(['Enter', t('shortcut.list_open', 'Open')], ['Tab', t('detail.links', 'Links')]);
    }
    if (list && document.querySelector('[data-load-more-btn]') && document.querySelector('[data-load-more-btn]').offsetParent !== null) opts.push(['m', t('list.load_more', 'Load more')]);
    if ($('equation')) opts.push(['e', t('create.equation', 'Equation')]);
    opts.push(['Esc', t('shortcut.esc_close', 'Close')]);
    return opts;
  }
  function pendingOptions(p) {
    if (p === '.') return dotMenuOptions();
    if (p === 'f') return filterPendingOptions();
    if (p === 'fr') return diffPendingOptions(false);
    if (p === 'fR') return diffPendingOptions(true);
    if (p === 'fde') return dimOpPendingOptions();
    if (p === 'fd' || p === 'fdo') {
      var opts = dimGroupedOptions();
      if (p === 'fd') opts.push(['e', dimOpHint()]);
      return opts.concat([['f', t('filter.fill_zeros', 'Set empty dimension fields to 0')], ['b', t('detail.base_quantities', 'Base quantities')]]);
    }
    if (p === 'fs') return sortLetterOptions();
    if (p === 'c') return copyPendingOptions();
    if (p === 'ft') return treePendingOptions();
    return (PENDING_STATIC[p] || []).map(function(opt) { return opt.length > 2 ? [opt[0], t(opt[1], opt[2])] : [opt[0], opt[1] || '']; });
  }

  /* '/' stays outside <kbd> styling (m/1 means "m or 1"), matching the dialog. */
  function renderPendingKey(key) {
    if (key === '/') return '<kbd>/</kbd>';
    return String(key).split('/').map(function(part) { return '<kbd>' + escapeHtml(part) + '</kbd>'; }).join('/');
  }
  function showPending(p) {
    var el = $('shortcut-pending');
    if (!el) return;
    el.innerHTML = pendingOptions(p).map(function(opt) {
      return '<span class="pending-opt">' + renderPendingKey(opt[0]) + (opt[1] ? ' ' + escapeHtml(opt[1]) : '') + '</span>';
    }).join('');
    el.classList.add('open');
    syncPendingPos();
  }
  function hidePending() {
    var el = $('shortcut-pending');
    if (el) {
      el.classList.remove('open');
      el.style.left = '';
      el.style.right = '';
    }
  }
  /* Pin the pill to the main column: mirror #main-content's rect. The stylesheet offsets stay the fallback. */
  function syncPendingPos() {
    var el = $('shortcut-pending');
    if (!el || !el.classList.contains('open')) return;
    var main = $('main-content');
    if (!main || !main.getBoundingClientRect) return;
    try {
      var r = main.getBoundingClientRect();
      var w = window.innerWidth || document.documentElement.clientWidth || 0;
      var left = Math.max(0, Math.min(w, r.left));
      var right = Math.max(0, Math.min(w, w - r.right));
      el.style.left = left + 'px';
      el.style.right = right + 'px';
    } catch (e) {}
  }
  function watchPendingPos() {
    if (window.addEventListener) window.addEventListener('resize', syncPendingPos);
    if (typeof MutationObserver === 'undefined') return;
    var mo = new MutationObserver(function() {
      if (!$('shortcut-pending') || !$('shortcut-pending').classList.contains('open')) return;
      syncPendingPos();
      /* Sidebar width animates (~200ms); re-sync once it settles. */
      setTimeout(syncPendingPos, 260);
    });
    ['sidebar-left', 'sidebar-right'].forEach(function(id) {
      var sb = $(id);
      if (sb) mo.observe(sb, { attributes: true, attributeFilter: ['class', 'style', 'data-open'] });
    });
  }
  watchPendingPos();
  function setPending(p) {
    pending = p;
    pendingAt = Date.now();
    showPending(p);
    if (pendingTimer) clearTimeout(pendingTimer);
    pendingTimer = setTimeout(function() { pendingTimer = null; if (pending === p) { pendingDimOp = null; clearPending(); } }, SEQ_MS);
  }
  function clearPending() {
    pending = null;
    if (pendingTimer) { clearTimeout(pendingTimer); pendingTimer = null; }
    hidePending();
    clearHints();
  }

  var SHORTCUT_SECTIONS = [
    { titleKey: 'shortcut.section_global', titleFallback: 'Global', rows: [
      { html: '<kbd>/</kbd> / <kbd>Ctrl K</kbd>', labelKey: 'tooltip.focus_search', labelFallback: 'Focus search ( / )' },
      { html: '<kbd>Ctrl</kbd> + <kbd>,</kbd>', labelKey: 'tooltip.settings', labelFallback: 'Settings' },
      { html: '<kbd>?</kbd>', labelKey: 'shortcut.help_toggle', labelFallback: 'Show or hide this dialog' },
      { html: '<kbd>.</kbd>', labelKey: 'shortcut.dot_menu', labelFallback: 'Show available keys' },
      { html: '<kbd>[</kbd> / <kbd>Ctrl B</kbd>', labelKey: 'tooltip.toggle_sidebar', labelFallback: 'Toggle sidebar' },
      { html: '<kbd>]</kbd> / <kbd>Ctrl Shift B</kbd>', labelKey: 'tooltip.toggle_tree', labelFallback: 'Toggle tree' },
      { html: '<kbd>g</kbd> <kbd>f</kbd> / <kbd>Alt 1</kbd>', labelKey: 'nav.formulas', labelFallback: 'Formulas' },
      { html: '<kbd>g</kbd> <kbd>q</kbd> / <kbd>Alt 2</kbd>', labelKey: 'detail.quantities', labelFallback: 'Quantities' },
      { html: '<kbd>g</kbd> <kbd>c</kbd>', labelKey: 'settings.create', labelFallback: 'Create' },
      { html: '<kbd>g</kbd> <kbd>h</kbd>', labelKey: 'shortcut.go_home', labelFallback: 'Home' },
      { html: '<kbd>Esc</kbd>', labelKey: 'shortcut.esc_close', labelFallback: 'Close dialog, menu or highlight, or clear search' },
    ] },
    { titleKey: 'shortcut.section_filters', titleFallback: 'Filters', rows: [
      { html: '<kbd>f</kbd> <kbd>q</kbd>', labelKey: 'detail.quantity', labelFallback: 'Quantity' },
      { html: '<kbd>f</kbd> <kbd>Q</kbd>', labelFn: function() { return modeToggleLabel(false); } },
      { html: '<kbd>f</kbd> <kbd>d</kbd>', labelKey: 'filter.dimension', labelFallback: 'Dimension' },
      { html: '<kbd>f</kbd> <kbd>D</kbd>', labelFn: function() { return modeToggleLabel(true); } },
      { html: '<kbd>f</kbd> <kbd>d</kbd> <kbd>f</kbd>', labelKey: 'filter.fill_zeros', labelFallback: 'Set empty dimension fields to 0' },
      { html: '<kbd>f</kbd> <kbd>d</kbd> <kbd>b</kbd>', labelKey: 'detail.base_quantities', labelFallback: 'Base quantities' },
      { html: '<kbd>f</kbd> <kbd>s</kbd>', labelKey: 'sort.section', labelFallback: 'Sort' },
      { html: '<kbd>f</kbd> <kbd>r</kbd> <kbd>0</kbd>–<kbd>9</kbd> (0 = 10)', labelKey: 'detail.difficulty_min', labelFallback: 'Minimum difficulty' },
      { html: '<kbd>f</kbd> <kbd>R</kbd> <kbd>0</kbd>–<kbd>9</kbd> (0 = 10)', labelKey: 'detail.difficulty_max', labelFallback: 'Maximum difficulty' },
      { html: '<kbd>f</kbd> <kbd>t</kbd>', labelKey: 'nav.tree', labelFallback: 'Tree' },
      { html: '<kbd>f</kbd> <kbd>t</kbd> <kbd>d</kbd>', labelKey: 'filter.deselect_all', labelFallback: 'Deselect all topics' },
    ] },
    { titleKey: 'shortcut.section_lists', titleFallback: 'Results & details', rows: [
      { html: '<kbd>j</kbd> / <kbd>k</kbd> / <kbd>↑</kbd> / <kbd>↓</kbd>', labelKey: 'shortcut.list_move', labelFallback: 'Move up / down' },
      { html: '<kbd>h</kbd> / <kbd>l</kbd> / <kbd>←</kbd> / <kbd>→</kbd>', labelKey: 'shortcut.list_horizontal', labelFallback: 'Move left / right' },
      { html: '<kbd>Enter</kbd>', labelKey: 'shortcut.list_open', labelFallback: 'Open' },
      { html: '<kbd>Tab</kbd>', labelKey: 'detail.links', labelFallback: 'Links' },
      { html: '<kbd>m</kbd>', labelKey: 'list.load_more', labelFallback: 'Load more' },
    ] },
    { titleKey: 'shortcut.section_copy', titleFallback: 'Copy formula as', rows: 'copy' },
    { titleKey: 'shortcut.section_clear', titleFallback: 'Clear filter', rows: 'clear' },
    { titleKey: 'settings.create', titleFallback: 'Create', rows: [
      { html: '<kbd>Ctrl Enter</kbd>', labelKey: 'shortcut.create_continue', labelFallback: 'Continue to SQL' },
      { html: '<kbd>e</kbd>', labelKey: 'create.equation', labelFallback: 'Equation' },
    ] },
  ];

  function prefixDialogRows(keys, labelOf) {
    return keys.map(function(k) { var L = labelOf(k); return typeof L === 'string' ? { html: '<kbd>c</kbd> <kbd>' + k + '</kbd>', label: L } : { html: '<kbd>c</kbd> <kbd>' + k + '</kbd>', labelKey: L[0], labelFallback: L[1] }; });
  }
  function renderShortcutSections() {
    var host = $('shortcuts-sections');
    if (!host) return;
    host.innerHTML = '<table class="shortcuts-table">' + SHORTCUT_SECTIONS.map(function(sec) {
      var copyKeys = Object.keys(COPY_FORMATS);
      if ($('formula-sql-modal')) copyKeys = copyKeys.concat(['s']);
      var rows = sec.rows === 'copy' ? prefixDialogRows(copyKeys, function(k) { return k === 's' ? 'SQL' : COPY_FORMATS[k][1]; })
        : sec.rows === 'clear' ? prefixDialogRows(Object.keys(CLEAR_DEFS), function(k) { return [CLEAR_DEFS[k].key, CLEAR_DEFS[k].fb]; }) : sec.rows;
      return '<tbody><tr class="shortcuts-head-row"><td colspan="2"><h3>' + escapeHtml(t(sec.titleKey, sec.titleFallback)) + '</h3></td></tr>' +
        rows.map(function(r) { return '<tr><td>' + r.html + '</td><td>' + escapeHtml(('label' in r) ? r.label : (r.labelFn ? r.labelFn() : t(r.labelKey, r.labelFallback))) + '</td></tr>'; }).join('') + '</tbody>';
    }).join('') + '</table>';
  }

  /* ---- Shortcuts dialog + settings menu (shared open/close shape) ---- */
  function setOpen(el, open) { if (el) el.classList.toggle('open', !!open); }
  function isOpen(el) { return !!(el && el.classList.contains('open')); }
  function openShortcuts() {
    var m = $('shortcuts-modal');
    if (!m) return;
    clearPending();
    renderShortcutSections();
    lastFocus = document.activeElement;
    setOpen($('settings-menu'), false);
    setOpen(m, true);
    if (typeof refreshIcons === 'function') refreshIcons();
    var btn = m.querySelector('[data-action="close-shortcuts"]');
    if (btn) btn.focus();
  }
  function closeShortcuts() {
    var m = $('shortcuts-modal');
    if (!isOpen(m)) return false;
    setOpen(m, false);
    if (lastFocus && lastFocus.focus) { try { lastFocus.focus(); } catch (e) {} }
    return true;
  }
  function toggleShortcuts() { if (!closeShortcuts()) openShortcuts(); }
  window._openShortcuts = openShortcuts;
  window._closeShortcuts = closeShortcuts;

  function settingsFocusables() {
    var m = $('settings-menu');
    return m ? qsa('button, a[href], select', m).filter(function(el) { return el.offsetParent !== null; }) : [];
  }
  function isSettingsOpen() { return isOpen($('settings-menu')); }
  function openSettings() {
    if (!$('settings-menu')) return false;
    clearPending();
    closeShortcuts();
    setOpen($('settings-menu'), true);
    var items = settingsFocusables();
    if (items.length) focusEl(items[0]);
    return true;
  }
  function closeSettings() {
    if (!isSettingsOpen()) return false;
    setOpen($('settings-menu'), false);
    var btn = document.querySelector('[data-action="toggle-settings"]');
    if (btn) btn.focus();
    return true;
  }
  function moveSettingsFocus(dir) {
    var items = settingsFocusables();
    if (!items.length) return false;
    var idx = items.indexOf(document.activeElement);
    focusEl(items[idx === -1 ? (dir > 0 ? 0 : items.length - 1) : (idx + dir + items.length) % items.length]);
    return true;
  }

  document.addEventListener('click', function(e) {
    if (!e.target.closest) return;
    if (e.target.closest('[data-action="open-shortcuts"]')) { openShortcuts(); return; }
    if (e.target.closest('[data-action="close-shortcuts"]')) { closeShortcuts(); return; }
    var m = $('shortcuts-modal');
    if (isOpen(m) && e.target === m) closeShortcuts();
    ['formula-sql-modal', 'sql-modal'].forEach(function(id) {
      var modal = $(id);
      if (modal && modal.classList.contains('open') && e.target === modal) {
        var closer = modal.querySelector('[data-action="close-formula-sql"], [data-action="close-modal"]');
        if (closer) closer.click();
        else modal.classList.remove('open');
      }
    });
  });

  /* ---- Escape chain ---- */
  function escChain() {
    var si;
    var steps = [
      function() { if (pending) { pendingDimOp = null; clearPending(); return true; } },
      function() { if (treeMode.active) { exitTreeMode(true); return true; } },
      demoteNavLink,
      function() { if (navHighlightEl()) { clearNavHighlight(); focusBody(); return true; } },
      function() { if (isSettingsOpen()) return closeSettings(); },
      closeShortcuts,
      function() { if (window._closeOverlays && window._closeOverlays()) return true; },
      function() {
        si = document.querySelector('.topbar-search input[name="q"]');
        if (si && document.activeElement === si) {
          var url = new URL(window.location), hadQ = url.searchParams.has('q');
          window.SFUtils.clearSearchInput(true);
          if (hadQ) {
            var clean = window.SFUtils.stripQFromUrl(url);
            if (url.pathname === '/search' && typeof window._navigateTo === 'function') window._navigateTo(clean);
            else { try { history.replaceState({ url: clean }, '', clean); } catch (e) {} }
          }
          return true;
        }
      },
      function() { var ae = document.activeElement; if (ae && ae !== document.body && ae.blur) { ae.blur(); return true; } },
    ];
    return steps.some(function(fn) { try { return fn() === true; } catch (e) { return false; } });
  }
  function suggestionsOwnKeys() {
    var s = $('search-suggestions'), q = $('qty-results');
    return !!((s && s.classList.contains('open')) || (q && q.classList.contains('open')));
  }

  /* ---- Main key handler ---- */
  function moveVertical(dir) { return isDetailView() ? moveDetail(dir, 'vertical') : moveContainer(dir, 'vertical'); }
  function handleHorizontal(dir) {
    if (isDetailView()) {
      if (dir > 0) return navHighlightEl() ? detailDrillOrNext() : false;
      var hCur = navHighlightEl();
      if (linkModeActive() && hCur && hCur.classList && hCur.classList.contains('formula-card')) { focusBody(); return true; }
      return demoteNavLink() || moveDetail(-1, 'horizontal');
    }
    if (window.location.pathname === '/quantities') {
      var lCur = navHighlightEl();
      if (!lCur) return false;
      if (dir < 0) return demoteNavLink();
      if (linkModeActive()) return stepLinks(listLinks(), 1);
      return focusLink(lCur.tagName === 'A' ? lCur : lCur.querySelector('a'));
    }
    return window.location.pathname === '/formulas' ? moveContainer(dir, 'horizontal') : false;
  }

  /* Single-key actions, shared by the normal flow and the dot menu. */
  function handleTopKey(e) {
    if (e.key === 'Tab' && !e.shiftKey) {
      var tabCur = navHighlightEl(), tabAe = document.activeElement;
      if (tabCur && tabAe && !isEditable(tabAe) && !(tabAe.closest && tabAe.closest('a'))) {
        if (isDetailView()) { e.preventDefault(); detailDrillOrNext(); return; }
        var tabFirst = tabCur.tagName === 'A' ? tabCur : tabCur.querySelector('a');
        if (tabFirst) { e.preventDefault(); focusLink(tabFirst); }
        return;
      }
    }
    if (e.key === 'Enter') {
      var entCur = navHighlightEl(), entAe = document.activeElement;
      if (entCur && (!entAe || entAe === document.body)) {
        var entLink = entCur.tagName === 'A' ? entCur : detailFocusable(entCur, 'a');
        if (entLink) { e.preventDefault(); entLink.click(); return; }
        if (isDetailView()) {
          var entBtn = entCur.querySelector ? entCur.querySelector('button:not([disabled])') : null;
          if (entBtn) {
            e.preventDefault();
            entBtn.click();
            if (entCur.classList && entCur.classList.contains('si-toggle-row')) focusSiBaseUnit(entCur);
            return;
          }
        }
      }
      return;
    }
    var TOP_KEYS = {
      '/': function() { e.preventDefault(); focusSearch(); },
      '?': function() { e.preventDefault(); toggleShortcuts(); },
      '.': function() { setPending('.'); },
      '[': function() { clickAction('toggle-sidebar-left'); },
      ']': function() { clickAction('toggle-sidebar-right'); },
      'g': function() { setPending('g'); },
      'f': function() { if (isListView()) setPending('f'); },
      'c': function() { if ($('formula-tex') || isListView()) setPending('c'); },
      'j': function() { moveVertical(1); },
      'k': function() { moveVertical(-1); },
      'h': function() { handleHorizontal(-1); },
      'l': function() { handleHorizontal(1); },
      'm': function() { if (isListView()) loadMore(); },
      'e': function() { if ($('equation')) { e.preventDefault(); focusEl($('equation')); } },
      'E': function() { if ($('equation')) { e.preventDefault(); focusEl($('equation')); } },
      'ArrowDown': function() { if (moveVertical(1)) e.preventDefault(); },
      'ArrowUp': function() { if (moveVertical(-1)) e.preventDefault(); },
      'ArrowLeft': function() { if (handleHorizontal(-1)) e.preventDefault(); },
      'ArrowRight': function() { if (handleHorizontal(1)) e.preventDefault(); },
    };
    if (TOP_KEYS[e.key]) TOP_KEYS[e.key]();
  }

  var PENDING_HANDLERS = {
    g: function(k) {
      if (k === 'f' || k === 'F') gotoView('formulas');
      else if (k === 'q' || k === 'Q') gotoView('quantities');
      else if (k === 'c' || k === 'C') gotoCreate();
      else if (k === 'h' || k === 'H') gotoHome();
    },
    f: function(k) { handleFilterKey(k); },
    fr: function(k) { setDiffBound(false, k); },
    fR: function(k) { setDiffBound(true, k); },
    c: function(k) { handleCopyKey(k.toLowerCase()); },
  };

  document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && !e.altKey) {
      if (e.key === 'Enter') {
        if ($('create-form')) {
          var cont = document.querySelector('[data-action="continue-to-sql"]');
          if (cont) { e.preventDefault(); cont.click(); }
        }
        return;
      }
      if (e.key === ',') { e.preventDefault(); if (isSettingsOpen()) closeSettings(); else openSettings(); return; }
      if (e.key === 'k' || e.key === 'K') { e.preventDefault(); focusSearch(); return; }
      if ((e.key === 'b' || e.key === 'B') && !e.shiftKey) { e.preventDefault(); clickAction('toggle-sidebar-left'); return; }
      if (e.key === 'B' && e.shiftKey) { e.preventDefault(); clickAction('toggle-sidebar-right'); return; }
      return;
    }
    if (e.altKey && !e.ctrlKey && !e.metaKey) {
      var ak = (e.key || '').toLowerCase();
      if (ak === '1') { e.preventDefault(); gotoView('formulas'); }
      else if (ak === '2') { e.preventDefault(); gotoView('quantities'); }
      else if (ak === ']') { e.preventDefault(); clickAction('toggle-sidebar-right'); }
      return;
    }
    if (e.key === 'Escape') { escChain(); return; }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (isSettingsOpen()) {
      var sAe = document.activeElement;
      if (sAe && sAe.closest && sAe.closest('#settings-menu')) {
        if (e.key === 'j' || e.key === 'l' || e.key === 'ArrowDown' || e.key === 'ArrowRight') { e.preventDefault(); moveSettingsFocus(1); return; }
        if (e.key === 'k' || e.key === 'h' || e.key === 'ArrowUp' || e.key === 'ArrowLeft') { e.preventDefault(); moveSettingsFocus(-1); return; }
      }
    }
    if (isEditable(document.activeElement)) {
      if (treeMode.active) exitTreeMode(true);
      if (!isModifierKey(e)) clearPending();
      return;
    }
    if (treeMode.active) {
      if (e.key === '/' || e.key === '?') exitTreeMode(true);
      else { handleTreeKey(e); return; }
    }

    if (pending) {
      if (isModifierKey(e)) return;
      var p = pending, age = Date.now() - pendingAt;
      clearPending();
      if (age <= SEQ_MS && e.key !== 'Tab' && e.key !== 'Enter') {
        if (e.key.length === 1) e.preventDefault();
        if (p === '.') { if (e.key !== '.') handleTopKey(e); }
        else if (e.key === '.') setPending('.');
        else if (PENDING_HANDLERS[p]) PENDING_HANDLERS[p](e.key);
        else if (p === 'fd' || p === 'fde' || p === 'fdo') handleDimKey(e.key.length === 1 ? e.key.toLowerCase() : e.key, e.key.length === 1 && e.shiftKey, p);
        else if (p === 'fs') handleSortKey(e.key); /* case-sensitive: d/D, t/T differ */
        return;
      }
    }

    if (suggestionsOwnKeys()) {
      if (e.key === '?') { e.preventDefault(); toggleShortcuts(); }
      return;
    }

    handleTopKey(e);
  });
})();
