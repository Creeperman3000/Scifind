/* eslint-disable no-undef */

(function() {
  'use strict';

  function showToast(message, type) {
    var container = document.getElementById('toast-container');
    var t = document.createElement('div');
    t.className = 'toast ' + (type || 'success');
    t.textContent = message;
    container.appendChild(t);
    setTimeout(function() { t.style.opacity = '0'; t.style.transition = 'opacity var(--dur-slow)'; setTimeout(function() { t.remove(); }, 300); }, 4000);
  }
  window.showToast = showToast;

  function refreshIcons() { if (typeof lucide !== 'undefined') lucide.createIcons(); }
  function setCookie(name, value) { document.cookie = name + '=' + value + '; path=/; max-age=31536000'; }

  function dimValInputs() { return Array.prototype.slice.call(document.querySelectorAll('.filter-dim-row .dim-val')); }
  function dimVals() { return dimValInputs().map(function(i) { return i.value.trim(); }); }
  /* A dim field counts as set only if it resolves to an integer — this
     keeps half-typed expressions like "-" from looking like a filter. */
  function dimResolved(v) { return evalDimExpr(v) !== null; }

  /* Evaluate simple integer arithmetic ("2+3*-4", "-(1+5)/2", "2^10")
     with a tiny recursive-descent parser — no eval(). Returns the
     integer result, or null when empty/incomplete/invalid. */
  function evalDimExpr(raw) {
    var s = String(raw == null ? '' : raw).replace(/\s+/g, '');
    if (!s || !/^[-+*/%^().0-9]+$/.test(s)) return null;
    var i = 0;
    function peek() { return s[i]; }
    function fail() { throw new Error('bad'); }
    function expr() {
      var v = term();
      while (peek() === '+' || peek() === '-') {
        var op = s[i++];
        var r = term();
        v = op === '+' ? v + r : v - r;
      }
      return v;
    }
    function term() {
      var v = power();
      while (peek() === '*' || peek() === '/' || peek() === '%') {
        var op = s[i++];
        var r = power();
        if ((op === '/' || op === '%') && r === 0) fail();
        v = op === '*' ? v * r : (op === '/' ? Math.trunc(v / r) : v % r);
      }
      return v;
    }
    function power() {
      var base = unary();
      if (peek() === '^') {
        i++;
        return Math.round(Math.pow(base, power()));
      }
      return base;
    }
    function unary() {
      if (peek() === '+') { i++; return +unary(); }
      if (peek() === '-') { i++; return -unary(); }
      return atom();
    }
    function atom() {
      if (peek() === '(') {
        i++;
        var v = expr();
        if (peek() !== ')') fail();
        i++;
        return v;
      }
      var start = i;
      while (i < s.length && s[i] >= '0' && s[i] <= '9') i++;
      if (start === i) fail();
      return parseInt(s.slice(start, i), 10);
    }
    try {
      var result = expr();
      if (i !== s.length || typeof result !== 'number' || !isFinite(result)) return null;
    } catch (err) {
      return null;
    }
    return Math.round(result);
  }

  /* Commit evaluated results into the fields on blur/Enter so the user
     sees what the filter actually applied. */
  function resolveDimExprs() {
    dimValInputs().forEach(function(input) {
      var resolved = evalDimExpr(input.value);
      if (resolved !== null && String(input.value.trim()) !== String(resolved)) input.value = resolved;
    });
  }
  function replayClass(el, cls) { el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); }

  function syncSearchCancel() {
    var wrap = document.querySelector('.search-input-wrap');
    var input = document.querySelector('.topbar-search input[name="q"]');
    if (wrap && input) wrap.classList.toggle('has-text', input.value.length > 0);
  }
  window.syncSearchCancel = syncSearchCancel;

  function updateOverflowPadding() {
    document.querySelectorAll('.sidebar-scroll').forEach(function(el) {
      var inner = el.querySelector('.sidebar-inner');
      if (!inner) return;
      var cs = getComputedStyle(inner);
      var extraPad = parseFloat(cs.paddingBottom) || 0;
      var contentH = inner.scrollHeight - extraPad;
      el.classList.toggle('no-overflow', contentH <= el.clientHeight);
    });
    var main = document.querySelector('.main');
    if (main) {
      /* Use the real spacer height (35vh on desktop, dock+20px on mobile)
         so mobile doesn't hide the bottom padding too eagerly. While the
         spacer is hidden it doesn't contribute to scrollHeight either. */
      var spacer = main.classList.contains('no-overflow') ? 0
        : (parseFloat(getComputedStyle(main, '::after').height) || 0);
      var contentH = main.scrollHeight - spacer;
      main.classList.toggle('no-overflow', contentH <= main.clientHeight);
    }
  }

  /* Content height changes after the fact (KaTeX renders lazily), so
     re-check the overflow padding whenever it does. */
  (function() {
    if (typeof ResizeObserver === 'undefined') return;
    var raf = null;
    var ro = new ResizeObserver(function() {
      if (raf) return;
      raf = requestAnimationFrame(function() {
        raf = null;
        updateOverflowPadding();
        updateDimNameFits();
      });
    });
    ['.main-inner', '.sidebar-inner'].forEach(function(sel) {
      document.querySelectorAll(sel).forEach(function(el) { ro.observe(el); });
    });
  })();

  /* Hide the dim-name label (e.g. "time") when ANY row would not have
     room for it — once we have to hide it for one, we hide it for all
     so the row columns stay vertically aligned.

     Hysteresis: once names are hidden they stay hidden until EVERY
     name has at least HYSTERESIS_PX of spare room (minSlack), and
     vice versa once shown they stay shown until something actually
     overflows. Without it, dragging the sidebar across the threshold
     makes the names flicker on every ResizeObserver tick. */
  var _dimNameState = { hidden: null };
  var HYSTERESIS_PX = 8;
  function updateDimNameFits() {
    var rows = Array.prototype.slice.call(document.querySelectorAll('.filter-dim-row'));
    if (rows.length === 0) return;
    /* Unhide names so we can measure their natural width. The
       .no-dim-name class uses display:none which would otherwise
       collapse the element and give scrollWidth=0. */
    var wasHidden = rows[0].classList.contains('no-dim-name');
    if (wasHidden) rows.forEach(function(r) { r.classList.remove('no-dim-name'); });
    /* Detach names from the flex layout temporarily so offsetWidth
       returns the unconstrained text width instead of the allocated
       flex slot. */
    var anyOverflow = false;
    var minSlack = Infinity;
    rows.forEach(function(row) {
      var name = row.querySelector('.dim-name');
      if (!name) return;
      var prevStyle = name.getAttribute('style') || '';
      name.style.position = 'absolute';
      name.style.visibility = 'hidden';
      name.style.whiteSpace = 'nowrap';
      name.style.flex = '0 0 auto';
      var natural = name.offsetWidth;
      name.setAttribute('style', prevStyle);
      var siblings = Array.prototype.slice.call(row.children).filter(function(el) {
        return el !== name;
      });
      var fixed = 0;
      siblings.forEach(function(el) {
        fixed += el.getBoundingClientRect().width;
      });
      var style = getComputedStyle(row);
      var gap = parseFloat(style.columnGap || style.gap) || 0;
      fixed += gap * (row.children.length - 1);
      var available = row.clientWidth - fixed;
      var slack = available - natural;
      if (slack < 0) anyOverflow = true;
      if (slack < minSlack) minSlack = slack;
    });
    var shouldHide;
    if (_dimNameState.hidden === null) {
      shouldHide = anyOverflow;
    } else if (_dimNameState.hidden) {
      /* Hidden: show again only when every name fits with slack to spare */
      shouldHide = !(minSlack >= HYSTERESIS_PX);
    } else {
      /* Shown: hide as soon as anything overflows */
      shouldHide = anyOverflow;
    }
    _dimNameState.hidden = shouldHide;
    rows.forEach(function(row) { row.classList.toggle('no-dim-name', shouldHide); });
  }
  window.updateDimNameFits = updateDimNameFits;

  var _latexObserver = null;
  var _latexObserved = new WeakSet();

  function renderLatexEl(el) {
    if (!el || !el.parentNode) return;
    if (typeof katex === 'undefined') return;
    var src = el.getAttribute('data-latex');
    if (src == null || src === '') {
      el.classList.remove('latex-observe');
      return;
    }
    try {
      var display = el.classList.contains('formula-eqn');
      katex.render(src, el, { displayMode: display, throwOnError: false, macros: window._KATEX_MACROS || {} });
      el.removeAttribute('data-latex');
      el.classList.remove('latex-observe');
    } catch (e) { /* leave for retry */ }
  }
  window.renderLatexEl = renderLatexEl;

  function renderLatexIn(el) {
    if (!el || typeof katex === 'undefined') return;
    var nodes = el.querySelectorAll('.latex-observe');
    for (var i = 0; i < nodes.length; i++) renderLatexEl(nodes[i]);
  }

  function ensureLatexObserver() {
    if (_latexObserver) return _latexObserver;
    if (typeof IntersectionObserver === 'undefined') return null;
    _latexObserver = new IntersectionObserver(function(entries) {
      for (var i = 0; i < entries.length; i++) {
        var e = entries[i];
        if (e.isIntersecting) {
          renderLatexEl(e.target);
          _latexObserver.unobserve(e.target);
        }
      }
    }, { root: null, rootMargin: '1500px 0px', threshold: 0 });
    return _latexObserver;
  }

  function observeLatexIn(root) {
    if (!root) return;
    var obs = ensureLatexObserver();
    if (!obs) {
      renderLatexIn(root);
      return;
    }
    var nodes = root.querySelectorAll('.latex-observe');
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i];
      if (_latexObserved.has(n)) continue;
      _latexObserved.add(n);
      obs.observe(n);
    }
  }

  function renderMathInContent() {
    var root = document.querySelector('#main-content');
    if (!root) return;
    if (typeof katex !== 'undefined') {
      observeLatexIn(root);
    }
    if (typeof renderMathInElement === 'function') {
      try { renderMathInElement(root, {
        delimiters: [{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],
        macros: window._KATEX_MACROS || {}
      }); } catch(e) { console.warn('renderMathInElement error', e); }
    }
  }
  window.renderMathInContent = renderMathInContent;

  /* ---------- Topic tree (infinite-tree) ---------- */

  var _treeEl = document.getElementById('science-tree');
  var _topicTree = null;
  var _topicTreeMode = null;

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function(c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* Fully checked = checked and not indeterminate (partial subtree) */
  function isNodeChecked(node) {
    return !!node.state.checked && !node.state.indeterminate;
  }

  /* Recursively true when any ancestor is indeterminate. Used so that
     the whole partial-checked subtree keeps its checkboxes visible,
     matching the old jstree "undetermined-parent" behaviour. */
  function isUnderIndet(node) {
    for (var p = node.parent; p && p.state.depth >= 0; p = p.parent) {
      if (p.state.indeterminate) return true;
    }
    return false;
  }

  function topicTreeRow(node) {
    var s = node.state;
    var branch = node.hasChildren();
    var cls = 'tree-row ' + (branch ? (s.open ? 'open' : 'closed') : 'leaf');
    if (s.indeterminate) cls += ' indeterminate';
    else if (s.checked) cls += ' checked';
    if (s.selected) cls += ' selected';
    /* Root-level rows, indeterminate rows and their descendants always
       show their control (matches the old jstree behaviour where root
       boxes and undetermined-ancestor subtrees never faded out). */
    if (s.depth === 0 || s.indeterminate || isUnderIndet(node)) cls += ' always-visible';
    var html = '<div class="' + cls + '" data-id="' + escapeHtml(node.id) + '"' +
      ' data-depth="' + s.depth + '" style="padding-left:' + (s.depth * 24) + 'px">';
    html += branch ? '<span class="tree-toggler"></span>' : '<span class="tree-leaf-spacer"></span>';
    html += '<span class="tree-label">';
    html += _topicTreeMode === 'radio'
      ? '<span class="tree-radio"></span>'
      : '<span class="tree-checkbox"></span>';
    html += escapeHtml(node.name) + '</span></div>';
    return html;
  }

  function buildTopicTree(mode) {
    if (_topicTree) _topicTree.destroy();
    _topicTreeMode = mode;
    var sidebarRight = document.getElementById('sidebar-right');
    if (sidebarRight) sidebarRight.classList.toggle('tree-radio-mode', mode === 'radio');
    _topicTree = new InfiniteTree(_treeEl, {
      data: window._topicTreeData || [],
      autoOpen: true,
      selectable: mode === 'radio',
      /* Radio mode: clicking a node selects it; clicking the selected
         node again deselects it (the lib emits selectNode(null)). */
      shouldSelectNode: function(node) {
        return _topicTree._programmatic || !!node;
      },
      /* Render every row: the outer sidebar scrolls, and wrapped labels
         have varying heights that the virtualizer cannot handle. */
      rowsInBlock: Infinity,
      togglerClass: 'tree-toggler',
      rowRenderer: topicTreeRow,
    });
    if (mode === 'checkbox') {
      _topicTree.on('click', function(event) {
        var box = event.target.closest ? event.target.closest('.tree-checkbox') : null;
        if (!box) return;
        var row = box.closest('[data-id]');
        var node = row && _topicTree.getNodeById(row.getAttribute('data-id'));
        if (node) _topicTree.checkNode(node); /* toggles, cascades up+down */
      });
      _topicTree.on('checkNode', function() {
        if (!window._restoringFilters) applyFilters();
        setTimeout(syncFilterStates, 0);
      });
    } else {
      _topicTree.on('selectNode', function(node) {
        if (_topicTree._programmatic) return;
        if (typeof window._treeSelectionChanged === 'function') {
          window._treeSelectionChanged(node ? node.id : null);
        }
      });
    }
  }

  /* Rebuild the tree when the page kind changed (e.g. SPA navigation
     between the filter views and /create). */
  function ensureTopicTree() {
    if (!_treeEl || typeof window.InfiniteTree === 'undefined') return;
    var mode = document.getElementById('create-form') ? 'radio' : 'checkbox';
    if (_topicTree && mode === _topicTreeMode) return;
    buildTopicTree(mode);
  }

  function treeRootNodes() {
    return _topicTree ? _topicTree.getRootNode().children : [];
  }

  /* Ids of the roots of checked subtrees (what the server treats as the selection) */
  function topCheckedIds() {
    var ids = [];
    (function walk(nodes) {
      nodes.forEach(function(node) {
        if (isNodeChecked(node)) ids.push(node.id);
        else walk(node.children || []);
      });
    })(treeRootNodes());
    return ids;
  }

  function allRootNodesChecked() {
    var roots = treeRootNodes();
    return roots.length > 0 && roots.every(isNodeChecked);
  }

  window._setTreeSelection = function(id) {
    if (!_topicTree || _topicTreeMode !== 'radio') return;
    var current = _topicTree.getSelectedNode();
    var currentId = current ? current.id : null;
    if ((id || null) === currentId) return;
    _topicTree._programmatic = true;
    try {
      _topicTree.selectNode(id ? _topicTree.getNodeById(id) : null);
    } finally {
      _topicTree._programmatic = false;
    }
  };

  document.getElementById('tree-select-all').addEventListener('click', function() {
    if (_topicTree && _topicTreeMode === 'checkbox') {
      window._restoringFilters = true;
      try {
        treeRootNodes().forEach(function(node) { _topicTree.checkNode(node, true); });
      } finally {
        window._restoringFilters = false;
      }
      applyFilters();
    }
  });
  document.getElementById('tree-deselect-all').addEventListener('click', function() {
    if (_topicTree && _topicTreeMode === 'checkbox') {
      window._restoringFilters = true;
      try {
        treeRootNodes().forEach(function(node) { _topicTree.checkNode(node, false); });
      } finally {
        window._restoringFilters = false;
      }
      applyFilters();
    }
  });
  if (_treeEl) _treeEl.addEventListener('dblclick', function(e) { e.stopPropagation(); });

  function dimFilterChange() { applyFilters(); setTimeout(syncFilterStates, 0); }

  document.getElementById('dim-reset').addEventListener('click', function() {
    document.querySelectorAll('.filter-dim-row').forEach(function(row) {
      row.querySelector('.dim-val').value = '';
      row.querySelector('.dim-op').value = 'eq';
    });
    applyFilters();
  });

  document.getElementById('dim-fill-zeros').addEventListener('click', function() {
    var vals = dimVals();
    var allFilled = vals.every(dimResolved), hasZero = vals.indexOf('0') !== -1;
    if (allFilled && hasZero) {
      dimValInputs().forEach(function(input) {
        if (String(evalDimExpr(input.value)) === '0') input.value = '';
      });
    } else {
      document.querySelectorAll('.filter-dim-row').forEach(function(row) {
        var input = row.querySelector('.dim-val');
        if (!dimResolved(input.value)) input.value = '0';
      });
    }
    applyFilters();
  });

  document.getElementById('dim-mode-toggle').addEventListener('click', function() { toggleModeSwitched('dim'); });

  document.getElementById('dim-base-qty').addEventListener('click', function() {
    var url = new URL(window.location);
    if (url.searchParams.get('is_dim') === '1') {
      url.searchParams.delete('is_dim');
    } else {
      url.searchParams.set('is_dim', '1');
    }
    fetchContent(url.pathname + url.search, true);
  });

  function getSwitched(url) {
    return (url.searchParams.get('mode_switched') || '').split(',').filter(Boolean);
  }

  function toggleModeSwitched(key) {
    var url = new URL(window.location);
    var switched = getSwitched(url);
    var idx = switched.indexOf(key);
    if (idx !== -1) switched.splice(idx, 1);
    else switched.push(key);
    if (switched.length) url.searchParams.set('mode_switched', switched.join(','));
    else url.searchParams.delete('mode_switched');
    fetchContent(url.pathname + url.search, true);
  }

  function setModeBtn(btn, active, title) {
    btn.classList.toggle('active', active);
    btn.title = title;
    btn.innerHTML = '<i data-lucide="' + (active ? 'squares-unite' : 'squares-intersect') + '" width="16" height="16"></i>';
    refreshIcons();
  }

  function syncFilterStates() {
    var url = new URL(window.location);

    cleanModeSwitched(url);

    var vals = dimVals();

    var modeBtn = document.getElementById('dim-mode-toggle');
    if (modeBtn) {
      if (vals.filter(dimResolved).length >= 2) {
        modeBtn.classList.remove('hidden');
        var isOr = getSwitched(url).indexOf('dim') !== -1;
        setModeBtn(modeBtn, isOr, isOr ? window._localeUI.filter.dim_mode_or : window._localeUI.filter.dim_mode_and);
      } else {
        modeBtn.classList.add('hidden');
      }
    }

    var baseQtyBtn = document.getElementById('dim-base-qty');
    if (baseQtyBtn) {
      baseQtyBtn.classList.toggle('active', url.searchParams.get('is_dim') === '1');
      baseQtyBtn.classList.toggle('disabled', isFormulasView());
    }

    var fillBtn = document.getElementById('dim-fill-zeros');
    if (fillBtn) {
      var allFilled = vals.every(dimResolved), hasZero = vals.indexOf('0') !== -1;
      fillBtn.classList.toggle('active', allFilled && hasZero);
      fillBtn.classList.toggle('disabled', allFilled && !hasZero);
    }

    var dimReset = document.getElementById('dim-reset');
    if (dimReset) dimReset.classList.toggle('disabled', !vals.some(dimResolved));

    var deselectBtn = document.getElementById('tree-deselect-all');
    if (deselectBtn && _topicTree && _topicTreeMode === 'checkbox') {
      deselectBtn.classList.toggle('disabled', topCheckedIds().length === 0);
    }

    var treeSelectAll = document.getElementById('tree-select-all');
    if (treeSelectAll && _topicTree && _topicTreeMode === 'checkbox') {
      treeSelectAll.classList.toggle('disabled', allRootNodesChecked());
    }

    var qtyModeBtn = document.getElementById('qty-mode-toggle');
    if (qtyModeBtn) {
      if (!isFormulasView()) {
        qtyModeBtn.classList.add('hidden');
      } else if ((window._qtySelected || []).length >= 2) {
        qtyModeBtn.classList.remove('hidden');
        var isSwitched = getSwitched(url).indexOf('fml') !== -1;
        setModeBtn(qtyModeBtn, isSwitched, isSwitched ? window._localeUI.filter.qty_mode_or : window._localeUI.filter.qty_mode_and);
      } else {
        qtyModeBtn.classList.add('hidden');
      }
    }

    var qtyReset = document.getElementById('qty-reset');
    if (qtyReset) {
      qtyReset.classList.toggle('disabled', !window._qtySelected || window._qtySelected.length === 0);
    }

    var diffReset = document.getElementById('diff-reset');
    if (diffReset) {
      var dMin = document.getElementById('diff-min');
      var dMax = document.getElementById('diff-max');
      var isDefault = dMin && dMax && parseInt(dMin.value) === 1 && parseInt(dMax.value) === 10;
      diffReset.classList.toggle('disabled', isDefault);
    }

    var sortMenu = document.getElementById('sort-menu');
    var allowed = window._availableSorts || [];
    var defaultSort = window._defaultSort || null;
    if (sortMenu && allowed.length) {
      var wantValue = url.searchParams.get('sort');
      if (wantValue === null || allowed.indexOf(wantValue) === -1) {
        wantValue = defaultSort;
      }
      window._renderSortMenu(sortMenu, wantValue);
    }
  }

  function cleanModeSwitched(url) {
    var raw = url.searchParams.get('mode_switched');
    if (!raw) return;
    var parts = raw.split(',').filter(Boolean);
    var changed = false;

    var dimCount = window._dimensionSymbols.filter(function(d) {
      return ['eq', 'geq', 'leq'].some(function(op) { return url.searchParams.get(d + '_' + op) !== null; });
    }).length;
    if (dimCount < 2) { var idx = parts.indexOf('dim'); if (idx !== -1) { parts.splice(idx, 1); changed = true; } }

    var qtyParam = url.searchParams.get('qty');
    var qtyCount = qtyParam ? qtyParam.split(',').length : 0;
    if (qtyCount < 2) { var qidx = parts.indexOf('fml'); if (qidx !== -1) { parts.splice(qidx, 1); changed = true; } }

    if (changed) {
      if (parts.length) url.searchParams.set('mode_switched', parts.join(','));
      else url.searchParams.delete('mode_switched');
      history.replaceState(null, '', url.toString());
    }
  }

  function syncViewTabLinks() {
    document.querySelectorAll('.view-tab').forEach(function(t) {
      var href = t.getAttribute('href');
      if (!href) return;
      var base = href.split('?')[0];
      var qs = window.location.search;
      t.setAttribute('href', base + qs);
    });
  }

  /* The sort dropdown applies to the formula/quantities/search lists */
  function syncSortVisibility() {
    var wrap = document.getElementById('sort-wrap');
    if (wrap) wrap.classList.remove('hidden');
  }

  function isFormulasView() {
    var p = window.location.pathname;
    return p.indexOf('/quantities') === -1 && p.indexOf('/quantity/') === -1 && p.indexOf('/unit/') === -1;
  }

  document.getElementById('qty-mode-toggle').addEventListener('click', function() {
    if (!isFormulasView()) return;
    toggleModeSwitched('fml');
  });

  document.getElementById('qty-reset').addEventListener('click', function() {
    window._qtySelected = [];
    var input = document.getElementById('qty-search');
    if (input) input.value = '';
    if (typeof window.renderQtyChips === 'function') window.renderQtyChips();
    if (typeof window.renderQtyResults === 'function') window.renderQtyResults('');
    applyFilters();
  });

  document.getElementById('diff-reset').addEventListener('click', function() {
    document.getElementById('diff-min').value = 1;
    document.getElementById('diff-max').value = 10;
    syncDiff();
    applyFilters();
  });

  (function() {
    var allQuantities = window._allQuantities || [];
    window._qtySelected = [];

    window._renderLatex = function(text) {
      if (typeof katex === 'undefined') return escapeHtml(text);
      try { return katex.renderToString(text, {displayMode: false, throwOnError: false}); }
      catch(e) { return escapeHtml(text); }
    };

    /* Restarts the .label-in animation on an element */
    window._bumpLabel = function(el) { replayClass(el, 'label-in'); };

    window._renderSortMenu = function(sortMenu, value) {
      var allowed = window._availableSorts || [];
      var labels = (window._localeUI && window._localeUI.sort) || {};
      sortMenu.dataset.value = value || '';
      /* Selected value lives in the trigger, not repeated as a row */
      sortMenu.innerHTML = allowed.filter(function(key) { return key !== value; }).map(function(key) {
        return '<button type="button" class="sort-option"' +
          ' role="option" aria-selected="false"' +
          ' data-action="sort-pick" data-sort="' + key + '">' +
          '<span>' + (labels[key] || key) + '</span>' +
          '</button>';
      }).join('');
      var labelEl = document.getElementById('sort-trigger-label');
      if (labelEl) labelEl.textContent = labels[value] || value || '';
      refreshIcons();
    };

    /* Morphing select controller: opening morphs the trigger into the
       head of the list (see CSS); the selected value stays in the
       trigger instead of repeating as a row. */
    window._morphSelects = [];

    window._morphSelect = function(trigger, menu) {
      for (var i = 0; i < window._morphSelects.length; i++) {
        if (window._morphSelects[i].menu === menu) return window._morphSelects[i];
      }
      var ctrl = {
        trigger: trigger,
        menu: menu,
        sync: function() {},
        isOpen: function() { return menu.classList.contains('open'); },
        open: function() {
          window._morphSelects.forEach(function(other) {
            if (other !== ctrl && other.isOpen()) other.close();
          });
          menu.classList.remove('closing');
          this.sync();
          menu.classList.add('open');
          trigger.classList.add('open');
          trigger.setAttribute('aria-expanded', 'true');
        },
        close: function() {
          if (!this.isOpen()) return;
          menu.classList.remove('open');
          trigger.classList.remove('open');
          trigger.setAttribute('aria-expanded', 'false');
          replayClass(menu, 'closing');
        },
        toggle: function() {
          if (this.isOpen()) this.close();
          else this.open();
        }
      };
      window._morphSelects.push(ctrl);
      menu._morphCtrl = ctrl;
      return ctrl;
    };

    document.addEventListener('keydown', function(e) {
      if (e.key !== 'Escape') return;
      window._morphSelects.forEach(function(ctrl) {
        if (ctrl.isOpen()) {
          ctrl.close();
          ctrl.trigger.focus();
        }
      });
    });

    /* Wraps a native <select> in a custom dropdown; the hidden native
       element stays the source of truth and dispatches 'change', so
       existing handlers keep working untouched. */
    function initCSelect(select) {
      if (!select || select.dataset.cselectBound || !select.options.length) return;
      select.dataset.cselectBound = '1';
      var compact = select.classList.contains('dim-op');
      /* Operator picks get no chevron */
      var wrap = document.createElement('div');
      wrap.className = 'cselect';
      wrap.innerHTML =
        '<button type="button" class="sort-trigger cselect-trigger' + (compact ? ' compact' : '') + '"' +
        ' aria-haspopup="listbox" aria-expanded="false"><span class="cselect-label"></span>' +
        (compact ? '' : '<i data-lucide="chevron-down" width="14" height="14"></i>') + '</button>' +
        '<div class="dropdown-menu sort-menu cselect-menu' + (compact ? ' compact' : '') + '" role="listbox"></div>';
      var trigger = wrap.children[0];
      var label = trigger.children[0];
      var menu = wrap.children[1];
      select.parentNode.insertBefore(wrap, select);
      select.style.display = 'none';

      var ctrl = window._morphSelect(trigger, menu);
      /* Re-sync rows from native state before showing */
      ctrl.sync = render;

      function render() {
        menu.innerHTML = '';
        var sel = select.selectedIndex;
        for (var i = 0; i < select.options.length; i++) {
          if (i === sel) continue; /* shown in the trigger, not the list */
          var o = select.options[i];
          var b = document.createElement('button');
          b.type = 'button';
          b.className = 'sort-option';
          b.setAttribute('role', 'option');
          b.setAttribute('aria-selected', 'false');
          b.setAttribute('data-cselect-index', i);
          var sp = document.createElement('span');
          sp.textContent = o.textContent.trim();
          b.appendChild(sp);
          menu.appendChild(b);
        }
        label.textContent = select.options[sel] ? select.options[sel].textContent.trim() : '';
      }

      function commit(idx) {
        if (idx === select.selectedIndex) { ctrl.close(); return; }
        select.selectedIndex = idx;
        ctrl.close();
        render();
        window._bumpLabel(label);
        select.dispatchEvent(new Event('change', { bubbles: true }));
      }

      trigger.addEventListener('click', function(e) {
        e.stopPropagation();
        e.preventDefault();
        ctrl.toggle();
      });

      menu.addEventListener('click', function(e) {
        var btn = e.target.closest('.sort-option');
        if (!btn || !menu.contains(btn)) return;
        e.stopPropagation();
        commit(parseInt(btn.getAttribute('data-cselect-index'), 10));
      });

      render();
      refreshIcons();
    }

    window.initCSelects = function(root) {
      var scope = root || document;
      scope.querySelectorAll('.settings-item select, .filter-dim-row select.dim-op').forEach(initCSelect);
    };

    window.renderQtyChips = function() {
      var chipsEl = document.getElementById('qty-chips');
      if (!chipsEl) return;
      chipsEl.innerHTML = window._qtySelected.map(function(qid) {
        var q = allQuantities.find(function(x) { return x.id === qid; });
        var label = q ? (q.symbol || q.name || q.id) : qid;
        return '<span class="qty-chip" data-qty="' + escapeHtml(qid) + '">' + window._renderLatex(label) + '<span class="qty-chip-x" data-action="remove-qty-chip" data-qty="' + escapeHtml(qid) + '"><i data-lucide="x" width="12" height="12"></i></span></span>';
      }).join('');
      refreshIcons();
    };

    window.renderQtyResults = function(query) {
      var resultsEl = document.getElementById('qty-results');
      if (!resultsEl) return;
      var q = (query || '').toLowerCase().trim();
      var matches = allQuantities.filter(function(item) {
        if (!q) return true;
        return ['name', 'symbol', 'id'].some(function(k) {
          return String(item[k] || '').toLowerCase().indexOf(q) !== -1;
        });
      });
      if (matches.length === 0) {
        resultsEl.classList.remove('open');
        resultsEl.innerHTML = '';
        return;
      }
      resultsEl.classList.add('open');
      var html = '';
      matches.slice(0, 30).forEach(function(item) {
        var isSel = window._qtySelected.indexOf(item.id) !== -1;
        var symRaw = item.symbol || '';
        var nameRaw = item.name || item.id;
        var symDisplay = symRaw ? window._renderLatex(symRaw) : '';
        html += '<div class="qty-result' + (isSel ? ' selected' : '') + '" data-action="add-qty-chip" data-qty="' + escapeHtml(item.id) + '" tabindex="0">';
        html += '<span class="qty-result-sym">' + symDisplay + '</span>';
        html += '<span class="qty-result-name">' + escapeHtml(nameRaw) + '</span>';
        html += '</div>';
      });
      resultsEl.innerHTML = html;
    };

    window.addQtyChip = function(qid) {
      if (window._qtySelected.indexOf(qid) !== -1) return;
      window._qtySelected.push(qid);
      window.renderQtyChips();
      var input = document.getElementById('qty-search');
      if (input) input.value = '';
      window.renderQtyResults('');
      dimFilterChange();
    };

    window.removeQtyChip = function(qid) {
      window._qtySelected = window._qtySelected.filter(function(x) { return x !== qid; });
      window.renderQtyChips();
      var input = document.getElementById('qty-search');
      var query = input ? input.value : '';
      window.renderQtyResults(query);
      dimFilterChange();
    };

    function resetQtySearch() {
      var el = document.getElementById('qty-results');
      if (el) el.classList.remove('open');
      var inp = document.getElementById('qty-search');
      if (inp) inp._userInteracted = false;
    }
    window.addEventListener('pageshow', resetQtySearch);
    resetQtySearch();
    var qtyInput = document.getElementById('qty-search');
    if (qtyInput) {
      qtyInput.addEventListener('input', function() {
        window.renderQtyResults(qtyInput.value);
      });
      qtyInput.addEventListener('focus', function() {
        if (qtyInput.value.trim() || qtyInput._userInteracted) {
          window.renderQtyResults(qtyInput.value);
        }
      });
      qtyInput.addEventListener('click', function() {
        qtyInput._userInteracted = true;
        window.renderQtyResults(qtyInput.value);
      });
      qtyInput.addEventListener('blur', function() {
        setTimeout(function() {
          var active = document.activeElement;
          if (active && active.classList && active.classList.contains('qty-result')) return;
          var el = document.getElementById('qty-results');
          if (el) el.classList.remove('open');
        }, 200);
      });
    }
    document.addEventListener('keydown', function(e) {
      var el = document.getElementById('qty-results');
      if (!el || !el.classList.contains('open')) return;
      var items = el.querySelectorAll('.qty-result');
      if (items.length === 0) return;
      if (!qtyInput || (!qtyInput.contains(document.activeElement) && !el.contains(document.activeElement))) return;
      var idx = Array.prototype.indexOf.call(items, document.activeElement);
      if (idx < 0 && document.activeElement === qtyInput) idx = -1;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (idx < items.length - 1) items[idx + 1].focus();
        else items[0].focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (idx > 0) items[idx - 1].focus();
        else if (idx === 0) { if (qtyInput) qtyInput.focus(); }
        else items[items.length - 1].focus();
      } else if (e.key === 'Enter' && idx >= 0) {
        e.preventDefault();
        items[idx].click();
      }
    });
    document.addEventListener('click', function(e) {
      var wrap = document.querySelector('.filter-qty-search-wrap');
      if (wrap && !wrap.contains(e.target)) {
        var el = document.getElementById('qty-results');
        if (el) el.classList.remove('open');
      }
    });
  })();

  function applyFilters() {
    if (window._restoringFilters) return;
    var url = buildFilterUrl();
    fetchContent(url, true);
  }

  function buildFilterUrl() {
    var allIds = [];
    var allRootSelected = false;
    if (_topicTree && _topicTreeMode === 'checkbox') {
      allIds = topCheckedIds();
      allRootSelected = allRootNodesChecked();
    }

    var url = new URL(window.location);
    url.searchParams.delete('subbranch');
    url.searchParams.delete('topic');
    url.searchParams.delete('id');
    url.searchParams.delete('exclude_all');
    /* `q` belongs to /search; never let a stray value leak into the
       filters of other pages (e.g. after cancelling a search). */
    if (url.pathname !== '/search') url.searchParams.delete('q');

    if (allRootSelected) {
      url.searchParams.delete('ids');
    } else if (allIds.length === 0) {
      url.searchParams.set('ids', '');
    } else {
      url.searchParams.set('ids', allIds.join(','));
    }

    var min = Math.round(parseFloat(document.getElementById('diff-min').value));
    var max = Math.round(parseFloat(document.getElementById('diff-max').value));
    if (min > 1) url.searchParams.set('diff_min', min);
    else url.searchParams.delete('diff_min');
    if (max < 10) url.searchParams.set('diff_max', max);
    else url.searchParams.delete('diff_max');

    window._dimensionSymbols.forEach(function(d) {
      var rows = document.querySelectorAll('.filter-dim-row[data-dim="' + d + '"]');
      if (rows.length === 0) return;
      var row = rows[0];
      ['_o','_v','_eq','_geq','_leq'].forEach(function(s) { url.searchParams.delete(d + s); });
      var op = row.querySelector('.dim-op').value;
      var parsed = evalDimExpr(row.querySelector('.dim-val').value);
      if (parsed !== null) url.searchParams.set(d + '_' + op, parsed);
    });

    var qtySelected = window._qtySelected || [];
    if (qtySelected.length > 0) url.searchParams.set('qty', qtySelected.join(','));
    else url.searchParams.delete('qty');

    var sortMenu = document.getElementById('sort-menu');
    var sortAllowed = window._availableSorts || [];
    var sortVal = sortMenu && sortAllowed.length ? (sortMenu.dataset.value || '') : '';
    if (!sortVal || sortAllowed.indexOf(sortVal) === -1 || sortVal === (window._defaultSort || null)) {
      url.searchParams.delete('sort');
    } else {
      url.searchParams.set('sort', sortVal);
    }

    var path = url.pathname;
    if (path !== '/formulas' && path !== '/quantities' && path !== '/search') {
      url.pathname = '/formulas';
    }
    return url.pathname + url.search;
  }

  var _pendingFetch = null;

  function fetchContent(url, pushState) {
    if (_pendingFetch) _pendingFetch.abort();
    var controller = new AbortController();
    var opts = { signal: controller.signal };
    _pendingFetch = controller;
    fetch(url, opts)
      .then(function(r) { return r.text(); })
      .then(function(html) {
        var parser = new DOMParser();
        var doc = parser.parseFromString(html, 'text/html');
        var newContent = doc.querySelector('#main-content .main-inner');
        if (newContent) {
          document.querySelector('#main-content .main-inner').innerHTML = newContent.innerHTML;
          document.getElementById('main-content').scrollTop = 0;
        }
        if (pushState) {
          history.pushState({url: url}, '', url);
        }
        renderMathInContent();
        restoreAllFromUrl();
        updateOverflowPadding();
        updateDimNameFits();
        syncDockPills();
        syncViewTabLinks();
        syncSortVisibility();
      })
      .catch(function(err) { if (err.name !== 'AbortError') console.warn('fetchContent error', err); })
      .then(function() { if (_pendingFetch === controller) _pendingFetch = null; });
  }
  window.fetchContent = fetchContent;

  function currentBreakpoint() {
    var w = window.innerWidth;
    if (w >= 1024) return 'pc';
    if (w >= 768) return 'tablet';
    return 'mobile';
  }

  function isSidebarOpen(side) {
    var el = document.getElementById('sidebar-' + side);
    return !el || el.getAttribute('data-open') !== '0'; // default open if element missing
  }
  function setSidebarState(side, open) {
    var el = document.getElementById('sidebar-' + side);
    if (!el) return;
    el.setAttribute('data-open', open ? '1' : '0');
    var bp = currentBreakpoint();
    el.classList.toggle('collapsed', bp === 'pc' && !open);
    el.classList.toggle('open', bp !== 'pc' && open);
  }

  function syncAfterSidebarToggle(side) {
    syncBackdrop();
    syncSidebarIcon(side);
    syncDockPills();
  }

  function openSidebar(side) {
    var el = document.getElementById('sidebar-' + side);
    if (!el) return;
    if (currentBreakpoint() === 'mobile') {
      var other = side === 'left' ? 'right' : 'left';
      if (isSidebarOpen(other)) closeSidebar(other);
    }
    exitSearch();
    setSidebarState(side, true);
    syncAfterSidebarToggle(side);
  }

  function closeSidebar(side) {
    var el = document.getElementById('sidebar-' + side);
    if (!el) return;
    setSidebarState(side, false);
    syncAfterSidebarToggle(side);
  }

  function toggleSidebar(side) {
    if (isSidebarOpen(side)) closeSidebar(side);
    else openSidebar(side);
  }
  window.toggleSidebar = toggleSidebar;

  function syncBackdrop() {
    var bp = document.getElementById('sidebar-backdrop');
    if (!bp) return;
    var anyOpen = isSidebarOpen('left') || isSidebarOpen('right');
    var layoutBp = currentBreakpoint();
    if (layoutBp === 'tablet') anyOpen = isSidebarOpen('right');
    bp.classList.toggle('open', anyOpen && layoutBp !== 'pc');
  }

  function syncSidebarIcon(side) {
    var el = document.getElementById('sidebar-' + side);
    var iconWrap = document.getElementById(side + '-sidebar-icon');
    if (!el || !iconWrap) return;
    var bp = currentBreakpoint();
    var closed = isSidebarOpen(side) ? false : (bp !== 'tablet' || side === 'right');
    var icons = {
      left: closed ? 'panel-left-open' : 'panel-left-close',
      right: closed ? 'panel-right-open' : 'panel-right-close'
    };
    iconWrap.innerHTML = '<i data-lucide="' + icons[side] + '" width="18" height="18"></i>';
    refreshIcons();
  }

  function hasActiveFilters() {
    var diffMin = parseInt(document.getElementById('diff-min').value);
    var diffMax = parseInt(document.getElementById('diff-max').value);
    return dimVals().some(dimResolved) ||
      (window._qtySelected && window._qtySelected.length > 0) ||
      diffMin > 1 || diffMax < 10;
  }
  window.hasActiveFilters = hasActiveFilters;

  function hasTreeFilter() {
    return !!(_topicTree && _topicTreeMode === 'checkbox' && !allRootNodesChecked());
  }

  function syncDockPills() {
    var dock = document.getElementById('mobile-dock');
    if (!dock) return;
    var view = isFormulasView() ? 'formulas' : 'quantities';
    var onCreate = window.location.pathname === '/create';
    dock.querySelectorAll('[data-dock-view]').forEach(function(btn) {
      btn.classList.toggle('active', !onCreate && btn.getAttribute('data-dock-view') === view);
      btn.classList.remove('open');
    });
    dock.querySelectorAll('[data-pill="filter"]').forEach(function(btn) {
      btn.classList.toggle('open', isSidebarOpen('left'));
      btn.classList.toggle('active', hasActiveFilters());
    });
    dock.querySelectorAll('[data-pill="tree"]').forEach(function(btn) {
      btn.classList.toggle('open', isSidebarOpen('right'));
      btn.classList.toggle('active', hasTreeFilter());
    });
    dock.querySelectorAll('[data-pill="search"]').forEach(function(btn) {
      var topbar = document.querySelector('.topbar');
      btn.classList.toggle('open', topbar && topbar.classList.contains('expand-search'));
      var url = new URL(window.location);
      btn.classList.toggle('active', url.searchParams.has('q'));
    });
  }

  function dockSetView(view) {
    var url = new URL(window.location);
    var base = view === 'quantities' ? '/quantities' : '/formulas';
    var qs = url.searchParams.toString();
    var target = base + (qs ? '?' + qs : '');
    if (typeof window._navigateTo === 'function') {
      window._navigateTo(target);
    } else {
      window.location.href = target;
    }
  }

  function dockToggleSearch() {
    var topbar = document.querySelector('.topbar');
    if (topbar.classList.contains('expand-search')) {
      exitSearch();
    } else {
      enterSearch();
    }
  }

  (function() {
    var timer = null;
    var pressedEl = null;
    var LONG_PRESS_MS = 500;

    document.addEventListener('pointerdown', function(e) {
      var pill = e.target.closest('[data-pill]');
      if (!pill) return;
      pressedEl = pill;
      timer = setTimeout(function() {
        if (!pressedEl) return;
        pressedEl._longPressed = true;
        switch (pressedEl.getAttribute('data-pill')) {
          case 'filter':
            document.getElementById('dim-reset').click();
            document.getElementById('qty-reset').click();
            document.getElementById('diff-reset').click();
            break;
          case 'tree':
            document.getElementById('tree-select-all').click();
            break;
          case 'search':
            var url = new URL(window.location);
            url.searchParams.delete('q');
            var target = (isFormulasView() ? '/formulas' : '/quantities') + url.search;
            fetchContent(target, true);
            exitSearch();
            break;
        }
      }, LONG_PRESS_MS);
    });

    function endPress(cancelled) {
      if (timer) { clearTimeout(timer); timer = null; }
      if (cancelled && pressedEl) pressedEl._longPressed = false;
      pressedEl = null;
    }
    document.addEventListener('pointerup', function() { endPress(false); });
    document.addEventListener('pointercancel', function() { endPress(true); });

    document.addEventListener('click', function(e) {
      var pill = e.target.closest('[data-pill]');
      if (pill && pill._longPressed) {
        pill._longPressed = false;
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
      }
    }, true);
  })();

  function enterSearch() {
    closeSidebar('left');
    closeSidebar('right');
    var topbar = document.querySelector('.topbar');
    topbar.classList.add('expand-search');
    var input = topbar.querySelector('.topbar-search input');
    if (input) input.focus();
    syncDockPills();
  }
  function exitSearch(focusAfter) {
    var topbar = document.querySelector('.topbar');
    topbar.classList.remove('expand-search');
    var input = topbar.querySelector('.topbar-search input');
    if (input) { input.value = ''; input.blur(); }
    if (typeof window.syncSearchCancel === 'function') window.syncSearchCancel();
    syncDockPills();
    if (focusAfter && input) input.focus();
  }

  function toggleSettings(e) {
    e.stopPropagation();
    document.getElementById('settings-menu').classList.toggle('open');
  }

  /* Clicking a control inside the settings menu must not leave it
     focused (Chromium focuses buttons on mousedown, so e.g. clicking
     "Report" then pressing Space would re-open the GitHub tab). */
  (function() {
    var menu = document.getElementById('settings-menu');
    if (!menu) return;
    menu.addEventListener('mousedown', function(e) {
      if (e.target.closest('button, a, input, select')) e.preventDefault();
    });
  })();

  function toggleSortMenu(e) {
    e.stopPropagation();
    var menu = document.getElementById('sort-menu');
    if (menu && menu._morphCtrl) menu._morphCtrl.toggle();
  }

  /* Icon animations: .icon-play added on press, removed on animationend
     so the effect completes even on early release. */
  var ICON_ANIM_SELECTOR = '#dim-reset, #qty-reset, #diff-reset, #tree-select-all, #tree-deselect-all, #dim-fill-zeros, #dim-base-qty, [data-action="toggle-settings"], .formula-copy-btn';
  document.addEventListener('pointerdown', function(e) {
    var btn = e.target.closest(ICON_ANIM_SELECTOR);
    if (btn) replayClass(btn, 'icon-play');
  });
  document.addEventListener('animationend', function(e) {
    if (!e.animationName) return;
    if (e.animationName === 'menu-out') { e.target.classList.remove('closing'); return; }
    if (e.animationName.indexOf('icon-') !== 0) return;
    var btn = e.target.closest ? e.target.closest('.icon-play') : null;
    if (btn) btn.classList.remove('icon-play');
  });

  function pickSort(key) {
    var sortMenu = document.getElementById('sort-menu');
    if (!sortMenu || !sortMenu._morphCtrl) {
      if (sortMenu) sortMenu.classList.remove('open');
      applyFilters();
      return;
    }
    var ctrl = sortMenu._morphCtrl;
    if (sortMenu.dataset.value === key) { ctrl.close(); return; }
    sortMenu.dataset.value = key;
    ctrl.close();
    window._renderSortMenu(sortMenu, key);
    var labelEl = document.getElementById('sort-trigger-label');
    if (labelEl) window._bumpLabel(labelEl);
    applyFilters();
  }

  document.addEventListener('click', function(e) {
    var settingsWrap = document.querySelector('.settings-wrap');
    if (settingsWrap && !settingsWrap.contains(e.target)) {
      document.getElementById('settings-menu').classList.remove('open');
    }
    window._morphSelects.forEach(function(ctrl) {
      if (!ctrl.trigger.contains(e.target) && !ctrl.menu.contains(e.target)) ctrl.close();
    });
    var copyMenu = document.getElementById('formula-copy-menu');
    if (copyMenu && !e.target.closest('.formula-box *') && e.target !== copyMenu && !copyMenu.contains(e.target)) {
      copyMenu.classList.remove('open');
    }

    var el = e.target.closest('[data-action]');
    if (!el) return;
    switch (el.getAttribute('data-action')) {
      case 'toggle-sidebar-left': toggleSidebar('left'); break;
      case 'toggle-sidebar-right': toggleSidebar('right'); break;
      case 'exit-search':
        /* The X button clears the input and re-focuses it so the user
           can immediately retype; also strip q from the URL since the
           field is empty and q only belongs to /search. */
        var path = window.location.pathname;
        var search = window.location.search;
        if (path === '/search' && /[?&]q=/.test(search)) {
          var url = new URL(window.location);
          url.searchParams.delete('q');
          if (typeof window._navigateTo === 'function') {
            window._navigateTo(url.pathname + (url.searchParams.toString() ? '?' + url.searchParams.toString() : ''));
          } else {
            window.location.href = url.pathname + (url.searchParams.toString() ? '?' + url.searchParams.toString() : '');
          }
        } else if (path !== '/search' && /[?&]q=/.test(search)) {
          var url2 = new URL(window.location);
          url2.searchParams.delete('q');
          history.replaceState({url: url2.pathname + url2.search}, '', url2.pathname + url2.search);
        }
        exitSearch(true);
        break;
      case 'dock-toggle-search': dockToggleSearch(); break;
      case 'toggle-settings': toggleSettings(e); break;
      case 'toggle-sort-menu': toggleSortMenu(e); break;
      case 'sort-pick': pickSort(el.getAttribute('data-sort')); break;
      case 'toggle-copy-menu': toggleCopyMenu(e); break;
      case 'copy-formula-latex': copyFormula('latex'); break;
      case 'copy-formula-unicode': copyFormula('unicode'); break;
      case 'copy-formula-image-png': copyFormula('png'); break;
      case 'copy-formula-image-svg': copyFormula('svg'); break;
      case 'remove-qty-chip': removeQtyChip(el.getAttribute('data-qty')); break;
      case 'add-qty-chip': addQtyChip(el.getAttribute('data-qty')); break;
      case 'close-overlays': closeSidebar('left'); closeSidebar('right'); break;
      case 'dock-set-view': dockSetView(el.getAttribute('data-dock-view')); break;
      case 'dock-toggle-panel': toggleSidebar(el.getAttribute('data-target')); break;
      case 'open-bug-report': window.open('https://github.com/Creeperman3000/Scifind/issues/new', '_blank'); break;
    }
  });
  document.addEventListener('change', function(e) {
    var el = e.target.closest('[data-action]');
    if (!el) return;
    switch (el.getAttribute('data-action')) {
      case 'switch-theme': switchTheme(el.value); break;
      case 'switch-lang': switchLang(el.value); break;
      case 'switch-dim-mode': switchDimMode(el.value); break;
      case 'dim-filter-change':
        if (el.classList.contains('dim-val')) resolveDimExprs();
        dimFilterChange();
        break;
      case 'set-export-format': setCookie('sf_export_format', el.value); break;
    }
  });
  document.addEventListener('input', function(e) {
    var el = e.target.closest('[data-action]');
    if (!el) return;
    switch (el.getAttribute('data-action')) {
      /* dim value fields apply only on change (Enter/unfocus) — no
         live evaluation while typing */
      case 'dim-filter-change':
        if (!el.classList.contains('dim-val')) dimFilterChange();
        break;
      case 'sync-diff': syncDiff(); break;
    }
  });

  function prefersDark() { return window.matchMedia('(prefers-color-scheme: dark)').matches; }
  function applyTheme(dark) { document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light'); }

  function switchTheme(theme) {
    if (theme === 'dark' || theme === 'light') {
      localStorage.setItem('sf-theme', theme);
      applyTheme(theme === 'dark');
    } else {
      localStorage.removeItem('sf-theme');
      document.documentElement.removeAttribute('data-theme');
      applyTheme(prefersDark());
    }
  }

  (function() {
    var t = localStorage.getItem('sf-theme');
    if (t) {
      switchTheme(t);
      document.getElementById('setting-theme').value = t;
    } else {
      if (prefersDark()) applyTheme(true);
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
        if (!localStorage.getItem('sf-theme')) applyTheme(e.matches);
      });
    }
  })();

  function switchLang(locale) {
    setCookie('sf_locale', locale);
    window.location.reload();
  }

  function switchDimMode(mode) {
    setCookie('sf_dim_mode', mode);
    window.location.reload();
  }

  function syncDiff() {
    var min = document.getElementById('diff-min');
    var max = document.getElementById('diff-max');
    var fill = document.getElementById('diff-fill');
    /* No step on the inputs → they move smoothly under the mouse. Round
       only when applying the filter (server expects ints). */
    var raw1 = parseFloat(min.value), raw2 = parseFloat(max.value);
    if (raw1 > raw2) { var tmp = raw1; raw1 = raw2; raw2 = tmp; min.value = raw1; max.value = raw2; }
    var v1 = Math.round(raw1), v2 = Math.round(raw2);
    document.getElementById('diff-min-val').textContent = v1;
    document.getElementById('diff-max-val').textContent = v2;
    var p1 = (raw1 - 1) / 9, p2 = (raw2 - 1) / 9;
    /* Fill edges sit on the thumb centers, whose travel stops half a
       thumb short of each end of the track. */
    var travel = '(100% - var(--thumb-size))';
    fill.style.left = 'calc(' + travel + ' * ' + p1 + ' + var(--thumb-size) / 2)';
    fill.style.width = 'calc(' + travel + ' * ' + (p2 - p1) + ')';
  }
  window.syncDiff = syncDiff;
  syncDiff();

  document.getElementById('diff-min').addEventListener('change', applyFilters);
  document.getElementById('diff-max').addEventListener('change', applyFilters);

  /* Native click-to-position only works when the click hits an input.
     Both inputs have pointer-events:none so the visible track catches
     the click; we then dispatch the click onto the nearer thumb. The
     native browser behavior would otherwise route everything to the
     topmost input (diff-max). */
  (function() {
    var wrap = document.querySelector('.diff-sliders');
    if (!wrap) return;
    wrap.addEventListener('pointerdown', function(e) {
      if (e.button !== 0) return;
      var rect = wrap.getBoundingClientRect();
      var x = e.clientX - rect.left;
      var min = document.getElementById('diff-min');
      var max = document.getElementById('diff-max');
      /* Thumb centers travel across [size/2, width - size/2]; mapping
         clicks through that same space keeps the same spot of the knob
         under the cursor for the whole drag. */
      var range = 9;
      var thumb = parseFloat(getComputedStyle(wrap).getPropertyValue('--thumb-size')) || 20;
      function toValue(px) {
        var usable = Math.max(rect.width - thumb, 1);
        var t = Math.max(0, Math.min(usable, px - thumb / 2)) / usable;
        return 1 + t * range;
      }
      var value = toValue(x);
      var distMin = Math.abs(value - parseFloat(min.value));
      var distMax = Math.abs(value - parseFloat(max.value));
      var target = distMin <= distMax ? min : max;
      target.value = value;
      target.dispatchEvent(new Event('input', { bubbles: true }));
      target.focus();
      /* Forward subsequent pointermoves until pointerup to that input
         so the drag continues smoothly. */
      function onMove(ev) {
        var px = ev.clientX - rect.left;
        target.value = toValue(px);
        target.dispatchEvent(new Event('input', { bubbles: true }));
      }
      function onUp() {
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
        target.dispatchEvent(new Event('change', { bubbles: true }));
      }
      window.addEventListener('pointermove', onMove);
      window.addEventListener('pointerup', onUp);
      e.preventDefault();
    });
  })();

  (function() {
    var isResizing = false;
    var currentSide = null;
    var startX, startWidth;

    ['left', 'right'].forEach(function(side) {
      var handle = document.getElementById('sidebar-resize-' + side);
      if (!handle) return;
      var sidebar = document.getElementById('sidebar-' + side);

      handle.addEventListener('mousedown', function(e) {
        isResizing = true;
        currentSide = side;
        startX = e.clientX;
        startWidth = sidebar.getBoundingClientRect().width;
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
      });
      handle.addEventListener('dblclick', function() {
        sidebar.style.width = '';
        sidebar.style.transition = '';
        sidebar.querySelector('.sidebar-inner').style.width = '';
      });
    });

    document.addEventListener('mousemove', function(e) {
      if (!isResizing) return;
      var delta;
      if (currentSide === 'left') {
        delta = e.clientX - startX;
      } else {
        delta = startX - e.clientX;
      }
      var newWidth = Math.max(180, Math.min(500, startWidth + delta));
      var sidebar = document.getElementById('sidebar-' + currentSide);
      sidebar.style.width = newWidth + 'px';
      sidebar.style.transition = 'none';
      sidebar.querySelector('.sidebar-inner').style.width = newWidth + 'px';
    });

    document.addEventListener('mouseup', function() {
      if (isResizing) {
        isResizing = false;
        currentSide = null;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        document.querySelectorAll('.sidebar').forEach(function(s) {
          s.style.transition = '';
        });
        updateOverflowPadding();
        updateDimNameFits();
      }
    });
  })();

  (function() {
    var mqTabletUp = window.matchMedia('(min-width: 768px)');
    var mqPcUp = window.matchMedia('(min-width: 1024px)');
    var mqMobile = window.matchMedia('(width < 768px)');

    /* Only re-sync when the layout actually changed. The soft keyboard
       fires resize events with an unchanged width/breakpoint; re-running
       would force-close the open bottom sheets. */
    var lastBp = null, lastWidth = null;

    function syncOnResize() {
      var left = document.getElementById('sidebar-left');
      var right = document.getElementById('sidebar-right');
      if (!left || !right) return;

      var bp = currentBreakpoint();
      var w = window.innerWidth;
      if (bp === lastBp && w === lastWidth) return;
      lastBp = bp;
      lastWidth = w;

      document.documentElement.classList.add('suppress-transitions');

      setSidebarState('left', bp !== 'mobile');
      setSidebarState('right', bp === 'pc');

      syncBackdrop();
      syncSidebarIcon('left');
      syncSidebarIcon('right');
      syncDockPills();

      void document.documentElement.offsetWidth;
      document.documentElement.classList.remove('suppress-transitions');
    }

    [mqTabletUp, mqPcUp, mqMobile].forEach(function(m) {
      if (m.addEventListener) m.addEventListener('change', syncOnResize);
      else if (m.addListener) m.addListener(syncOnResize);
    });
    window.addEventListener('resize', syncOnResize);
    syncOnResize();
  })();

  (function() {
    var COMMIT_RATIO = 0.25;     // dragged past 25% of sheet height -> close
    var FLICK_VELOCITY = 0.5;    // px/ms downward -> close on a quick flick
    var FLICK_MIN_DISTANCE = 24; // ignore tap jitter before calling it a flick
    var RUBBER_BAND = 0.15;      // resistance when pulling past the resting position
    var ENGAGE_DISTANCE = 12;    // px of downward travel before a content grab turns into a drag
    var INTERACTIVE = 'button, a, input, select, textarea, label';
    var startY = 0, currentY = 0, lastY = 0, lastT = 0, velocity = 0;
    var dragging = false, target = null, engaged = false, activePointerId = null;

    function onDown(e) {
      if (dragging || (e.button !== undefined && e.button !== 0)) return;
      if (currentBreakpoint() !== 'mobile') return;
      var t = e.target;
      if (!t || !t.closest) return;
      var sheet = t.closest('.sidebar.left, .sidebar.right');
      if (!sheet || !sheet.classList.contains('open')) return;
      var onHandle = !!t.closest('.sheet-handle');
      /* Controls inside the sheet keep their taps; only the grip and
         plain content are drag surfaces */
      if (!onHandle && t.closest(INTERACTIVE)) return;
      /* Content grabs only become drags from the very top of the list;
         anywhere else the gesture belongs to native scrolling */
      var scrollArea = sheet.querySelector('.sidebar-scroll');
      if (!onHandle && (!scrollArea || scrollArea.scrollTop !== 0)) return;
      dragging = true;
      target = sheet;
      engaged = onHandle; // the grip follows the finger immediately
      activePointerId = e.pointerId;
      startY = currentY = lastY = e.clientY;
      lastT = e.timeStamp;
      velocity = 0;
      if (engaged) {
        sheet.style.transition = 'none';
        sheet.classList.add('dragging');
      }
    }
    function onMove(e) {
      if (!dragging || !target || e.pointerId !== activePointerId) return;
      var y = e.clientY;
      var dt = e.timeStamp - lastT;
      /* Smoothed instantaneous velocity, so one noisy sample can't
         trigger the flick threshold */
      if (dt > 0) velocity = 0.6 * ((y - lastY) / dt) + 0.4 * velocity;
      lastY = y;
      lastT = e.timeStamp;
      currentY = y;
      var dy = y - startY;
      if (!engaged) {
        if (dy > ENGAGE_DISTANCE) {
          engaged = true;
          target.style.transition = 'none';
          target.classList.add('dragging');
        } else {
          /* Moving up first means the user wants to scroll, not drag */
          if (dy < -ENGAGE_DISTANCE) { dragging = false; target = null; }
          return;
        }
      }
      /* Elastic resistance above the resting position instead of a hard stop */
      target.style.transform = 'translateY(' + (dy > 0 ? dy : dy * RUBBER_BAND) + 'px)';
    }
    function settle(sheet, toY) {
      /* Animate inline from the finger's position; clearing the inline
         transform instead would snap the sheet back to rest first */
      sheet.style.transition = 'transform var(--dur-base) var(--ease-in-out)';
      sheet.style.transform = 'translateY(' + toY + 'px)';
      /* Zero-displacement releases fire no transitionend */
      var done = false;
      function cleanup() {
        if (done) return;
        done = true;
        sheet.style.transition = '';
        sheet.style.transform = '';
      }
      sheet.addEventListener('transitionend', function(ev) {
        if (ev.propertyName !== 'transform') return;
        cleanup();
      }, { once: true });
      setTimeout(cleanup, 400);
    }
    function onUp(cancelled, e) {
      if (!dragging || !target) return;
      if (e && e.pointerId !== undefined && e.pointerId !== activePointerId) return;
      var sheet = target;
      var side = sheet.id === 'sidebar-left' ? 'left' : 'right';
      var dy = Math.max(0, currentY - startY);
      var sheetH = sheet.offsetHeight || 1;
      var wasEngaged = engaged;
      dragging = false;
      target = null;
      engaged = false;
      sheet.classList.remove('dragging');
      if (!wasEngaged) return;
      var dismiss = !cancelled && (
        dy > sheetH * COMMIT_RATIO ||
        (dy > FLICK_MIN_DISTANCE && velocity > FLICK_VELOCITY)
      );
      if (dismiss) {
        if (navigator.vibrate) navigator.vibrate(10);
        settle(sheet, sheetH + 32);
        setSidebarState(side, false);
        syncAfterSidebarToggle(side);
      } else {
        settle(sheet, 0);
      }
    }
    document.querySelectorAll('.sidebar.left, .sidebar.right').forEach(function(s) {
      s.addEventListener('pointerdown', onDown);
    });
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', function(e) { onUp(false, e); });
    window.addEventListener('pointercancel', function(e) { onUp(true, e); });
  })();

  refreshIcons();
  initCSelects();
  syncSearchCancel();
  syncSortVisibility();
  (function() {
    var sortMenu = document.getElementById('sort-menu');
    var sortTrigger = document.getElementById('sort-trigger');
    if (!sortMenu || !sortTrigger) return;
    var ctrl = window._morphSelect(sortTrigger, sortMenu);
    ctrl.sync = function() { window._renderSortMenu(sortMenu, sortMenu.dataset.value); };
  })();
  syncSidebarIcon('left');
  syncSidebarIcon('right');
  document.documentElement.classList.remove('suppress-transitions');

  function restoreTreeFromUrl() {
    ensureTopicTree();
    if (!_topicTree || _topicTreeMode !== 'checkbox') return;
    var url = new URL(window.location);
    var idsParam = url.searchParams.get('ids');
    var excludeAll = url.searchParams.get('exclude_all') === '1';
    window._restoringFilters = true;
    try {
      var roots = treeRootNodes();
      roots.forEach(function(node) { _topicTree.checkNode(node, false); });
      if (!excludeAll) {
        if (idsParam === null) {
          roots.forEach(function(node) { _topicTree.checkNode(node, true); });
        } else if (idsParam !== '') {
          idsParam.split(',').forEach(function(id) {
            var node = _topicTree.getNodeById(id);
            if (node) _topicTree.checkNode(node, true);
          });
        }
      }
    } finally {
      window._restoringFilters = false;
    }
  }

  function restoreFiltersFromUrl() {
    var url = new URL(window.location);

    window._dimensionSymbols.forEach(function(d) {
      var rows = document.querySelectorAll('.filter-dim-row[data-dim="' + d + '"]');
      if (rows.length === 0) return;
      var row = rows[0];
      var foundOp = 'eq', foundVal = null;
      ['eq','geq','leq'].forEach(function(op) {
        var v = url.searchParams.get(d + '_' + op);
        if (v !== null) { foundOp = op; foundVal = v; }
      });
      row.querySelector('.dim-op').value = foundOp;
      row.querySelector('.dim-val').value = (foundVal !== null ? foundVal : '');
    });

    var qtyParam = url.searchParams.get('qty');
    window._qtySelected = qtyParam ? qtyParam.split(',') : [];
    window.renderQtyChips();
    var qr = document.getElementById('qty-results');
    if (qr) qr.classList.remove('open');

    var diffMin = parseInt(url.searchParams.get('diff_min'));
    var diffMax = parseInt(url.searchParams.get('diff_max'));
    var dMinEl = document.getElementById('diff-min');
    var dMaxEl = document.getElementById('diff-max');
    if (!isNaN(diffMin)) dMinEl.value = diffMin;
    if (!isNaN(diffMax)) dMaxEl.value = diffMax;
    syncDiff();
  }

  function restoreAllFromUrl() {
    restoreFiltersFromUrl();
    restoreTreeFromUrl();
    syncFilterStates();
  }
  window.restoreAllFromUrl = restoreAllFromUrl;
  restoreFiltersFromUrl();
  restoreTreeFromUrl();
  syncFilterStates();
  syncViewTabLinks();
  window._initLatexObserver = function() {
    if (typeof katex !== 'undefined') observeLatexIn(document.querySelector('#main-content'));
  };
  syncDockPills();
  updateOverflowPadding();
  updateDimNameFits();
  /* KaTeX re-flows the dim-symbol after auto-render; re-measure once it
     has finished so the names show/hide correctly. */
  function recheckAfterKatex() {
    /* Defer two RAFs so layout settles after KaTeX writes new DOM. */
    requestAnimationFrame(function() {
      requestAnimationFrame(function() { updateDimNameFits(); });
    });
  }
  if (document.documentElement.classList.contains('katex-ready')) {
    recheckAfterKatex();
  } else {
    var obs2 = new MutationObserver(function() {
      if (document.documentElement.classList.contains('katex-ready')) {
        obs2.disconnect();
        recheckAfterKatex();
      }
    });
    obs2.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
  }
  window.addEventListener('resize', function() {
    updateOverflowPadding();
    updateDimNameFits();
  });

  function copyFormula(fmt) {
    var el = document.getElementById('formula-math');
    var latex = document.getElementById('formula-tex');
    if (!latex) return;
    var tex = latex.textContent;
    var doCopy = null;

    if (fmt === 'latex') {
      doCopy = navigator.clipboard.writeText(tex);
    } else if (fmt === 'unicode') {
      doCopy = import('https://cdn.jsdelivr.net/npm/unicodeit@0.7.5/+esm').then(function(mod) {
        return navigator.clipboard.writeText(mod.replace(tex));
      });
    } else if (fmt === 'png' || fmt === 'svg') {
      var url = 'https://latex.codecogs.com/' + fmt + '.latex?' + encodeURIComponent((fmt === 'png' ? '\\dpi{3000}' : '') + tex);
      doCopy = fetch(url).then(function(r) { return r.blob(); }).then(function(blob) {
        var item = {};
        item['image/' + fmt] = blob;
        return navigator.clipboard.write([new ClipboardItem(item)]);
      });
    }

    if (doCopy) {
      var labelMap = { latex: 'LaTeX', unicode: 'Unicode', png: 'PNG', svg: 'SVG' };
      var label = (window._localeUI.copy && window._localeUI.copy[fmt]) || labelMap[fmt] || fmt;
      doCopy.then(function() { showToast(window._localeUI.toast.copied + ' ' + label, 'success'); })
            .catch(function(e) { showToast(window._localeUI.toast.copy_failed + ': ' + e.message, 'error'); });
    }
  }
  window.copyFormula = copyFormula;

  function toggleCopyMenu(e) {
    e.stopPropagation();
    var menu = document.getElementById('formula-copy-menu');
    if (menu) menu.classList.toggle('open');
  }
  window.toggleCopyMenu = toggleCopyMenu;

  (function() {
    var searchForm = document.querySelector('.topbar-search form');
    var searchInput = searchForm ? searchForm.querySelector('input[name="q"]') : null;
    var suggestionsEl = document.getElementById('search-suggestions');
    var suggestDebounce = null;
    var suggestHighlight = -1;

    function fetchSuggestions(q) {
      if (!q) { suggestionsEl.classList.remove('open'); suggestionsEl.innerHTML = ''; return; }
      fetch('/api/search-suggestions?q=' + encodeURIComponent(q))
        .then(function(r) { return r.json(); })
        .then(function(data) {
          suggestionsEl.innerHTML = '';
          suggestHighlight = -1;
          if (!data.suggestions || data.suggestions.length === 0) {
            suggestionsEl.classList.remove('open');
            return;
          }
          data.suggestions.forEach(function(s) {
            var div = document.createElement('div');
            div.className = 'search-suggestion';
            div.tabIndex = -1;
            var headingSpan = document.createElement('span');
            headingSpan.textContent = s.heading;
            var kindSpan = document.createElement('span');
            kindSpan.className = 'ss-kind';
            kindSpan.textContent = s.kind;
            div.appendChild(headingSpan);
            div.appendChild(kindSpan);
            div.addEventListener('click', function() {
              suggestionsEl.classList.remove('open');
              searchInput.value = s.heading;
              navigateTo('/' + s.kind + '/' + s.id);
            });
            suggestionsEl.appendChild(div);
          });
          suggestionsEl.classList.add('open');
        })
        .catch(function() { suggestionsEl.classList.remove('open'); });
    }

    if (searchInput && suggestionsEl) {
      searchInput.addEventListener('input', function() {
        syncSearchCancel();
        /* The URL is only updated on submit (Enter / submit button); the
           box updates the URL via history on /search only on submit. */
        clearTimeout(suggestDebounce);
        suggestDebounce = setTimeout(function() {
          fetchSuggestions(searchInput.value.trim());
        }, 150);
      });
      searchInput.addEventListener('keydown', function(e) {
        var items = suggestionsEl.querySelectorAll('.search-suggestion');
        if (!suggestionsEl.classList.contains('open') || items.length === 0) return;
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          suggestHighlight = Math.min(suggestHighlight + 1, items.length - 1);
          items.forEach(function(el, i) { el.classList.toggle('highlighted', i === suggestHighlight); });
          items[suggestHighlight].scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          suggestHighlight = Math.max(suggestHighlight - 1, -1);
          items.forEach(function(el, i) { el.classList.toggle('highlighted', i === suggestHighlight); });
          if (suggestHighlight >= 0) items[suggestHighlight].scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'Enter' && suggestHighlight >= 0) {
          e.preventDefault();
          items[suggestHighlight].click();
        }
      });
      searchInput.addEventListener('blur', function() {
        setTimeout(function() { suggestionsEl.classList.remove('open'); }, 200);
      });
      searchInput.addEventListener('focus', function() {
        if (searchInput.value.trim()) fetchSuggestions(searchInput.value.trim());
      });
    }

    if (searchForm) {
      searchForm.addEventListener('submit', function(e) {
        e.preventDefault();
        suggestionsEl.classList.remove('open');
        if (searchInput) searchInput.blur();
        var q = searchInput ? encodeURIComponent(searchInput.value.trim()) : '';
        var url = q ? '/search?q=' + q : '/search';
        navigateTo(url);
      });
    }

    /* Keep <head> stylesheets in step with the target page so SPA
       navigation renders identically to a full load (e.g. create.css,
       which only /create declares). */
    function syncPageStyles(doc) {
      var want = {};
      Array.prototype.forEach.call(doc.head.querySelectorAll('link[rel="stylesheet"]'), function(l) {
        want[l.getAttribute('href')] = true;
      });
      Array.prototype.forEach.call(document.head.querySelectorAll('link[rel="stylesheet"]'), function(l) {
        var href = l.getAttribute('href');
        if (href in want) delete want[href];
        else l.remove();
      });
      Object.keys(want).forEach(function(href) {
        var l = document.createElement('link');
        l.rel = 'stylesheet';
        l.href = href;
        document.head.appendChild(l);
      });
    }

    function navigateTo(url, isPop) {
      if (!isPop && window.location.pathname + window.location.search === url) return;
      var si = document.querySelector('.topbar-search input[name="q"]');
      /* Keep the query visible while on the search results; clear it as
         soon as the user navigates away from them. */
      var target = new URL(url, window.location.origin);
      if (si) {
        si.value = target.pathname === '/search' ? (target.searchParams.get('q') || '') : '';
        syncSearchCancel();
      }
      var qs = document.getElementById('qty-search');
      if (qs) qs.value = '';
      fetch(url).then(function(r) { if (!r.ok) { window.location.href = url; return null; } return r.text(); }).then(function(html) {
        if (!html) return;
        var doc = new DOMParser().parseFromString(html, 'text/html');
        syncPageStyles(doc);
        var newContent = doc.getElementById('main-content');
        if (!newContent) { window.location.href = url; return; }
        document.getElementById('main-content').innerHTML = newContent.innerHTML;
        Array.from(document.getElementById('main-content').querySelectorAll('script')).forEach(function(oldScript) {
          var newScript = document.createElement('script');
          if (oldScript.src) newScript.src = oldScript.src;
          else newScript.textContent = oldScript.textContent;
          oldScript.parentNode.replaceChild(newScript, oldScript);
        });
        document.getElementById('main-content').scrollTop = 0;
        if (!isPop && !(window.history.state && window.history.state.url === url)) history.pushState({url: url}, '', url);
        var isFormulas = isFormulasView();
        var isSearch = url.indexOf('/search') !== -1;
        document.querySelectorAll('.view-tab').forEach(function(t) {
          if (isSearch) {
            t.classList.remove('active');
          } else {
            t.classList.toggle('active', isFormulas ? t.getAttribute('href').indexOf('formulas') !== -1 : t.getAttribute('href').indexOf('quantities') !== -1);
          }
        });
        renderMathInContent();
        refreshIcons();
        restoreAllFromUrl();
        updateOverflowPadding();
        updateDimNameFits();
        syncDockPills();
        syncSortVisibility();
      }).catch(function() { window.location.href = url; });
    }
    document.body.addEventListener('click', function(e) {
      var link = e.target.closest('a');
      if (!link) return;
      var href = link.getAttribute('href');
      if (!href || href.startsWith('http') || href.startsWith('//') || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('javascript:') || link.hasAttribute('download') || link.getAttribute('target') === '_blank') return;
      if (e.button === 1 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
      if (href === '/') { e.preventDefault(); navigateTo('/formulas'); return; }
      e.preventDefault();
      var parts = href.split('?');
      var base = parts[0];
      var params = new URLSearchParams(window.location.search);
      params.delete('q');
      if (parts[1]) {
        var linkParams = new URLSearchParams(parts[1]);
        linkParams.forEach(function(value, key) { params.set(key, value); });
      }
      href = base + (params.toString() ? '?' + params.toString() : '');
      navigateTo(href);
    });
    window.addEventListener('popstate', function() { navigateTo(window.location.href, true); });

    window._navigateTo = navigateTo;
  })();
})();
