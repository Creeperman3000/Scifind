/* eslint-disable no-undef */
'use strict';
/* ---------- Topic tree (infinite-tree) ---------- */

var _treeEl = document.getElementById('science-tree');
var _topicTree = null;
var _topicTreeMode = null;

function $(id) { return window.SFUtils.byId(id); }
function $$(sel, root) { return window.SFUtils.bySel(sel, root); }
function on(id, ev, fn) { return window.SFUtils.on(id, ev, fn); }
function setParam(sp, k, v, keep) { return window.SFUtils.setParam(sp, k, v, keep); }
function toggleCls(id, cls, cond) { return window.SFUtils.toggleCls(id, cls, cond); }
function escapeHtml(s) { return window.SFUtils.escapeHtml(s); }

function isNodeChecked(node) {
  return !!node.state.checked && !node.state.indeterminate;
}

function topicTreeRow(node) {
  var s = node.state;
  var branch = node.hasChildren();
  var cls = 'tree-row ' + (branch ? (s.open ? 'open' : 'closed') : 'leaf');
  if (s.indeterminate) cls += ' indeterminate';
  else if (s.checked) cls += ' checked';
  if (s.selected) cls += ' selected';
  /* Root rows, indeterminate rows and their descendants always show control. */
  var underIndet = false;
  for (var parent = node.parent; parent && parent.state.depth >= 0; parent = parent.parent) {
    if (parent.state.indeterminate) { underIndet = true; break; }
  }
  if (s.depth === 0 || s.indeterminate || underIndet) cls += ' always-visible';
  var ctl = _topicTreeMode === 'radio' ? '<span class="tree-radio"></span>' : '<span class="tree-checkbox"></span>';
  return '<div class="' + cls + '" data-id="' + escapeHtml(node.id) + '"' +
    ' data-depth="' + s.depth + '" style="padding-left:' + (s.depth * 24) + 'px">' +
    (branch ? '<span class="tree-toggler"></span>' : '<span class="tree-leaf-spacer"></span>') +
    '<span class="tree-label">' + ctl + escapeHtml(node.name) + '</span></div>';
}

function buildTopicTree(mode) {
  if (_topicTree) _topicTree.destroy();
  _topicTreeMode = mode;
  var sidebarRight = $('sidebar-right');
  if (sidebarRight) sidebarRight.classList.toggle('tree-radio-mode', mode === 'radio');
  _topicTree = new InfiniteTree(_treeEl, {
    data: window._topicTreeData || [],
    autoOpen: true,
    selectable: mode === 'radio',
    /* Radio: clicking the selected node deselects (lib emits selectNode(null)). */
    shouldSelectNode: function(node) { return _topicTree._programmatic || !!node; },
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
      if (typeof window._treeSelectionChanged === 'function') window._treeSelectionChanged(node ? node.id : null);
    });
  }
}

/* Rebuild when the page kind changed (SPA nav between filter views and /create). */
function ensureTopicTree() {
  if (!_treeEl || typeof window.InfiniteTree === 'undefined') return;
  var mode = $('create-form') ? 'radio' : 'checkbox';
  if (_topicTree && mode === _topicTreeMode) return;
  buildTopicTree(mode);
}

function treeRootNodes() {
  return _topicTree ? _topicTree.getRootNode().children : [];
}

