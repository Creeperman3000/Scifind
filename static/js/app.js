
/* eslint-disable no-undef */

(function() {
  'use strict';

  function showToast(message, type) {
    var container = document.getElementById('toast-container');
    var t = document.createElement('div');
    t.className = 'toast ' + (type || 'success');
    t.textContent = message;
    container.appendChild(t);
    setTimeout(function() { t.style.opacity = '0'; t.style.transition = 'opacity 0.3s'; setTimeout(function() { t.remove(); }, 300); }, 4000);
  }
  window.showToast = showToast;

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
      var vh = window.innerHeight * 0.35;
      var contentH = main.scrollHeight - vh;
      main.classList.toggle('no-overflow', contentH <= main.clientHeight);
    }
  }

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

  (function() {
    var treeData = window._topicTreeData || [];
    var $tree = $('#science-tree');
    if (!$tree.length || typeof $.fn.jstree === 'undefined') return;
    $tree.on('dblclick.jstree', function(e) { e.stopPropagation(); });
    $tree.jstree({
      core: {
        data: treeData,
        themes: { icons: false, dots: false },
        dblclick_toggle: false,
      },
      checkbox: {
        keep_selected_style: false,
        three_state: true,
        cascade: 'up+down+undetermined',
      },
      plugins: ['checkbox'],
    });
    window._jstree = $tree.jstree(true);
    $tree.on('ready.jstree', function() {
      restoreTreeFromUrl();
      syncFilterStates();
      syncViewTabLinks();
    });
  })();

  document.getElementById('tree-select-all').addEventListener('click', function() {
    if (window._jstree) { window._jstree.check_all(); applyFilters(); }
  });
  document.getElementById('tree-deselect-all').addEventListener('click', function() {
    if (window._jstree) { window._jstree.uncheck_all(); applyFilters(); }
  });
  $('#science-tree').on('changed.jstree check_node.jstree uncheck_node.jstree', function() {
    syncUndeterminedVisibility(); applyFilters();
    setTimeout(syncFilterStates, 0);
  });

  (function() {
    var tree = $('#science-tree')[0], timer = null;
    var obs = new MutationObserver(function(muts) {
      for (var i = 0; i < muts.length; i++) {
        var m = muts[i];
        if (m.type !== 'attributes') continue;
        var c = m.target.className, o = m.oldValue || '';
        if ((c.indexOf('jstree-undetermined') !== -1) !== (o.indexOf('jstree-undetermined') !== -1)) {
          clearTimeout(timer);
          timer = setTimeout(function() { syncUndeterminedVisibility(); }, 20);
          return;
        }
      }
    });
    if (tree) obs.observe(tree, { attributes: true, subtree: true, attributeFilter: ['class'], attributeOldValue: true });
  })();

  function syncUndeterminedVisibility() {
    var tree = $('#science-tree');
    tree.find('.jstree-node').removeClass('jstree-undetermined-parent');
    tree.find('.jstree-undetermined').each(function() {
      $(this).closest('.jstree-node').addClass('jstree-undetermined-parent');
    });
  }

  function dimFilterChange() { applyFilters(); setTimeout(syncFilterStates, 0); }

  document.getElementById('dim-reset').addEventListener('click', function() {
    document.querySelectorAll('.filter-dim-row').forEach(function(row) {
      row.querySelector('.dim-val').value = '';
      row.querySelector('.dim-op').value = 'eq';
    });
    applyFilters();
  });

  document.getElementById('dim-fill-zeros').addEventListener('click', function() {
    var allFilled = true, hasZero = false;
    document.querySelectorAll('.filter-dim-row .dim-val').forEach(function(input) {
      var v = input.value.trim();
      if (v === '') allFilled = false;
      else if (v === '0') hasZero = true;
    });
    if (allFilled && hasZero) {
      document.querySelectorAll('.filter-dim-row .dim-val').forEach(function(input) {
        if (input.value.trim() === '0') input.value = '';
      });
    } else {
      document.querySelectorAll('.filter-dim-row').forEach(function(row) {
        var input = row.querySelector('.dim-val');
        if (input.value === '' || input.value === '-' || input.value === '+' || input.value === '.') {
          input.value = '0';
        }
      });
    }
    applyFilters();
  });

  document.getElementById('dim-mode-toggle').addEventListener('click', function() {
    var url = new URL(window.location);
    var switched = (url.searchParams.get('mode_switched') || '').split(',').filter(Boolean);
    var idx = switched.indexOf('dim');
    if (idx !== -1) switched.splice(idx, 1);
    else switched.push('dim');
    if (switched.length) url.searchParams.set('mode_switched', switched.join(','));
    else url.searchParams.delete('mode_switched');
    fetchContent(url.pathname + url.search, true);
  });

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

  function syncFilterStates() {
    var url = new URL(window.location);

    cleanModeSwitched(url);

    var modeBtn = document.getElementById('dim-mode-toggle');
    if (modeBtn) {
      var filledCount = 0;
      document.querySelectorAll('.filter-dim-row .dim-val').forEach(function(input) {
        if (input.value.trim() !== '') filledCount++;
      });
      if (filledCount >= 2) {
        modeBtn.style.display = '';
        var switched = getSwitched(url);
        var isOr = switched.indexOf('dim') !== -1;
        modeBtn.classList.toggle('active', isOr);
        modeBtn.title = isOr ? window._localeUI.filter.dim_mode_or : window._localeUI.filter.dim_mode_and;
        modeBtn.innerHTML = '<i data-lucide="' + (isOr ? 'squares-unite' : 'squares-intersect') + '" width="16" height="16"></i>';
        if (typeof lucide !== 'undefined') lucide.createIcons();
      } else {
        modeBtn.style.display = 'none';
      }
    }

    var baseQtyBtn = document.getElementById('dim-base-qty');
    if (baseQtyBtn) {
      baseQtyBtn.classList.toggle('active', url.searchParams.get('is_dim') === '1');
      baseQtyBtn.classList.toggle('disabled', isFormulasView());
    }

    var fillBtn = document.getElementById('dim-fill-zeros');
    if (fillBtn) {
      var allFilled = true, hasZero = false;
      document.querySelectorAll('.filter-dim-row .dim-val').forEach(function(input) {
        var v = input.value.trim();
        if (v === '') allFilled = false;
        else if (v === '0') hasZero = true;
      });
      fillBtn.classList.toggle('active', allFilled && hasZero);
      fillBtn.classList.toggle('disabled', allFilled && !hasZero);
    }

    var dimReset = document.getElementById('dim-reset');
    if (dimReset) {
      var dimHasVal = false;
      document.querySelectorAll('.filter-dim-row .dim-val').forEach(function(input) {
        if (input.value.trim() !== '') dimHasVal = true;
      });
      dimReset.classList.toggle('disabled', !dimHasVal);
    }

    var deselectBtn = document.getElementById('tree-deselect-all');
    if (deselectBtn && window._jstree) {
      var checked = window._jstree.get_checked(true);
      deselectBtn.classList.toggle('disabled', checked.length === 0);
    }

    var treeSelectAll = document.getElementById('tree-select-all');
    if (treeSelectAll && window._jstree) {
      var allChecked = window._jstree.get_checked(true);
      var allNodes = window._jstree.get_node('#').children_d;
      treeSelectAll.classList.toggle('disabled', allNodes.length === allChecked.length);
    }

    var qtyModeBtn = document.getElementById('qty-mode-toggle');
    if (qtyModeBtn) {
      if (!isFormulasView()) {
        qtyModeBtn.style.display = 'none';
      } else {
        var qtyCount = (window._qtySelected || []).length;
        if (qtyCount >= 2) {
          qtyModeBtn.style.display = '';
          var switched = getSwitched(url);
          var isSwitched = switched.indexOf('fml') !== -1;
          qtyModeBtn.classList.toggle('active', isSwitched);
          qtyModeBtn.classList.remove('inactive');
          qtyModeBtn.title = isSwitched ? window._localeUI.filter.qty_mode_or : window._localeUI.filter.qty_mode_and;
          qtyModeBtn.innerHTML = '<i data-lucide="' + (isSwitched ? 'squares-unite' : 'squares-intersect') + '" width="16" height="16"></i>';
          if (typeof lucide !== 'undefined') lucide.createIcons();
        } else {
          qtyModeBtn.style.display = 'none';
        }
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

    var sortEl = document.getElementById('sort-select');
    var allowed = window._availableSorts || [];
    var defaultSort = window._defaultSort || null;
    if (sortEl && allowed.length) {
      var wantValue = url.searchParams.get('sort');
      if (wantValue === null || allowed.indexOf(wantValue) === -1) {
        wantValue = defaultSort;
      }
      if (sortEl.value !== wantValue) sortEl.value = wantValue;
      var labels = (window._localeUI && window._localeUI.sort) || {};
      var needsRebuild = sortEl.options.length !== allowed.length;
      if (!needsRebuild) {
        for (var i = 0; i < allowed.length; i++) {
          if (sortEl.options[i].value !== allowed[i]) { needsRebuild = true; break; }
        }
      }
      if (needsRebuild) {
        sortEl.innerHTML = '';
        allowed.forEach(function(key) {
          var opt = document.createElement('option');
          opt.value = key;
          opt.textContent = labels[key] || key;
          if (key === wantValue) opt.selected = true;
          sortEl.appendChild(opt);
        });
      } else {
        for (var j = 0; j < allowed.length; j++) {
          sortEl.options[j].textContent = labels[allowed[j]] || allowed[j];
        }
      }
    }
  }

  function cleanModeSwitched(url) {
    var raw = url.searchParams.get('mode_switched');
    if (!raw) return;
    var parts = raw.split(',').filter(Boolean);
    var changed = false;

    var dimCount = 0;
    window._dimensionSymbols.forEach(function(d) {
      var hasVal = ['eq','geq','leq'].some(function(op) {
        return url.searchParams.get(d + '_' + op) !== null;
      });
      if (hasVal) dimCount++;
    });
    if (dimCount < 2) { var idx = parts.indexOf('dim'); if (idx !== -1) { parts.splice(idx, 1); changed = true; } }

    var qtyParam = url.searchParams.get('qty');
    var qtyCount = qtyParam ? qtyParam.split(',').length : 0;
    if (qtyCount < 2) {
      ['fml'].forEach(function(k) { var idx; while ((idx = parts.indexOf(k)) !== -1) { parts.splice(idx, 1); changed = true; } });
    }

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
    var url = new URL(window.location);
    var switched = (url.searchParams.get('mode_switched') || '').split(',').filter(Boolean);
    var idx = switched.indexOf('fml');
    if (idx !== -1) switched.splice(idx, 1);
    else switched.push('fml');
    if (switched.length) url.searchParams.set('mode_switched', switched.join(','));
    else url.searchParams.delete('mode_switched');
    fetchContent(url.pathname + url.search, true);
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
      if (typeof katex === 'undefined') return text;
      try { return katex.renderToString(text, {displayMode: false, throwOnError: false}); }
      catch(e) { return text; }
    };

    window.renderQtyChips = function() {
      var chipsEl = document.getElementById('qty-chips');
      if (!chipsEl) return;
      var html = '';
      window._qtySelected.forEach(function(qid) {
        var q = allQuantities.find(function(x) { return x.id === qid; });
        var label = q ? (q.symbol || q.name || q.id) : qid;
        var display = window._renderLatex(label);
        html += '<span class="qty-chip" data-qty="' + qid + '">';
        html += display + '<span class="qty-chip-x" data-action="remove-qty-chip" data-qty="' + qid + '"><i data-lucide="x" width="12" height="12"></i></span>';
        html += '</span>';
      });
      chipsEl.innerHTML = html;
      if (typeof lucide !== 'undefined') lucide.createIcons();
    };

    window.renderQtyResults = function(query) {
      var resultsEl = document.getElementById('qty-results');
      if (!resultsEl) return;
      var q = (query || '').toLowerCase().trim();
      var matches = allQuantities.filter(function(item) {
        var name = (item.name || '').toLowerCase();
        var sym = (item.symbol || '').toLowerCase();
        var id = (item.id || '').toLowerCase();
        if (!q) return true;
        if (name.indexOf(q) === -1 && sym.indexOf(q) === -1 && id.indexOf(q) === -1) return false;
        return true;
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
        html += '<div class="qty-result' + (isSel ? ' selected' : '') + '" data-action="add-qty-chip" data-qty="' + item.id + '" tabindex="0">';
        html += '<span class="qty-result-sym">' + symDisplay + '</span>';
        html += '<span class="qty-result-name">' + nameRaw + '</span>';
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
    if (window._jstree) {
      var selected = window._jstree.get_top_checked(true);
      allIds = selected.map(function(n) { return n.id; });
      var rootIds = window._jstree.get_node('#').children || [];
      allRootSelected = rootIds.length > 0 && allIds.length === rootIds.length && allIds.every(function(id) { return rootIds.indexOf(id) !== -1; });
    }

    var url = new URL(window.location);
    url.searchParams.delete('subbranch');
    url.searchParams.delete('topic');
    url.searchParams.delete('id');
    url.searchParams.delete('exclude_all');

    if (allRootSelected) {
      url.searchParams.delete('ids');
    } else if (allIds.length === 0) {
      url.searchParams.delete('exclude_all');
      url.searchParams.set('ids', '');
    } else {
      url.searchParams.set('ids', allIds.join(','));
    }

    var min = parseInt(document.getElementById('diff-min').value);
    var max = parseInt(document.getElementById('diff-max').value);
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
      var val = row.querySelector('.dim-val').value;
      if (val !== '' && val !== '-' && val !== '+' && val !== '.') {
        var parsed = parseInt(val);
        if (!isNaN(parsed)) url.searchParams.set(d + '_' + op, parsed);
      }
    });

    var qtySelected = window._qtySelected || [];
    if (qtySelected.length > 0) url.searchParams.set('qty', qtySelected.join(','));
    else url.searchParams.delete('qty');

    var sortEl = document.getElementById('sort-select');
    var sortAllowed = (window._availableSorts || []);
    var sortDefault = window._defaultSort || null;
    if (sortEl && sortAllowed.length) {
      if (sortAllowed.indexOf(sortEl.value) === -1) {
        url.searchParams.delete('sort');
      } else if (sortEl.value && sortEl.value !== sortDefault) {
        url.searchParams.set('sort', sortEl.value);
      } else {
        url.searchParams.delete('sort');
      }
    } else {
      url.searchParams.delete('sort');
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
        syncDockPills();
        syncViewTabLinks();
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

  function sidebarState(side) {
    var el = document.getElementById('sidebar-' + side);
    if (!el) return '1'; // default open if element missing
    var v = el.getAttribute('data-open');
    return v === '0' ? '0' : '1';
  }
  function setSidebarState(side, open) {
    var el = document.getElementById('sidebar-' + side);
    if (!el) return;
    el.setAttribute('data-open', open ? '1' : '0');
    var bp = currentBreakpoint();
    el.classList.toggle('collapsed', bp === 'pc' && !open);
    el.classList.toggle('open', bp !== 'pc' && open);
  }
  function isSidebarOpen(side) { return sidebarState(side) === '1'; }

  function openSidebar(side) {
    var el = document.getElementById('sidebar-' + side);
    if (!el) return;
    if (currentBreakpoint() === 'mobile') {
      var other = side === 'left' ? 'right' : 'left';
      if (isSidebarOpen(other)) closeSidebar(other);
    }
    exitSearch();
    setSidebarState(side, true);
    syncBackdrop();
    syncSidebarIcon(side);
    syncDockPills();
  }

  function closeSidebar(side) {
    var el = document.getElementById('sidebar-' + side);
    if (!el) return;
    setSidebarState(side, false);
    syncBackdrop();
    syncSidebarIcon(side);
    syncDockPills();
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
    if (typeof lucide !== 'undefined') lucide.createIcons();
  }

  function hasActiveFilters() {
    var dimHasVal = false;
    document.querySelectorAll('.filter-dim-row .dim-val').forEach(function(input) {
      if (input.value.trim() !== '') dimHasVal = true;
    });
    var qtyHasVal = window._qtySelected && window._qtySelected.length > 0;
    var diffMin = parseInt(document.getElementById('diff-min').value);
    var diffMax = parseInt(document.getElementById('diff-max').value);
    var diffHasVal = diffMin > 1 || diffMax < 10;
    return dimHasVal || qtyHasVal || diffHasVal;
  }
  window.hasActiveFilters = hasActiveFilters;

  function hasTreeFilter() {
    if (!window._jstree) return false;
    var checked = window._jstree.get_checked(true);
    var allNodes = window._jstree.get_node('#').children_d;
    return checked.length < allNodes.length;
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
    syncDockLabels();
  }

  function syncDockLabels() {
    var dock = document.getElementById('mobile-dock');
    if (!dock) return;
    dock.classList.toggle('compact', window.innerWidth < 320);
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

  function dockTogglePanel(side) {
    toggleSidebar(side);
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
            break;
        }
      }, LONG_PRESS_MS);
    });

    document.addEventListener('pointerup', function() {
      if (timer) { clearTimeout(timer); timer = null; }
      pressedEl = null;
    });

    document.addEventListener('pointercancel', function() {
      if (timer) { clearTimeout(timer); timer = null; }
      if (pressedEl) pressedEl._longPressed = false;
      pressedEl = null;
    });

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
  function exitSearch() {
    var topbar = document.querySelector('.topbar');
    topbar.classList.remove('expand-search');
    var input = topbar.querySelector('.topbar-search input');
    if (input) { input.value = ''; input.blur(); }
    syncDockPills();
  }

  function closeAllOverlays() {
    closeSidebar('left');
    closeSidebar('right');
  }

  function toggleSettings(e) {
    e.stopPropagation();
    document.getElementById('settings-menu').classList.toggle('open');
  }

  document.addEventListener('click', function(e) {
    var settingsWrap = document.querySelector('.settings-wrap');
    if (settingsWrap && !settingsWrap.contains(e.target)) {
      document.getElementById('settings-menu').classList.remove('open');
    }
    var copyMenu = document.getElementById('formula-copy-menu');
    if (copyMenu && !e.target.closest('.formula-box *') && e.target !== copyMenu && !copyMenu.contains(e.target)) {
      copyMenu.classList.remove('open');
    }
  });

  document.addEventListener('click', function(e) {
    var el = e.target.closest('[data-action]');
    if (!el) return;
    switch (el.getAttribute('data-action')) {
      case 'toggle-sidebar-left': toggleSidebar('left'); break;
      case 'toggle-sidebar-right': toggleSidebar('right'); break;
      case 'exit-search': exitSearch(); break;
      case 'dock-toggle-search': dockToggleSearch(); break;
      case 'toggle-settings': toggleSettings(e); break;
      case 'toggle-copy-menu': toggleCopyMenu(e); break;
      case 'copy-formula-latex': copyFormula('latex'); break;
      case 'copy-formula-unicode': copyFormula('unicode'); break;
      case 'copy-formula-image-png': copyFormula('png'); break;
      case 'copy-formula-image-svg': copyFormula('svg'); break;
      case 'remove-qty-chip': removeQtyChip(el.getAttribute('data-qty')); break;
      case 'add-qty-chip': addQtyChip(el.getAttribute('data-qty')); break;
      case 'close-overlays': closeAllOverlays(); break;
      case 'dock-set-view': dockSetView(el.getAttribute('data-dock-view')); break;
      case 'dock-toggle-panel': dockTogglePanel(el.getAttribute('data-target')); break;
    }
  });
  document.addEventListener('change', function(e) {
    var el = e.target.closest('[data-action]');
    if (!el) return;
    switch (el.getAttribute('data-action')) {
      case 'switch-theme': switchTheme(el.value); break;
      case 'switch-lang': switchLang(el.value); break;
      case 'switch-dim-mode': switchDimMode(el.value); break;
      case 'switch-wait-latex': switchWaitLatex(el.checked); break;
      case 'dim-filter-change': dimFilterChange(); break;
      case 'sort-change': applyFilters(); break;
      case 'set-export-format': document.cookie = 'sf_export_format=' + el.value + '; path=/; max-age=31536000'; break;
    }
  });
  document.addEventListener('input', function(e) {
    var el = e.target.closest('[data-action]');
    if (!el) return;
    switch (el.getAttribute('data-action')) {
      case 'dim-filter-change': dimFilterChange(); break;
      case 'sync-diff': syncDiff(); break;
    }
  });
  document.getElementById('setting-theme').addEventListener('change', function() { switchTheme(this.value); });
  document.getElementById('setting-lang').addEventListener('change', function() { switchLang(this.value); });
  document.getElementById('setting-dim').addEventListener('change', function() { switchDimMode(this.value); });
  document.getElementById('setting-wait-latex').addEventListener('change', function() { switchWaitLatex(this.checked); });

  function switchTheme(theme) {
    var root = document.documentElement;
    if (theme === 'dark') {
      applyDarkTheme();
      localStorage.setItem('sf-theme', 'dark');
    } else if (theme === 'light') {
      applyLightTheme();
      localStorage.setItem('sf-theme', 'light');
    } else {
      localStorage.removeItem('sf-theme');
      root.removeAttribute('data-theme');
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        applyDarkTheme();
      } else {
        applyLightTheme();
      }
    }
  }

  function applyDarkTheme() {
    document.documentElement.setAttribute('data-theme', 'dark');
  }

  function applyLightTheme() {
    document.documentElement.setAttribute('data-theme', 'light');
  }

  (function() {
    var t = localStorage.getItem('sf-theme');
    if (t) {
      switchTheme(t);
      document.getElementById('setting-theme').value = t;
    } else {
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        applyDarkTheme();
      }
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
        if (!localStorage.getItem('sf-theme')) {
          if (e.matches) applyDarkTheme();
          else applyLightTheme();
        }
      });
    }
  })();

  (function() {
    try {
      var cb = document.getElementById('setting-wait-latex');
      if (cb) {
        var val = localStorage.getItem('sf-wait-latex');
        cb.checked = val !== '0';
      }
    } catch(e) {}
  })();

  function switchLang(locale) {
    document.cookie = 'sf_locale=' + locale + '; path=/; max-age=31536000';
    window.location.reload();
  }

  function switchWaitLatex(enabled) {
    var val = enabled ? '1' : '0';
    localStorage.setItem('sf-wait-latex', val);
    document.documentElement.setAttribute('data-wait-latex', val);
  }

  function switchDimMode(mode) {
    document.cookie = 'sf_dim_mode=' + mode + '; path=/; max-age=31536000';
    window.location.reload();
  }

  function syncDiff() {
    var min = document.getElementById('diff-min');
    var max = document.getElementById('diff-max');
    var fill = document.getElementById('diff-fill');
    var v1 = parseInt(min.value), v2 = parseInt(max.value);
    if (v1 > v2) { var tmp = v1; v1 = v2; v2 = tmp; min.value = v1; max.value = v2; }
    document.getElementById('diff-min-val').textContent = v1;
    document.getElementById('diff-max-val').textContent = v2;
    var pct1 = ((v1 - 1) / 9) * 100;
    var pct2 = ((v2 - 1) / 9) * 100;
    fill.style.left = pct1 + '%';
    fill.style.width = (pct2 - pct1) + '%';
  }
  window.syncDiff = syncDiff;
  syncDiff();

  document.getElementById('diff-min').addEventListener('change', applyFilters);
  document.getElementById('diff-max').addEventListener('change', applyFilters);

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
      }
    });
  })();

  (function() {
    var mqTabletUp = window.matchMedia('(min-width: 768px)');
    var mqPcUp = window.matchMedia('(min-width: 1024px)');
    var mqMobile = window.matchMedia('(width < 768px)');

    function syncOnResize() {
      var left = document.getElementById('sidebar-left');
      var right = document.getElementById('sidebar-right');
      if (!left || !right) return;

      document.documentElement.classList.add('suppress-transitions');

      var bp = currentBreakpoint();
      if (bp === 'pc') {
        setSidebarState('left', true);
        setSidebarState('right', true);
      } else if (bp === 'tablet') {
        setSidebarState('left', true);
        setSidebarState('right', false);
      } else {
        setSidebarState('left', false);
        setSidebarState('right', false);
      }

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
    var DRAG_THRESHOLD = 80; // px to commit close
    var startY = 0, currentY = 0, dragging = false, target = null;

    function onDown(e) {
      if (currentBreakpoint() !== 'mobile') return;
      if (e.target.closest('.sidebar-scroll') && e.target.closest('.sidebar-scroll').scrollTop > 0) return;
      var handle = e.currentTarget;
      var side = handle.getAttribute('data-sheet-target');
      var sheet = document.getElementById('sidebar-' + side);
      if (!sheet || !sheet.classList.contains('open')) return;
      dragging = true;
      target = sheet;
      startY = e.clientY || (e.touches && e.touches[0].clientY) || 0;
      currentY = startY;
      sheet.style.transition = 'none';
    }
    function onMove(e) {
      if (!dragging || !target) return;
      var y = e.clientY || (e.touches && e.touches[0].clientY) || 0;
      currentY = y;
      var dy = Math.max(0, y - startY);
      target.style.transform = 'translateY(' + dy + 'px)';
    }
    function onUp() {
      if (!dragging || !target) return;
      var dy = Math.max(0, currentY - startY);
      target.style.transform = '';
      target.style.transition = '';
      if (dy > DRAG_THRESHOLD) {
        var side = target.id === 'sidebar-left' ? 'left' : 'right';
        setSidebarState(side, false);
        syncBackdrop();
        syncSidebarIcon(side);
        syncDockPills();
      }
      dragging = false;
      target = null;
    }
    document.querySelectorAll('.sheet-handle').forEach(function(h) {
      h.addEventListener('pointerdown', onDown);
      window.addEventListener('pointermove', onMove);
      window.addEventListener('pointerup', onUp);
      window.addEventListener('pointercancel', onUp);
    });
  })();

  if (typeof lucide !== 'undefined') lucide.createIcons();
  syncSidebarIcon('left');
  syncSidebarIcon('right');
  document.documentElement.classList.remove('suppress-transitions');

  function restoreTreeFromUrl() {
    if (!window._jstree) return;
    var url = new URL(window.location);
    var idsParam = url.searchParams.get('ids');
    var excludeAll = url.searchParams.get('exclude_all') === '1';
    var hasIds = idsParam !== null && idsParam !== '';
    window._restoringFilters = true;
    window._jstree.uncheck_all();
    if (excludeAll) {
    } else if (idsParam === null) {
      window._jstree.check_all();
    } else if (!hasIds) {
    } else {
      window._jstree.check_node(idsParam.split(','));
    }
    window._restoringFilters = false;
    syncUndeterminedVisibility();
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

    if (typeof renderQtyChips === 'function') {
      var qtyParam = url.searchParams.get('qty');
      window._qtySelected = qtyParam ? qtyParam.split(',') : [];
      renderQtyChips();
      var qr = document.getElementById('qty-results');
      if (qr) qr.classList.remove('open');
    }

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
    if (typeof restoreTreeFromUrl === 'function') restoreTreeFromUrl();
    syncFilterStates();
  }
  window.restoreAllFromUrl = restoreAllFromUrl;
  restoreFiltersFromUrl();
  syncFilterStates();
  window._initLatexObserver = function() {
    if (typeof katex !== 'undefined') observeLatexIn(document.querySelector('#main-content'));
  };
  syncDockPills();
  updateOverflowPadding();
  window.addEventListener('resize', updateOverflowPadding);

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
    } else if (fmt === 'png') {
      var url = 'https://latex.codecogs.com/png.latex?' + encodeURIComponent('\\dpi{3000}' + tex);
      doCopy = fetch(url).then(function(r) { return r.blob(); }).then(function(blob) {
        return navigator.clipboard.write([new ClipboardItem({'image/png': blob})]);
      });
    } else if (fmt === 'svg') {
      var url = 'https://latex.codecogs.com/svg.latex?' + encodeURIComponent(tex);
      doCopy = fetch(url).then(function(r) { return r.blob(); }).then(function(blob) {
        return navigator.clipboard.write([new ClipboardItem({'image/svg+xml': blob})]);
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
            div.innerHTML = '<span>' + s.heading + '</span><span class="ss-kind">' + s.kind + '</span>';
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
        var q = searchInput ? encodeURIComponent(searchInput.value.trim()) : '';
        var url = q ? '/search?q=' + q : '/search';
        navigateTo(url);
      });
    }

    function navigateTo(url, isPop) {
      if (!isPop && window.location.pathname + window.location.search === url) return;
      var si = document.querySelector('.topbar-search input[name="q"]');
      if (si) si.value = '';
      var qs = document.getElementById('qty-search');
      if (qs) qs.value = '';
      fetch(url).then(function(r) { if (!r.ok) { window.location.href = url; return null; } return r.text(); }).then(function(html) {
        if (!html) return;
        var doc = new DOMParser().parseFromString(html, 'text/html');
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
        var isFormulas = url.indexOf('/quantities') === -1 && url.indexOf('/quantity/') === -1 && url.indexOf('/unit/') === -1;
        var isSearch = url.indexOf('/search') !== -1;
        document.querySelectorAll('.view-tab').forEach(function(t) {
          if (isSearch) {
            t.classList.remove('active');
          } else {
            t.classList.toggle('active', isFormulas ? t.getAttribute('href').indexOf('formulas') !== -1 : t.getAttribute('href').indexOf('quantities') !== -1);
          }
        });
        renderMathInContent();
        if (typeof lucide !== 'undefined') lucide.createIcons();
        restoreAllFromUrl();
        updateOverflowPadding();
        syncDockPills();
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
