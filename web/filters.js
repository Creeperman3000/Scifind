/* eslint-disable no-undef */
'use strict';
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
     the whole partial-checked subtree keeps its checkboxes visible. */
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
       show their control. */
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

  document.getElementById('tree-select-all').addEventListener('click', function() {
    bulkCheck(true);
  });
  document.getElementById('tree-deselect-all').addEventListener('click', function() {
    bulkCheck(false);
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
    loadPage(url.pathname + url.search, true);
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
    loadPage(url.pathname + url.search, true);
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
      var modal = document.getElementById('formula-sql-modal');
      if (modal && modal.classList.contains('open')) modal.classList.remove('open');
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
          var option = select.options[i];
          var btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'sort-option';
          btn.setAttribute('role', 'option');
          btn.setAttribute('aria-selected', 'false');
          btn.setAttribute('data-cselect-index', i);
          var sp = document.createElement('span');
          var txt = option.textContent.trim();
          sp.textContent = txt;
          btn.appendChild(sp);
          menu.appendChild(btn);
        }
        var curTxt = select.options[sel] ? select.options[sel].textContent.trim() : '';
        label.textContent = curTxt;

        /* Size the trigger to the widest option (label + chevron + padding +
           gap) so the menu's min-width:100% matches. The <i data-lucide>
           isn't swapped for an <svg> yet, so probe with a real chevron
           <svg> and let the browser compute the width. */
        var widestText = curTxt;
        for (var j = 0; j < select.options.length; j++) {
          var t = select.options[j].textContent.trim();
          if (t.length > widestText.length) widestText = t;
        }
        var probe = document.createElement('button');
        probe.className = trigger.className;
        probe.style.cssText = 'position:absolute;visibility:hidden;left:-9999px;top:-9999px;width:auto;min-width:0;';
        var probeLbl = document.createElement('span');
        probeLbl.className = 'cselect-label';
        probeLbl.textContent = widestText;
        probe.appendChild(probeLbl);
        if (!compact) {
          var ns = 'http://www.w3.org/2000/svg';
          var svg = document.createElementNS(ns, 'svg');
          svg.setAttribute('width', '14');
          svg.setAttribute('height', '14');
          svg.setAttribute('viewBox', '0 0 24 24');
          svg.setAttribute('fill', 'none');
          svg.setAttribute('stroke', 'currentColor');
          svg.setAttribute('stroke-width', '2');
          svg.setAttribute('stroke-linecap', 'round');
          svg.setAttribute('stroke-linejoin', 'round');
          var path = document.createElementNS(ns, 'path');
          path.setAttribute('d', 'm6 9 6 6 6-6');
          svg.appendChild(path);
          probe.appendChild(svg);
        }
        document.body.appendChild(probe);
        trigger.style.minWidth = probe.offsetWidth + 'px';
        document.body.removeChild(probe);
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
    loadPage(url, true);
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
      ['_eq','_geq','_leq'].forEach(function(s) { url.searchParams.delete(d + s); });
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