/* Ids of checked-subtree roots (what the server treats as the selection). */
function topCheckedIds() {
  var ids = [];
  (function walk(nodes) {
    nodes.forEach(function(n) { if (isNodeChecked(n)) ids.push(n.id); else walk(n.children || []); });
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
  if ((id || null) === (current ? current.id : null)) return;
  _topicTree._programmatic = true;
  try {
    _topicTree.selectNode(id ? _topicTree.getNodeById(id) : null);
  } finally {
    _topicTree._programmatic = false;
  }
};

/* Bulk (de)select without firing applyFilters per node. */
function bulkCheck(value) {
  if (!_topicTree || _topicTreeMode !== 'checkbox') return;
  window._restoringFilters = true;
  try {
    treeRootNodes().forEach(function(node) { _topicTree.checkNode(node, value); });
  } finally {
    window._restoringFilters = false;
  }
  applyFilters();
}

on('tree-select-all', 'click', function() { bulkCheck(true); });
on('tree-deselect-all', 'click', function() { bulkCheck(false); });
if (_treeEl) _treeEl.addEventListener('dblclick', function(e) { e.stopPropagation(); });

function dimFilterChange() { applyFilters(); setTimeout(syncFilterStates, 0); }

/* Shared fill-state for the zeros toggle (handler + button sync).
   Zero means "evaluates to 0", so expressions like 2-2 count too. */
function dimFillState(vals) {
  var resolved = (vals || dimVals()).map(evalDimExpr);
  var set = resolved.filter(function(r) { return r !== null; }).length;
  return { allFilled: set === resolved.length, hasZero: resolved.indexOf(0) !== -1, dimSet: set };
}

/* Left-sidebar element bindings. Re-run after #sidebar-left-inner is
   replaced (e.g. /create hijacks it; loadPage restores it on leave):
   `on()` no-ops on missing elements and replaced nodes are detached,
   so re-running never double-binds live elements. */
function bindSidebarLeft() {
  on('dim-reset', 'click', function() {
    $$('.filter-dim-row').forEach(function(row) {
      row.querySelector('.dim-val').value = '';
      row.querySelector('.dim-op').value = 'eq';
    });
    applyFilters();
  });

  on('dim-fill-zeros', 'click', function() {
    var st = dimFillState();
    if (st.allFilled && st.hasZero) {
      dimValInputs().forEach(function(input) {
        if (evalDimExpr(input.value) === 0) input.value = '';
      });
    } else {
      $$('.filter-dim-row').forEach(function(row) {
        var input = row.querySelector('.dim-val');
        if (!dimResolved(input.value)) input.value = '0';
      });
    }
    applyFilters();
  });

  on('dim-mode-toggle', 'click', function() { toggleModeSwitched('dim'); });

  on('dim-base-qty', 'click', function() {
    var url = new URL(window.location);
    url.searchParams.get('is_dim') === '1' ? url.searchParams.delete('is_dim') : url.searchParams.set('is_dim', '1');
    loadPage(url.pathname + url.search, true);
  });

  on('qty-mode-toggle', 'click', function() { if (isFormulasView()) toggleModeSwitched('fml'); });

  on('qty-reset', 'click', function() {
    window._qtySelected = [];
    var input = $('qty-search');
    if (input) input.value = '';
    if (typeof window.renderQtyChips === 'function') window.renderQtyChips();
    if (typeof window.renderQtyResults === 'function') window.renderQtyResults('');
    applyFilters();
  });

  on('diff-reset', 'click', function() {
    $('diff-min').value = 1;
    $('diff-max').value = 10;
    syncDiff();
    applyFilters();
  });

  on('diff-min', 'change', applyFilters);
  on('diff-max', 'change', applyFilters);

  bindQtySearch();
  bindDiffPointer();
}
window._bindSidebarLeft = bindSidebarLeft;
bindSidebarLeft();

/* mode_switched is a comma list ('dim' = dim OR, 'fml' = qty OR). */
function getSwitched(url) { return (url.searchParams.get('mode_switched') || '').split(',').filter(Boolean); }
function setSwitched(url, parts) {
  parts.length ? url.searchParams.set('mode_switched', parts.join(',')) : url.searchParams.delete('mode_switched');
}

function toggleModeSwitched(key) {
  var url = new URL(window.location);
  var switched = getSwitched(url);
  var idx = switched.indexOf(key);
  idx !== -1 ? switched.splice(idx, 1) : switched.push(key);
  setSwitched(url, switched);
  loadPage(url.pathname + url.search, true);
}

function setModeBtn(btn, active, title) {
  btn.classList.toggle('active', active);
  btn.title = title;
  btn.innerHTML = '<i data-lucide="' + (active ? 'squares-unite' : 'squares-intersect') + '" width="16" height="16"></i>';
  refreshIcons();
}

function syncModeBtn(btnId, show, key, url) {
  var btn = $(btnId);
  if (!btn) return;
  if (!show) { btn.classList.add('hidden'); return; }
  btn.classList.remove('hidden');
  var isOr = getSwitched(url).indexOf(key) !== -1;
  var dim = btnId === 'dim-mode-toggle';
  setModeBtn(btn, isOr, window._localeUI.filter[dim ? (isOr ? 'dim_mode_or' : 'dim_mode_and') : (isOr ? 'qty_mode_or' : 'qty_mode_and')]);
}

function syncFilterStates() {
  var url = new URL(window.location);
  cleanModeSwitched(url);
  var st = dimFillState();
  var formulas = isFormulasView();
  var qtyN = (window._qtySelected || []).length;

  syncModeBtn('dim-mode-toggle', st.dimSet >= 2, 'dim', url);
  syncModeBtn('qty-mode-toggle', formulas && qtyN >= 2, 'fml', url);
  if ($('qty-mode-toggle') && !formulas) $('qty-mode-toggle').classList.add('hidden');

  toggleCls('dim-base-qty', 'active', url.searchParams.get('is_dim') === '1');
  toggleCls('dim-base-qty', 'disabled', formulas);

  toggleCls('dim-fill-zeros', 'active', st.allFilled && st.hasZero);
  toggleCls('dim-fill-zeros', 'disabled', st.allFilled && !st.hasZero);
  toggleCls('dim-reset', 'disabled', !st.dimSet);

  if (_topicTree && _topicTreeMode === 'checkbox') {
    toggleCls('tree-deselect-all', 'disabled', topCheckedIds().length === 0);
    toggleCls('tree-select-all', 'disabled', allRootNodesChecked());
  }
  toggleCls('qty-reset', 'disabled', qtyN === 0);

  var dMin = $('diff-min'), dMax = $('diff-max');
  toggleCls('diff-reset', 'disabled', dMin && dMax && parseInt(dMin.value) === 1 && parseInt(dMax.value) === 10);

  var sortMenu = $('sort-menu');
  var allowed = window._availableSorts || [];
  if (sortMenu && allowed.length) {
    var want = url.searchParams.get('sort');
    if (allowed.indexOf(want) === -1) want = window._defaultSort || null;
    window._renderSortMenu(sortMenu, want);
  }
}

function cleanModeSwitched(url) {
  var raw = url.searchParams.get('mode_switched');
  if (!raw) return;
  var qp = url.searchParams.get('qty');
  var dimCount = window._dimensionSymbols.filter(function(d) {
    return ['eq', 'geq', 'leq'].some(function(op) { return url.searchParams.get(d + '_' + op) !== null; });
  }).length;
  var parts = getSwitched(url).filter(function(key) {
    if (key === 'dim') return dimCount >= 2;
    if (key === 'fml') return !!qp && qp.split(',').length >= 2;
    return true;
  });
  if (parts.join(',') !== getSwitched(url).join(',')) {
    setSwitched(url, parts);
    history.replaceState(null, '', url.toString());
  }
}

function syncViewTabLinks() {
  $$('.view-tab').forEach(function(tab) {
    var href = tab.getAttribute('href');
    if (href) tab.setAttribute('href', href.split('?')[0] + window.location.search);
  });
}

function isFormulasView() {
  var p = window.location.pathname;
  return p.indexOf('/quantities') === -1 && p.indexOf('/quantity/') === -1 && p.indexOf('/unit/') === -1;
}

(function() {
  var allQuantities = [];
  window._qtySelected = [];
  function ensureQuantities(cb) {
    if (allQuantities.length) { if (cb) cb(); return; }
    window.SFApi.getJSON('/api/quantities-filter').then(function(data) {
      if (data && data.quantities) allQuantities = data.quantities;
      if (cb) cb();
    }, function() { if (cb) cb(); });
  }

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
    /* Selected value lives in the trigger, not repeated as a row. */
    sortMenu.innerHTML = allowed.filter(function(key) { return key !== value; }).map(function(key) {
      return '<button type="button" class="sort-option" role="option" aria-selected="false"' +
        ' data-action="sort-pick" data-sort="' + key + '"><span>' + (labels[key] || key) + '</span></button>';
    }).join('');
    var labelEl = $('sort-trigger-label');
    if (labelEl) labelEl.textContent = labels[value] || value || '';
    refreshIcons();
  };

  /* Morphing select: opening morphs the trigger into the list head (see
     CSS); the selected value stays in the trigger, not as a row. */
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
        window._morphSelects.forEach(function(other) { if (other !== ctrl && other.isOpen()) other.close(); });
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
      toggle: function() { this.isOpen() ? this.close() : this.open(); }
    };
    window._morphSelects.push(ctrl);
    menu._morphCtrl = ctrl;
    return ctrl;
  };

  /* Wraps a native <select> in a custom dropdown; the hidden native
     stays the source of truth and dispatches 'change'. */
  function chevronSvg() {
    var s = document.createElement('span');
    s.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"' +
      ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>';
    return s.firstChild;
  }

  function sizeTriggerToWidest(trigger, select, label, compact) {
    var cur = select.options[select.selectedIndex];
    var widest = cur ? cur.textContent.trim() : '';
    $$('option', select).forEach(function(o) {
      var t = o.textContent.trim();
      if (t.length > widest.length) widest = t;
    });
    label.textContent = cur ? cur.textContent.trim() : '';
    var probe = document.createElement('button');
    probe.className = trigger.className;
    probe.style.cssText = 'position:absolute;visibility:hidden;left:-9999px;top:-9999px;width:auto;min-width:0;';
    var pl = document.createElement('span');
    pl.className = 'cselect-label';
    pl.textContent = widest;
    probe.appendChild(pl);
    if (!compact) probe.appendChild(chevronSvg());
    document.body.appendChild(probe);
    trigger.style.minWidth = probe.offsetWidth + 'px';
    document.body.removeChild(probe);
  }

  function initCSelect(select) {
    if (!select || select.dataset.cselectBound || !select.options.length) return;
    select.dataset.cselectBound = '1';
    var compact = select.classList.contains('dim-op');
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
    ctrl.sync = render;

    function render() {
      var sel = select.selectedIndex;
      menu.innerHTML = $$('option', select).map(function(option, i) {
        if (i === sel) return '';
        return '<button type="button" class="sort-option" role="option" aria-selected="false"' +
          ' data-cselect-index="' + i + '"><span>' + escapeHtml(option.textContent.trim()) + '</span></button>';
      }).join('');
      sizeTriggerToWidest(trigger, select, label, compact);
    }

    function commit(idx) {
      if (idx === select.selectedIndex) { ctrl.close(); return; }
      select.selectedIndex = idx;
      ctrl.close();
      render();
      window._bumpLabel(label);
      select.dispatchEvent(new Event('change', { bubbles: true }));
    }

    trigger.addEventListener('click', function(e) { e.stopPropagation(); e.preventDefault(); ctrl.toggle(); });
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
    $$('.settings-item select, .filter-dim-row select.dim-op', root || document).forEach(initCSelect);
  };

  window.renderQtyChips = function() {
    var chipsEl = $('qty-chips');
    if (!chipsEl) return;
    if (!allQuantities.length && window._qtySelected.length) {
      ensureQuantities(function() { if (allQuantities.length) window.renderQtyChips(); });
    }
    var byId = {};
    allQuantities.forEach(function(q) { byId[q.id] = q; });
    var html = window._qtySelected.map(function(qid) {
      var q = byId[qid];
      var label = q ? (q.symbol || q.name || q.id) : qid;
      return '<span class="qty-chip" data-qty="' + escapeHtml(qid) + '">' + window._renderLatex(label) +
        '<span class="qty-chip-x" data-action="remove-qty-chip" data-qty="' + escapeHtml(qid) + '">' +
        '<i data-lucide="x" width="12" height="12"></i></span></span>';
    }).join('');
    if (chipsEl._lastChipsHtml !== html) {
      chipsEl.innerHTML = html;
      chipsEl._lastChipsHtml = html;
      refreshIcons();
    }
  };

  window.renderQtyResults = function(query) {
    var resultsEl = $('qty-results');
    if (!resultsEl) return;
    if (!allQuantities.length) { ensureQuantities(function() { window.renderQtyResults(query); }); return; }
    var q = (query || '').toLowerCase().trim();
    var matches = allQuantities.filter(function(item) {
      return !q || ['name', 'symbol', 'id'].some(function(k) {
        return String(item[k] || '').toLowerCase().indexOf(q) !== -1;
      });
    }).slice(0, 30);
    if (!matches.length) { resultsEl.classList.remove('open'); resultsEl.innerHTML = ''; return; }
    resultsEl.classList.add('open');
    resultsEl.innerHTML = matches.map(function(item) {
      var sel = window._qtySelected.indexOf(item.id) !== -1 ? ' selected' : '';
      var inner = window.SFUtils.qtyResultInner(item.symbol ? window._renderLatex(item.symbol) : '', item.name || item.id);
      var search = (item.id + ' ' + (item.symbol || '') + ' ' + (item.name || '')).toLowerCase();
      return '<div class="qty-result' + sel + '" data-kind="qty" data-insert="' +
        escapeHtml(item.id) + '" data-search="' + escapeHtml(search) +
        '" data-action="add-qty-chip" data-qty="' + escapeHtml(item.id) + '" tabindex="0">' + inner + '</div>';
    }).join('');
  };

  /* Single refresh point for chips+results+filter application. */
  function refreshQty(query) {
    window.renderQtyChips();
    toggleCls('qty-results', 'open', false);
    dimFilterChange();
  }

  window.addQtyChip = function(qid) {
    if (window._qtySelected.indexOf(qid) !== -1) return;
    window._qtySelected.push(qid);
    var input = $('qty-search');
    if (input) input.value = '';
    refreshQty('');
  };

  window.removeQtyChip = function(qid) {
    window._qtySelected = window._qtySelected.filter(function(id) { return id !== qid; });
    var input = $('qty-search');
    refreshQty(input ? input.value : '');
  };

  function resetQtySearch() {
    var el = $('qty-results');
    if (el) el.classList.remove('open');
    var inp = $('qty-search');
    if (inp) inp._userInteracted = false;
  }
  window.addEventListener('pageshow', resetQtySearch);
  resetQtySearch();
  bindQtySearch();
  if (!window._sfQtyKeysBound) {
    window._sfQtyKeysBound = true;
    document.addEventListener('keydown', function(e) {
      var el = $('qty-results');
      if (!el || !el.classList.contains('open') || (e.key !== 'ArrowDown' && e.key !== 'ArrowUp' && e.key !== 'Enter')) return;
      var items = $$('.qty-result', el);
      if (!items.length) return;
      var qtyInput = $('qty-search');
      if (!qtyInput || (!qtyInput.contains(document.activeElement) && !el.contains(document.activeElement))) return;
      var idx = items.indexOf(document.activeElement);
      if (idx < 0 && document.activeElement === qtyInput) idx = -1;
      e.preventDefault();
      if (e.key === 'ArrowDown') (items[idx + 1] || items[0]).focus();
      else if (e.key === 'ArrowUp') (idx > 0 ? items[idx - 1] : qtyInput || items[items.length - 1]).focus();
      else if (idx >= 0) items[idx].click();
    });
  }
  document.addEventListener('click', function(e) {
    var wrap = document.querySelector('.filter-qty-search-wrap');
    if (wrap && !wrap.contains(e.target)) toggleCls('qty-results', 'open', false);
  });
})();

