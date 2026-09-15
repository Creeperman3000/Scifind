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
  var pending = null;
  var pendingAt = 0;
  var pendingTimer = null;
  var lastFocus = null;
  var sortMode = { openedMenu: false };
  var treeMode = { active: false, hl: null };

  function isEditable(el) {
    if (!el || !el.tagName) return false;
    var tag = el.tagName.toLowerCase();
    if (tag === 'textarea' || tag === 'select') return true;
    if (tag === 'input') {
      var type = (el.type || 'text').toLowerCase();
      if (type === 'hidden') return false;
      if (type === 'checkbox' || type === 'radio' || type === 'button' ||
          type === 'submit' || type === 'reset' || type === 'file' ||
          type === 'image') return false;
      return true; /* text-like + range (range keeps native arrows) */
    }
    return !!el.isContentEditable;
  }

  function isListView() {
    var p = window.location.pathname;
    return p === '/formulas' || p === '/quantities' || p === '/search';
  }

  function clickAction(action) {
    var btn = document.querySelector('[data-action="' + action + '"]');
    if (btn) { btn.click(); return true; }
    return false;
  }

  function clickId(id, onlyIfEnabled) {
    var el = $(id);
    if (!el) return false;
    if (onlyIfEnabled && el.classList.contains('disabled')) return false;
    el.click();
    return true;
  }

  function focusEl(el) {
    if (!el) return false;
    var tag = (el.tagName || '').toUpperCase();
    if (!el.hasAttribute('tabindex') &&
        tag !== 'INPUT' && tag !== 'TEXTAREA' && tag !== 'SELECT' &&
        tag !== 'BUTTON' && tag !== 'A') {
      el.setAttribute('tabindex', '-1');
    }
    try { el.focus({ preventScroll: true }); }
    catch (e) { el.focus(); }
    reveal(el);
    if (typeof el.select === 'function' && (tag === 'INPUT' || tag === 'TEXTAREA')) {
      try { el.select(); } catch (err) { /* e.g. range inputs */ }
    }
    return true;
  }

  function focusLink(el) {
    if (!el) return false;
    focusEl(el);
    setNavHighlight(el);
    return true;
  }

  function sidebarClosed(side) { return !window.SFUtils.sidebarOpenAttr(side); }

  function ensureSidebar(side, fn) {
    if (!sidebarClosed(side)) { fn(); return; }
    clickAction(side === 'left' ? 'toggle-sidebar-left' : 'toggle-sidebar-right');
    requestAnimationFrame(function() { requestAnimationFrame(fn); });
  }

  function focusSearch() {
    var topbar = document.querySelector('.topbar');
    if (topbar && window.innerWidth < 768 && !topbar.classList.contains('expand-search')) {
      clickAction('dock-toggle-search');
    }
    focusEl(document.querySelector('.topbar-search input[name="q"]'));
  }

  function gotoView(view) {
    hidePending();
    var target = window.SFUtils.viewUrl(view, true);
    if (typeof window._navigateTo === 'function') window._navigateTo(target);
    else window.location.href = target;
  }

  function gotoHome() {
    hidePending();
    var logo = document.querySelector('.topbar-logo');
    if (logo) { logo.click(); return; }
    if (typeof window._navigateTo === 'function') window._navigateTo('/formulas');
    else window.location.href = '/';
  }

  /* ---- Result list navigation (formulas / quantities / search) ---- */
  var LIST_LINK_SEL = '#main-content .formula-grid .formula-card a,' +
    ' #main-content tbody[data-list-container] a';

  function listLinks() { return vis(LIST_LINK_SEL); }

  function moveListFocus(dir) {
    var links = listLinks();
    if (!links.length) return false;
    var idx = links.indexOf(document.activeElement);
    var next = idx === -1
      ? (dir > 0 ? 0 : links.length - 1)
      : (idx + dir + links.length) % links.length;
    return focusLink(links[next]);
  }

  /* ---- Two-level result navigation: ROW/CARD mode (.kb-current); Enter opens, Tab drills in ---- */
  function navContainers() {
    var p = window.location.pathname;
    if (p === '/quantities') return vis('#main-content tbody[data-list-container] tr');
    if (p === '/formulas') return vis('#main-content .formula-grid .formula-card');
    return null; /* /search keeps legacy linear link navigation */
  }

  function gridCols(cards) {
    if (!cards.length) return 1;
    var top = cards[0].offsetTop;
    var n = 0;
    for (var i = 0; i < cards.length; i++) {
      if (Math.abs(cards[i].offsetTop - top) < 2) n++;
      else break;
    }
    return Math.max(1, n);
  }

  function focusBody() {
    var ae = document.activeElement;
    if (ae && ae !== document.body && typeof ae.blur === 'function') ae.blur();
  }

  function navHighlightEl() {
    return document.querySelector('.kb-current');
  }

  function linkModeActive() {
    var cur = navHighlightEl();
    var ae = document.activeElement;
    return !!(cur && ae && ae !== document.body && ae.closest &&
      ae.closest('a') && cur.contains(ae));
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
    var scroller = $('main-content');
    var y = toBottom && scroller ? scroller.scrollHeight : 0;
    if (scroller) {
      if (typeof scroller.scrollTo === 'function') { try { scroller.scrollTo(0, y); } catch (e) { scroller.scrollTop = y; } }
      else scroller.scrollTop = y;
    }
    try { window.scrollTo(0, y); } catch (e) { /* noop */ }
    return true;
  }

  function clampStep(len, idx, dir) {
    return dir > 0 ? Math.min(len - 1, idx + 1) : Math.max(0, idx - 1);
  }

  function stepTo(list, idx, next, dir, axis) {
    if (axis !== 'horizontal' && idx !== -1 && next === idx) return leaveNav(dir > 0);
    gotoContainer(list[next]);
    return true;
  }

  function moveContainer(dir, axis) {
    var list = navContainers();
    if (!list || !list.length) {
      if (window.location.pathname === '/search') return moveListFocus(dir);
      return false;
    }
    var idx = list.indexOf(navHighlightEl());
    var next;
    if (idx === -1) {
      next = dir > 0 ? 0 : list.length - 1;
    } else if (window.location.pathname === '/formulas' && axis === 'vertical') {
      var cols = gridCols(list);
      next = dir > 0
        ? Math.min(list.length - 1, idx + cols)
        : Math.max(0, idx - cols);
    } else if (axis === 'horizontal') {
      var hcols = gridCols(list);
      var col = idx % hcols;
      if (dir < 0) next = col > 0 ? idx - 1 : idx;
      else next = (col < hcols - 1 && idx + 1 < list.length) ? idx + 1 : idx;
    } else {
      next = clampStep(list.length, idx, dir);
    }
    return stepTo(list, idx, next, dir, axis);
  }

  function navContainer(link) {
    if (!link || !link.closest) return null;
    return link.closest('.formula-card') || link.closest('tr') ||
      link.closest('.link-list li') || link;
  }

  function setNavHighlight(link) {
    clearNavHighlight();
    var c = navContainer(link);
    if (c) c.classList.add('kb-current');
  }

  function clearNavHighlight(root) {
    qsa('.kb-current', root).forEach(function(el) { el.classList.remove('kb-current'); });
  }

  document.addEventListener('focusin', function(e) {
    var t = e.target;
    if (!t || t === document.body || t === document) return;
    var link = t.closest ? (t.closest('.formula-card a') ||
      t.closest('tbody[data-list-container] a') ||
      t.closest('#main-content .detail-section table tbody tr a') ||
      t.closest('#main-content .detail-section .link-list a')) : null;
    if (link) setNavHighlight(link);
    else clearNavHighlight();
  });

  /* ---- Detail-page navigation: one flat stream in DOM order ---- */
  var DETAIL_RE = /^\/(formula|quantity|constant|unit)\//;

  function isDetailView() {
    return DETAIL_RE.test(window.location.pathname);
  }

  function detailContainers() {
    var found = [];
    [
      '#main-content .detail-section table tbody tr',
      '#main-content .detail-section .formula-grid .formula-card',
      '#main-content .detail-section .link-list li',
    ].forEach(function(sel) {
      vis(sel).forEach(function(el) { found.push(el); });
    });
    found.sort(function(a, b) {
      if (a === b) return 0;
      var pos = a.compareDocumentPosition(b);
      if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
      if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
      return 0;
    });
    return found;
  }

  function detailGridCards(grid) { return vis('.formula-card', grid); }

  function detailFocusable(container, sel) {
    if (!container || !container.querySelector) return null;
    if (container.tagName === 'A') return container;
    return container.querySelector(sel);
  }

  function detailAllLinks() {
    var out = [];
    detailContainers().forEach(function(c) { vis('a', c).forEach(function(a) { out.push(a); }); });
    return out;
  }

  function moveDetail(dir, axis) {
    var list = detailContainers();
    if (!list.length) return false;
    var idx = list.indexOf(navHighlightEl());
    if (idx === -1) {
      gotoContainer(list[dir > 0 ? 0 : list.length - 1]);
      return true;
    }
    var cur = list[idx];
    var grid = cur.closest ? cur.closest('.formula-grid') : null;
    if (grid && cur.classList.contains('formula-card')) {
      var cards = detailGridCards(grid);
      var pos = cards.indexOf(cur);
      var cols = gridCols(cards);
      if (axis === 'vertical') {
        var v = pos + dir * cols;
        if (v >= 0 && v < cards.length) { gotoContainer(cards[v]); return true; }
      } else {
        var h = pos + dir;
        if (h >= 0 && h < cards.length &&
            Math.abs(cards[h].offsetTop - cur.offsetTop) < 2) {
          gotoContainer(cards[h]);
          return true;
        }
      }
      var first = list.indexOf(cards[0]);
      var last = list.indexOf(cards[cards.length - 1]);
      var edge = dir > 0 ? last + 1 : first - 1;
      if (edge >= 0 && edge < list.length) gotoContainer(list[edge]);
      else if (axis !== 'horizontal') leaveNav(dir > 0);
      return true;
    }
    var next = clampStep(list.length, idx, dir);
    stepTo(list, idx, next, dir, axis);
    return true;
  }

  function detailStepLink(dir) {
    var links = detailAllLinks();
    if (!links.length) return false;
    var li = links.indexOf(document.activeElement);
    if (li !== -1 && li + dir >= 0 && li + dir < links.length) {
      focusLink(links[li + dir]);
    } else {
      focusBody();
    }
    return true;
  }

  function detailDrillOrNext() {
    var cur = navHighlightEl();
    if (!cur) return false;
    if (linkModeActive()) return detailStepLink(1);
    var first = detailFocusable(cur, 'a, button:not([disabled])');
    if (first) return focusLink(first);
    return moveDetail(1, 'horizontal');
  }

  function focusSiBaseUnit(toggleRow) {
    var table = toggleRow.closest ? toggleRow.closest('table') : null;
    if (!table || !table.classList.contains('si-expanded')) return;
    var base = table.querySelector('tbody tr[data-exp="0"]') ||
      table.querySelector('tbody tr:not(.si-toggle-row)');
    if (base && base.offsetParent !== null) gotoContainer(base);
  }

  function loadMore() {
    var btn = document.querySelector('[data-load-more-btn]');
    if (btn && btn.offsetParent !== null && !btn.dataset.loading) {
      btn.click();
      return true;
    }
    return false;
  }

  /* ---- Filter (f-prefix) focus targets ---- */
  function handleFilterKey(k) {
    if (!isListView()) return true;
    switch (k) {
      case 'q':
        ensureSidebar('left', function() {
          var inp = $('qty-search');
          if (!inp) return;
          focusEl(inp);
          if (typeof window.renderQtyResults === 'function') {
            window.renderQtyResults(inp.value);
          }
        });
        break;
      case 'd':
        ensureSidebar('left', function() { enterDimMode(); });
        break;
      case 's':
        ensureSidebar('left', function() { enterSortMode(); });
        break;
      case 'r':
        ensureSidebar('left', function() { focusEl($('diff-min')); });
        break;
      case 't':
        enterTreeMode();
        break;
      default:
        break;
    }
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

  /* ---- Dimension picker (f d …): letter/1-7 focuses the field directly;
      f d e g/l/e letter/1-7 picks the operator first, then the field;
      f fills empties with 0, b toggles base quantities ---- */
  var DIM_LETTERS = { m: 'M', l: 'L', t: 'T', i: 'I', n: 'N', j: 'J' };
  var DIM_OPS = { l: 'leq', g: 'geq', e: 'eq' };

  function dimRows() { return qsa('.filter-dim-row'); }

  function dimRowLetters() {
    var taken = {};
    var out = dimRows().map(function(row) { return { row: row, letter: null }; });
    out.forEach(function(entry) {
      var sym = (entry.row.getAttribute('data-dim') || '').toUpperCase();
      Object.keys(DIM_LETTERS).forEach(function(L) {
        if (!entry.letter && DIM_LETTERS[L] === sym && !taken[L]) {
          entry.letter = L;
          taken[L] = true;
        }
      });
    });
    out.forEach(function(entry) {
      if (!entry.letter && !taken.h) { entry.letter = 'h'; taken.h = true; }
    });
    return out;
  }

  /* One chip per row grouping both keys: "m/1", "l/2", … plus the
     plain sidebar dimension name (.dim-name text, else raw symbol). */
  function dimGroupedOptions() {
    return dimRowLetters().map(function(entry, i) {
      var num = String(i + 1);
      var key = entry.letter ? entry.letter + '/' + num : num;
      var nameEl = entry.row.querySelector('.dim-name');
      var label = (nameEl ? nameEl.textContent.trim() : '') || entry.row.getAttribute('data-dim') || '';
      return [key, label];
    });
  }

  function dimRowFor(k) {
    if (/^[1-9]$/.test(k)) {
      var rows = dimRows();
      return rows[parseInt(k, 10) - 1] || null;
    }
    var found = null;
    dimRowLetters().forEach(function(entry) {
      if (entry.letter === k) found = found || entry.row;
    });
    return found;
  }

  var pendingDimOp = null;

  function enterDimMode() { pendingDimOp = null; clearPending(); setPending('fd'); }

  function handleDimKey(k, shifted, state) {
    if (state === 'fde') {
      if (DIM_OPS[k]) { pendingDimOp = DIM_OPS[k]; setPending('fdo'); }
      else setPending('fde');
      return true;
    }
    if (k === 'f' || k === 'b') {
      pendingDimOp = null;
      clearPending();
      if (isListView()) clickId(k === 'f' ? 'dim-fill-zeros' : 'dim-base-qty', true);
      return true;
    }
    if (state === 'fd' && k === 'e' && !shifted) {
      setPending('fde');
      return true;
    }
    var row = dimRowFor(k);
    if (!row) {
      setPending(state); /* unknown key: stay in picker mode */
      return true;
    }
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
    if (label && sel.options && sel.selectedIndex >= 0 &&
        sel.options[sel.selectedIndex]) {
      label.textContent = sel.options[sel.selectedIndex].textContent.trim();
    }
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }

  /* ---- Sort picker (f s …): r/q/i/n/d/D/t/T (case-sensitive) ---- */
  var SORT_LETTERS = {
    r: 'relevance',
    q: 'qty', i: 'id', n: 'name',
    d: 'diff_asc', D: 'diff_desc', t: 'topic_tree', T: 'topic_alpha',
  };

  function sortLetterOptions() {
    var allowed = window._availableSorts || [];
    var labels = (window._localeUI && window._localeUI.sort) || {};
    var opts = [];
    Object.keys(SORT_LETTERS).forEach(function(L) {
      var key = SORT_LETTERS[L];
      if (allowed.indexOf(key) !== -1) opts.push([L, labels[key] || key]);
    });
    return opts;
  }

  function enterSortMode() {
    clearPending();
    sortMode.openedMenu = false;
    var menu = $('sort-menu');
    if (menu && !menu.classList.contains('open')) {
      if (clickId('sort-trigger')) sortMode.openedMenu = true;
    }
    setPending('fs');
  }

  function handleSortKey(L) {
    var key = SORT_LETTERS[L];
    var allowed = window._availableSorts || [];
    if (!key || allowed.indexOf(key) === -1) { enterSortMode(); return true; }
    var btn = document.querySelector('#sort-menu [data-sort="' + key + '"]');
    if (btn) btn.click(); /* absent == already selected */
    clearPending();
    return true;
  }

  /* ---- Topic-tree navigator (f t): 1-9 drills, Enter toggles, d deselects, Esc exits ---- */
  function treeApi() {
    var T = window._topicTree;
    if (!T || window._topicTreeMode !== 'checkbox') return null;
    if (!document.getElementById('science-tree')) return null;
    return T;
  }

  function treeVisibleRows() { return vis('#science-tree .tree-row'); }

  function treeRowById(id) {
    var rows = treeVisibleRows();
    for (var i = 0; i < rows.length; i++) {
      if (rows[i].getAttribute('data-id') === id) return rows[i];
    }
    return null;
  }

  function treeRowDepth(row) {
    return parseInt(row.getAttribute('data-depth') || '0', 10) || 0;
  }

  function treeChildrenOf(row, rows) {
    rows = rows || treeVisibleRows();
    var out = [];
    var depth = treeRowDepth(row);
    var started = false;
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
    var depth = treeRowDepth(row);
    var idx = rows.indexOf(row);
    var out = [];
    var i = idx;
    while (i - 1 >= 0 && treeRowDepth(rows[i - 1]) >= depth) {
      i--;
      if (treeRowDepth(rows[i]) === depth) out.unshift(rows[i]);
    }
    out.push(row);
    i = idx;
    while (i + 1 < rows.length && treeRowDepth(rows[i + 1]) >= depth) {
      i++;
      if (treeRowDepth(rows[i]) === depth) out.push(rows[i]);
    }
    return out;
  }

  function treeCandidates() {
    var rows = treeVisibleRows();
    if (!treeMode.hl) {
      return rows.filter(function(r) { return treeRowDepth(r) === 0; });
    }
    var hlRow = treeRowById(treeMode.hl);
    if (!hlRow) return [];
    var kids = treeChildrenOf(hlRow, rows);
    return kids.length ? kids : treeSiblingsOf(hlRow, rows);
  }

  function isBranchNode(node) {
    if (!node) return false;
    if (typeof node.hasChildren === 'function') return node.hasChildren();
    return (node.children || []).length > 0;
  }

  function treeWalkBranches(fn) {
    var T = treeApi();
    if (!T) return;
    var root = T.getRootNode();
    var stack = (root && root.children ? root.children.slice() : []);
    while (stack.length) {
      var node = stack.pop();
      if (!isBranchNode(node)) continue;
      fn(node);
      var kids = node.children || [];
      for (var i = kids.length - 1; i >= 0; i--) stack.push(kids[i]);
    }
  }

  function setTreeAll(open) {
    var T = treeApi();
    if (!T) return;
    treeWalkBranches(function(node) {
      if (node.state && ((open && !node.state.open) || (!open && node.state.open))) {
        if (open) T.openNode(node);
        else T.closeNode(node);
      }
    });
  }

  function expandTreeNodeById(id) {
    var T = treeApi();
    if (!T) return false;
    var node = T.getNodeById(id);
    if (!node) return false;
    if (isBranchNode(node) && node.state && !node.state.open) T.openNode(node);
    return true;
  }

  function clearTreeHighlight() { clearNavHighlight($('science-tree')); }

  function refreshTreeHints() {
    clearHints();
    clearTreeHighlight();
    var hlRow = treeMode.hl ? treeRowById(treeMode.hl) : null;
    if (hlRow) hlRow.classList.add('kb-current');
    treeCandidates().slice(0, 9).forEach(function(row, i) { badgeRow(row, String(i + 1)); });
  }

  function enterTreeMode() {
    if (!treeApi()) {
      ensureSidebar('right', function() { focusEl($('science-tree')); });
      return;
    }
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
    clearTreeHighlight();
    hidePending();
    if (reexpand) setTreeAll(true);
  }

  function treeDigit(n) {
    var cands = treeCandidates();
    var row = cands[n - 1];
    if (!row) return;
    expandTreeNodeById(row.getAttribute('data-id')); /* no-op for leaves */
    treeMode.hl = row.getAttribute('data-id');
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
    if (e.key === 'Enter') { treeCommit(); return; }
    if (e.key.length === 1 && e.key >= '1' && e.key <= '9') {
      treeDigit(parseInt(e.key, 10));
      return;
    }
    if (e.key.length === 1 && e.key.toLowerCase() === 'd') { treeAction(); return; }
  }

  function treeAction() {
    exitTreeMode(true);
    if (!isListView()) return;
    clickId('tree-deselect-all', true);
  }

  /* ---- Copy & clear (c-prefix) ---- */
  var CLEAR_RESETS = {
    all: ['dim-reset', 'qty-reset', 'diff-reset', 'tree-select-all'],
    qty: ['qty-reset'],
    dim: ['dim-reset'],
    diff: ['diff-reset'],
    tree: ['tree-select-all'],
  };
  function clearFilters(which) {
    if (!isListView()) return;
    (CLEAR_RESETS[which] || []).forEach(function(id) { clickId(id); });
  }

  var COPY_FORMATS = { l: ['latex', 'LaTeX'], u: ['unicode', 'Unicode'], p: ['png', 'PNG'], v: ['svg', 'SVG'] };
  var CLEAR_IDS = { a: 'all', q: 'qty', d: 'dim', r: 'diff', t: 'tree' };
  var CLEAR_LABELS = {
    a: ['heading.all', 'All'], q: ['detail.quantity', 'Quantity'],
    d: ['filter.dimension', 'Dimension'], r: ['detail.difficulty', 'Difficulty'],
    t: ['nav.tree', 'Tree'],
  };

  function handleCopyKey(k) {
    if (COPY_FORMATS[k]) {
      if ($('formula-tex') && typeof copyFormula === 'function') copyFormula(COPY_FORMATS[k][0]);
    } else if (k === 's') {
      if ($('formula-sql-modal')) {
        var _m = $('formula-copy-menu');
        if (_m) _m.classList.remove('open');
        window.SFUtils.setModal('formula-sql-modal', true);
      }
    } else if (CLEAR_IDS[k]) {
      clearFilters(CLEAR_IDS[k]);
    }
    return true;
  }

  /* ---- Pending-prefix indicator ---- */
  var PENDING_STATIC = {
    g: [['f', 'nav.formulas', 'Formulas'], ['q', 'detail.quantities', 'Quantities'], ['h', 'shortcut.go_home', 'Home']],
    f: [['q', 'detail.quantity', 'Quantity'],
        ['d', 'filter.dimension', 'Dimension'],
        ['s', 'sort.section', 'Sort'],
        ['r', 'detail.difficulty', 'Difficulty'],
        ['t', 'nav.tree', 'Tree']],
    fde: [[ 'l', '≤' ], [ 'g', '≥' ], [ 'e', '=' ]],
  };

  function copyPendingOptions() {
    var opts = [];
    if ($('formula-tex') && typeof copyFormula === 'function') {
      Object.keys(COPY_FORMATS).forEach(function(k) { opts.push([k, COPY_FORMATS[k][1]]); });
    }
    if ($('formula-sql-modal')) {
      opts.push(['s', 'SQL']);
    }
    if (isListView()) {
      Object.keys(CLEAR_LABELS).forEach(function(k) {
        opts.push([k, t(CLEAR_LABELS[k][0], CLEAR_LABELS[k][1])]);
      });
    }
    return opts;
  }

  function treePendingOptions() {
    var n = treeCandidates().slice(0, 9).length;
    return [[n > 1 ? '1–' + n : '1', t('shortcut.tree_pick', 'expand / highlight')],
      ['Enter', t('shortcut.tree_toggle', 'toggle checkbox')],
      ['d', t('filter.deselect_all', 'Deselect all topics')],
      ['Esc', t('shortcut.tree_exit', 're-expand & exit')]];
  }

  /* ---- Dot menu (.): context-aware top-level keys, shown in the
     same bottom panel as the multi-key prefixes ---- */
  function dotMenuOptions() {
    var list = isListView();
    var nav = list || isDetailView();
    var horiz = nav && window.location.pathname !== '/search';
    var opts = [
      ['/', t('tooltip.focus_search', 'Search')],
      ['?', t('shortcut.help_toggle', 'Shortcuts')],
      ['[', t('tooltip.toggle_sidebar', 'Sidebar')],
      [']', t('tooltip.toggle_tree', 'Tree')],
      ['g', t('shortcut.dot_go', 'Go…')],
    ];
    if (list) opts.push(['f', t('shortcut.section_filters', 'Filter…')]);
    if ($('formula-tex')) opts.push(['c', t('shortcut.section_copy', 'Copy…')]);
    else if (list) opts.push(['c', t('shortcut.section_clear', 'Clear…')]);
    if (nav) {
      opts.push(['j/k', t('shortcut.list_move', 'Move')]);
      if (horiz) opts.push(['h/l', t('shortcut.list_horizontal', 'Left/right')]);
      opts.push(['Enter', t('shortcut.list_open', 'Open')]);
      opts.push(['Tab', t('detail.links', 'Links')]);
    }
    var moreBtn = document.querySelector('[data-load-more-btn]');
    if (isListView() && moreBtn && moreBtn.offsetParent !== null) {
      opts.push(['m', t('list.load_more', 'Load more')]);
    }
    if ($('equation')) opts.push(['e', t('create.equation', 'Equation')]);
    opts.push(['Esc', t('shortcut.esc_close', 'Close')]);
    return opts;
  }

  function pendingOptions(p) {
    if (p === '.') return dotMenuOptions();
    if (p === 'fd' || p === 'fdo') {
      var opts = dimGroupedOptions();
      if (p === 'fd') opts.push(['e', '=/≤/≥']);
      return opts.concat([
        ['f', t('filter.fill_zeros', 'Set empty dimension fields to 0')],
        ['b', t('detail.base_quantities', 'Base quantities')]]);
    }
    if (p === 'fs') return sortLetterOptions();
    if (p === 'c') return copyPendingOptions();
    if (p === 'ft') return treePendingOptions();
    return (PENDING_STATIC[p] || []).map(function(opt) {
      return opt.length > 2 ? [opt[0], t(opt[1], opt[2])] : [opt[0], opt[1] || ''];
    });
  }

  /* '/' separates alternative keys and stays outside <kbd> styling
     (e.g. m/1 means "m or 1"), matching the shortcuts dialog. */
  function renderPendingKey(key) {
    if (key === '/') return '<kbd>/</kbd>';
    return String(key).split('/').map(function(part) {
      return '<kbd>' + escapeHtml(part) + '</kbd>';
    }).join('/');
  }

  function showPending(p) {
    var el = $('shortcut-pending');
    if (!el) return;
    el.innerHTML = pendingOptions(p).map(function(opt) {
      return '<span class="pending-opt">' + renderPendingKey(opt[0]) +
        (opt[1] ? ' ' + escapeHtml(opt[1]) : '') + '</span>';
    }).join('');
    el.classList.add('open');
  }

  function hidePending() {
    var el = $('shortcut-pending');
    if (el) el.classList.remove('open');
  }

  function setPending(p) {
    pending = p;
    pendingAt = Date.now();
    showPending(p);
    if (pendingTimer) clearTimeout(pendingTimer);
    pendingTimer = setTimeout(function() {
      pendingTimer = null;
      if (pending === p) { pendingDimOp = null; clearPending(); }
    }, SEQ_MS);
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
      { html: '<kbd>g</kbd> <kbd>h</kbd>', labelKey: 'shortcut.go_home', labelFallback: 'Home' },
      { html: '<kbd>Esc</kbd>', labelKey: 'shortcut.esc_close', labelFallback: 'Close dialog, menu or highlight, or clear search' },
    ] },
    { titleKey: 'shortcut.section_filters', titleFallback: 'Filters', rows: [
      { html: '<kbd>f</kbd> <kbd>q</kbd>', labelKey: 'detail.quantity', labelFallback: 'Quantity' },
      { html: '<kbd>f</kbd> <kbd>d</kbd>', labelKey: 'filter.dimension', labelFallback: 'Dimension' },
      { html: '<kbd>f</kbd> <kbd>d</kbd> <kbd>f</kbd>', labelKey: 'filter.fill_zeros', labelFallback: 'Set empty dimension fields to 0' },
      { html: '<kbd>f</kbd> <kbd>d</kbd> <kbd>b</kbd>', labelKey: 'detail.base_quantities', labelFallback: 'Base quantities' },
      { html: '<kbd>f</kbd> <kbd>s</kbd>', labelKey: 'sort.section', labelFallback: 'Sort' },
      { html: '<kbd>f</kbd> <kbd>r</kbd>', labelKey: 'detail.difficulty', labelFallback: 'Difficulty' },
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

  var _shortcutsRendered = false;

  function copyDialogRows() {
    var rows = Object.keys(COPY_FORMATS).map(function(k) {
      return { html: '<kbd>c</kbd> <kbd>' + k + '</kbd>', label: COPY_FORMATS[k][1] };
    });
    rows.push({ html: '<kbd>c</kbd> <kbd>s</kbd>', label: 'SQL' });
    return rows;
  }

  function clearDialogRows() {
    return Object.keys(CLEAR_LABELS).map(function(k) {
      var L = CLEAR_LABELS[k];
      return { html: '<kbd>c</kbd> <kbd>' + k + '</kbd>', labelKey: L[0], labelFallback: L[1] };
    });
  }

  function renderShortcutSections() {
    var host = $('shortcuts-sections');
    if (!host || _shortcutsRendered) return;
    /* One shared table (a <tbody> per section): column widths are computed
       across the whole table, so every label starts at the same x-coordinate. */
    host.innerHTML = '<table class="shortcuts-table">' + SHORTCUT_SECTIONS.map(function(sec) {
      var rows = sec.rows === 'copy' ? copyDialogRows() : sec.rows === 'clear' ? clearDialogRows() : sec.rows;
      return '<tbody><tr class="shortcuts-head-row"><td colspan="2"><h3>' +
        escapeHtml(t(sec.titleKey, sec.titleFallback)) + '</h3></td></tr>' +
        rows.map(function(r) {
          var label = ('label' in r) ? r.label : t(r.labelKey, r.labelFallback);
          return '<tr><td>' + r.html + '</td><td>' +
            escapeHtml(label) + '</td></tr>';
        }).join('') + '</tbody>';
    }).join('') + '</table>';
    _shortcutsRendered = true;
  }

  /* ---- Shortcuts dialog ---- */
  function overlay() { return $('shortcuts-modal'); }

  function openShortcuts() {
    var m = overlay();
    if (!m) return;
    clearPending();
    renderShortcutSections();
    lastFocus = document.activeElement;
    var sm = $('settings-menu');
    if (sm) sm.classList.remove('open');
    m.classList.add('open');
    if (typeof refreshIcons === 'function') refreshIcons();
    var btn = m.querySelector('[data-action="close-shortcuts"]');
    if (btn) btn.focus();
  }

  function closeShortcuts() {
    var m = overlay();
    if (!m || !m.classList.contains('open')) return false;
    m.classList.remove('open');
    if (lastFocus && lastFocus.focus) {
      try { lastFocus.focus(); } catch (e) { /* opener may be gone after SPA nav */ }
    }
    return true;
  }

  function toggleShortcuts() {
    var m = overlay();
    if (m && m.classList.contains('open')) closeShortcuts();
    else openShortcuts();
  }

  window._openShortcuts = openShortcuts;
  window._closeShortcuts = closeShortcuts;

  /* ---- Settings menu (Ctrl+,): hjkl/arrows move between controls ---- */
  function settingsMenu() { return $('settings-menu'); }

  function isSettingsOpen() {
    var m = settingsMenu();
    return !!(m && m.classList.contains('open'));
  }

  function settingsFocusables() {
    var m = settingsMenu();
    if (!m) return [];
    return qsa('button, a[href], select', m).filter(function(el) {
      return el.offsetParent !== null;
    });
  }

  function openSettings() {
    var m = settingsMenu();
    if (!m) return false;
    clearPending();
    closeShortcuts();
    m.classList.add('open');
    var items = settingsFocusables();
    if (items.length) focusEl(items[0]);
    return true;
  }

  function closeSettings() {
    var m = settingsMenu();
    if (!m || !m.classList.contains('open')) return false;
    m.classList.remove('open');
    var btn = document.querySelector('[data-action="toggle-settings"]');
    if (btn) btn.focus();
    return true;
  }

  function moveSettingsFocus(dir) {
    var items = settingsFocusables();
    if (!items.length) return false;
    var idx = items.indexOf(document.activeElement);
    if (idx === -1) idx = dir > 0 ? 0 : items.length - 1;
    else idx = (idx + dir + items.length) % items.length;
    focusEl(items[idx]);
    return true;
  }

  document.addEventListener('click', function(e) {
    var opener = e.target.closest && e.target.closest('[data-action="open-shortcuts"]');
    if (opener) { openShortcuts(); return; }
    var closer = e.target.closest && e.target.closest('[data-action="close-shortcuts"]');
    if (closer) { closeShortcuts(); return; }
    var m = overlay();
    if (m && m.classList.contains('open') && e.target === m) closeShortcuts();
  });

  /* ---- Escape chain ---- */
  function exitSearchLike() {
    var url = new URL(window.location);
    var hadQ = url.searchParams.has('q');
    var clean = window.SFUtils.stripQFromUrl(url);
    window.SFUtils.clearSearchInput(true);
    if (hadQ) {
      if (url.pathname === '/search' && typeof window._navigateTo === 'function') {
        window._navigateTo(clean);
      } else {
        try { history.replaceState({ url: clean }, '', clean); } catch (e) { /* noop */ }
      }
    }
  }

  function escChain() {
    if (pending) { pendingDimOp = null; clearPending(); return true; }
    if (treeMode.active) { exitTreeMode(true); return true; }
    if (demoteNavLink()) return true;
    if (navHighlightEl()) {
      clearNavHighlight();
      focusBody();
      return true;
    }
    if (isSettingsOpen()) { closeSettings(); return true; }
    if (closeShortcuts()) return true;
    if (window._closeOverlays && window._closeOverlays()) return true;
    var si = document.querySelector('.topbar-search input[name="q"]');
    if (si && document.activeElement === si) { exitSearchLike(); return true; }
    var ae = document.activeElement;
    if (ae && ae !== document.body && ae.blur) { ae.blur(); return true; }
    return false;
  }

  function suggestionsOwnKeys() {
    var s = $('search-suggestions');
    var q = $('qty-results');
    return !!((s && s.classList.contains('open')) || (q && q.classList.contains('open')));
  }

  /* ---- Main key handler ---- */
  function moveVertical(dir) {
    if (isDetailView()) return moveDetail(dir, 'vertical');
    return moveContainer(dir, 'vertical');
  }

  function handleHorizontal(dir) {
    if (isDetailView()) {
      if (dir > 0) {
        if (navHighlightEl()) { detailDrillOrNext(); return true; }
        return false;
      }
      var hCur = navHighlightEl();
      if (linkModeActive() && hCur && hCur.classList && hCur.classList.contains('formula-card')) { focusBody(); return true; }
      if (demoteNavLink()) return true;
      return moveDetail(-1, 'horizontal');
    }
    if (window.location.pathname === '/quantities') {
      var lCur = navHighlightEl();
      if (!lCur) return false;
      if (dir < 0) { return demoteNavLink(); }
      if (linkModeActive()) {
        var lLinks = listLinks();
        var li = lLinks.indexOf(document.activeElement);
        if (li !== -1 && li + 1 < lLinks.length) focusLink(lLinks[li + 1]);
        else focusBody();
        return true;
      }
      return focusLink(lCur.tagName === 'A' ? lCur : lCur.querySelector('a'));
    }
    if (window.location.pathname === '/formulas') return moveContainer(dir, 'horizontal');
    return false;
  }

  document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && !e.altKey) {
      if (e.key === 'Enter') {
        if ($('create-form')) {
          var cont = document.querySelector('[data-action="continue-to-sql"]');
          if (cont) { e.preventDefault(); cont.click(); }
        }
        return;
      }
      if (e.key === ',') {
        e.preventDefault();
        if (isSettingsOpen()) closeSettings();
        else openSettings();
        return;
      }
      if (e.key === 'k' || e.key === 'K') {
        e.preventDefault();
        focusSearch();
        return;
      }
      if ((e.key === 'b' || e.key === 'B') && !e.shiftKey) {
        e.preventDefault();
        clickAction('toggle-sidebar-left');
        return;
      }
      if (e.key === 'B' && e.shiftKey) {
        e.preventDefault();
        clickAction('toggle-sidebar-right');
        return;
      }
      return;
    }
    if (e.altKey && !e.ctrlKey && !e.metaKey) {
      var ak = (e.key || '').toLowerCase();
      if (ak === '1') { e.preventDefault(); gotoView('formulas'); return; }
      if (ak === '2') { e.preventDefault(); gotoView('quantities'); return; }
      if (ak === ']') { e.preventDefault(); clickAction('toggle-sidebar-right'); return; }
      return;
    }
    if (e.key === 'Escape') { escChain(); return; }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (isSettingsOpen()) {
      var sAe = document.activeElement;
      if (sAe && sAe.closest && sAe.closest('#settings-menu')) {
        if (e.key === 'j' || e.key === 'l' || e.key === 'ArrowDown' || e.key === 'ArrowRight') {
          e.preventDefault();
          moveSettingsFocus(1);
          return;
        }
        if (e.key === 'k' || e.key === 'h' || e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
          e.preventDefault();
          moveSettingsFocus(-1);
          return;
        }
      }
    }
    if (isEditable(document.activeElement)) {
      if (treeMode.active) exitTreeMode(true);
      clearPending();
      return;
    }
    if (treeMode.active) {
      if (e.key === '/' || e.key === '?') {
        exitTreeMode(true);
      } else {
        handleTreeKey(e);
        return;
      }
    }

    if (pending) {
      var p = pending;
      var age = Date.now() - pendingAt;
      var low = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      clearPending();
      if (age <= SEQ_MS) {
        if (e.key === 'Tab' || e.key === 'Enter') {
        } else {
          if (e.key.length === 1) e.preventDefault();
        if (p === '.') {
          if (e.key !== '.') handleTopKey(e);
        } else if (e.key === '.') {
          setPending('.');
        } else if (p === 'g') {
          if (e.key === 'f' || e.key === 'F') gotoView('formulas');
          else if (e.key === 'q' || e.key === 'Q') gotoView('quantities');
          else if (e.key === 'h' || e.key === 'H') gotoHome();
        } else if (p === 'f') {
          handleFilterKey(low);
        } else if (p === 'fd' || p === 'fde' || p === 'fdo') {
          handleDimKey(low, e.key.length === 1 && e.shiftKey, p);
        } else if (p === 'fs') {
          handleSortKey(e.key); /* case-sensitive: d/D, t/T differ */
        } else if (p === 'c') {
          handleCopyKey(low);
        }
          return;
        }
      }
    }

    if (suggestionsOwnKeys()) {
      if (e.key === '?') { e.preventDefault(); toggleShortcuts(); }
      return;
    }

    handleTopKey(e);
  });

  /* Single-key actions, shared by the normal flow and the dot menu
     (which clears itself first, then re-dispatches the pressed key). */
  function handleTopKey(e) {
    if (e.key === 'Tab' && !e.shiftKey) {
      var tabCur = navHighlightEl();
      var tabAe = document.activeElement;
      if (tabCur && tabAe && !isEditable(tabAe) &&
          !(tabAe.closest && tabAe.closest('a'))) {
        if (isDetailView()) {
          e.preventDefault();
          detailDrillOrNext();
          return;
        }
        var tabFirst = tabCur.tagName === 'A' ? tabCur : tabCur.querySelector('a');
        if (tabFirst) { e.preventDefault(); focusLink(tabFirst); return; }
      }
    }

    if (e.key === 'Enter') {
      var entCur = navHighlightEl();
      var entAe = document.activeElement;
      if (entCur && (!entAe || entAe === document.body)) {
        var entLink = entCur.tagName === 'A' ? entCur : detailFocusable(entCur, 'a');
        if (entLink) { e.preventDefault(); entLink.click(); return; }
        if (isDetailView()) {
          var entBtn = entCur.querySelector
            ? entCur.querySelector('button:not([disabled])') : null;
          if (entBtn) {
            e.preventDefault();
            var siRow = entCur.classList &&
              entCur.classList.contains('si-toggle-row') ? entCur : null;
            entBtn.click();
            if (siRow) focusSiBaseUnit(siRow);
            return;
          }
        }
      }
    }

    switch (e.key) {
      case '/':
        e.preventDefault();
        focusSearch();
        break;
      case '?':
        e.preventDefault();
        toggleShortcuts();
        break;
      case '.':
        setPending('.');
        break;
      case '[':
        clickAction('toggle-sidebar-left');
        break;
      case ']':
        clickAction('toggle-sidebar-right');
        break;
      case 'g':
        setPending('g');
        break;
      case 'f':
        if (isListView()) setPending('f');
        break;
      case 'c':
        if ($('formula-tex') || isListView()) setPending('c');
        break;
      case 'j':
        moveVertical(1);
        break;
      case 'k':
        moveVertical(-1);
        break;
      case 'h':
        handleHorizontal(-1);
        break;
      case 'l':
        handleHorizontal(1);
        break;
      case 'm':
        if (isListView()) loadMore();
        break;
      case 'e':
      case 'E':
        if ($('equation')) { e.preventDefault(); focusEl($('equation')); }
        break;
      case 'ArrowDown':
        if (moveVertical(1)) e.preventDefault();
        break;
      case 'ArrowUp':
        if (moveVertical(-1)) e.preventDefault();
        break;
      case 'ArrowLeft':
        if (handleHorizontal(-1)) e.preventDefault();
        break;
      case 'ArrowRight':
        if (handleHorizontal(1)) e.preventDefault();
        break;
      default:
        break;
    }
  }
})();