function bindQtySearch() {
  var qtyInput = $('qty-search');
  if (!qtyInput || qtyInput.dataset.sfBound) return;
  qtyInput.dataset.sfBound = '1';
  var renderQtyDebounced = window.SFUtils.debounce(function() { window.renderQtyResults(qtyInput.value); }, 120);
  qtyInput.addEventListener('input', renderQtyDebounced);
  qtyInput.addEventListener('focus', function() {
    if (qtyInput.value.trim() || qtyInput._userInteracted) window.renderQtyResults(qtyInput.value);
  });
  qtyInput.addEventListener('click', function() {
    qtyInput._userInteracted = true;
    window.renderQtyResults(qtyInput.value);
  });
  qtyInput.addEventListener('blur', function() {
    setTimeout(function() {
      var active = document.activeElement;
      if (active && active.classList && active.classList.contains('qty-result')) return;
      var el = $('qty-results');
      if (el) el.classList.remove('open');
    }, 200);
  });
}

function applyFilters() {
  if (window._restoringFilters) return;
  loadPage(buildFilterUrl(), true);
}

function buildFilterUrl() {
  var url = new URL(window.location);
  var sp = url.searchParams;
  var U = window.SFUtils;
  U.stripTopicParams(sp);
  U.stripPagingParams(sp);
  U.stripSearchParam(sp, url.pathname === '/search');

  if (_topicTree && _topicTreeMode === 'checkbox' && !allRootNodesChecked()) sp.set('ids', topCheckedIds().join(','));
  else if (_topicTree && _topicTreeMode === 'checkbox') sp.delete('ids');
  else sp.set('ids', '');

  var dMinEl = $('diff-min'), dMaxEl = $('diff-max');
  if (dMinEl && dMaxEl) {
    var dMin = Math.round(parseFloat(dMinEl.value)), dMax = Math.round(parseFloat(dMaxEl.value));
    setParam(sp, 'diff_min', dMin, dMin > 1);
    setParam(sp, 'diff_max', dMax, dMax < 10);
  }

  window._dimensionSymbols.forEach(function(d) {
    var row = document.querySelector('.filter-dim-row[data-dim="' + d + '"]');
    if (!row) return;
    ['_eq', '_geq', '_leq'].forEach(function(s) { sp.delete(d + s); });
    var parsed = evalDimExpr(row.querySelector('.dim-val').value);
    if (parsed !== null) sp.set(d + '_' + row.querySelector('.dim-op').value, parsed);
  });

  var qty = window._qtySelected || [];
  setParam(sp, 'qty', qty.join(','), qty.length > 0);

  var sortMenu = $('sort-menu');
  var allowed = window._availableSorts || [];
  var sortVal = sortMenu && allowed.length ? (sortMenu.dataset.value || '') : '';
  setParam(sp, 'sort', sortVal, sortVal && allowed.indexOf(sortVal) !== -1 && sortVal !== (window._defaultSort || null));

  if (url.pathname !== '/formulas' && url.pathname !== '/quantities' && url.pathname !== '/search') url.pathname = '/formulas';
  return url.pathname + url.search;
}
function syncDiff() {
  var min = $('diff-min'), max = $('diff-max'), fill = $('diff-fill');
  if (!min || !max || !fill) return;
  var raw1 = parseFloat(min.value), raw2 = parseFloat(max.value);
  if (raw1 > raw2) { min.value = raw2; max.value = raw1; var t = raw1; raw1 = raw2; raw2 = t; }
  $('diff-min-val').textContent = Math.round(raw1);
  $('diff-max-val').textContent = Math.round(raw2);
  /* Fill edges sit on thumb centers, whose travel stops half a thumb short of each track end. */
  var travel = '(100% - var(--thumb-size))';
  fill.style.left = 'calc(' + travel + ' * ' + ((raw1 - 1) / 9) + ' + var(--thumb-size) / 2)';
  fill.style.width = 'calc(' + travel + ' * ' + ((raw2 - raw1) / 9) + ')';
}
syncDiff();

/* Both sidebar inputs have pointer-events:none so the track catches the
   click; dispatch onto the nearer thumb (native behavior would route
   everything to the topmost input). Scoped to the filter sidebar so the
   /create difficulty slider (native single-thumb drag) is untouched. */
function bindDiffPointer() {
  var wrap = document.querySelector('#sidebar-left-inner .diff-sliders');
  if (!wrap || wrap.dataset.sfBound) return;
  wrap.dataset.sfBound = '1';
  wrap.addEventListener('pointerdown', function(e) {
    if (e.button !== 0) return;
    var min = $('diff-min'), max = $('diff-max');
    if (!min || !max) return;
    var rect = wrap.getBoundingClientRect();
    var thumb = parseFloat(getComputedStyle(wrap).getPropertyValue('--thumb-size')) || 20;
    function toValue(px) {
      var usable = Math.max(rect.width - thumb, 1);
      return 1 + 9 * Math.max(0, Math.min(usable, px - thumb / 2)) / usable;
    }
    var value = toValue(e.clientX - rect.left);
    var target = Math.abs(value - parseFloat(min.value)) <= Math.abs(value - parseFloat(max.value)) ? min : max;
    function drag(ev) { target.value = toValue(ev.clientX - rect.left); target.dispatchEvent(new Event('input', { bubbles: true })); }
    function drop() {
      window.removeEventListener('pointermove', drag);
      window.removeEventListener('pointerup', drop);
      target.dispatchEvent(new Event('change', { bubbles: true }));
    }
    target.value = value;
    target.dispatchEvent(new Event('input', { bubbles: true }));
    target.focus();
    window.addEventListener('pointermove', drag);
    window.addEventListener('pointerup', drop);
    e.preventDefault();
  });
}
