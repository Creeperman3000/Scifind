/* eslint-disable no-undef */

(function() {
  'use strict';
  function $(id) { return window.SFUtils.byId(id); }
  function $$(sel, root) { return window.SFUtils.bySel(sel, root); }
  function showToast(message, type) {
    var toastEl = document.createElement('div');
    toastEl.className = 'toast ' + (type || 'success');
    toastEl.textContent = message;
    $('toast-container').appendChild(toastEl);
    setTimeout(function() { toastEl.style.opacity = '0'; toastEl.style.transition = 'opacity var(--dur-slow)'; setTimeout(function() { toastEl.remove(); }, 300); }, 4000);
  }
  window.showToast = showToast;
  function refreshIcons() { if (typeof lucide !== 'undefined') lucide.createIcons(); }
  window.refreshIcons = refreshIcons;
  function setCookie(name, value) { document.cookie = name + '=' + value + '; path=/; max-age=31536000'; }

  function dimValInputs() { return $$('.filter-dim-row .dim-val'); }
  function dimVals() { return dimValInputs().map(function(input) { return input.value.trim(); }); }
  /* A dim field counts as set only if it resolves to an integer — this
     keeps half-typed expressions like "-" from looking like a filter. */
  function dimResolved(v) { return evalDimExpr(v) !== null; }
  /* Shared with filters.js / detail.js (split from single-file app.js):
     keep local bindings and mirror onto window. */
  window.dimValInputs = dimValInputs;
  window.dimVals = dimVals;
  window.dimResolved = dimResolved;

  /* Integer expression evaluator for dim fields (no eval()). */
  function evalDimExpr(raw) {
    var s = String(raw == null ? '' : raw).replace(/\s+/g, '');
    if (!s || !/^[-+*/%^().0-9]+$/.test(s)) return null;
    var i = 0;
    function peek() { return s[i]; }
    function fail() { throw new Error('bad'); }
    function expr() {
      var v = term();
      while (peek() === '+' || peek() === '-') { var op = s[i++]; var r = term(); v = op === '+' ? v + r : v - r; }
      return v;
    }
    function term() {
      var v = power();
      while (peek() === '*' || peek() === '/' || peek() === '%') {
        var op = s[i++]; var r = power();
        if ((op === '/' || op === '%') && r === 0) fail();
        v = op === '*' ? v * r : (op === '/' ? Math.trunc(v / r) : v % r);
      }
      return v;
    }
    function power() {
      var base = unary();
      return peek() === '^' ? (i++, Math.round(Math.pow(base, power()))) : base;
    }
    function unary() {
      if (peek() === '+') { i++; return +unary(); }
      if (peek() === '-') { i++; return -unary(); }
      return atom();
    }
    function atom() {
      if (peek() === '(') { i++; var v = expr(); if (peek() !== ')') fail(); i++; return v; }
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
  window.evalDimExpr = evalDimExpr;

  /* Commit evaluated results into the fields on blur/Enter so the user
     sees what the filter actually applied. */
  function resolveDimExprs() {
    dimValInputs().forEach(function(input) {
      var resolved = evalDimExpr(input.value);
      if (resolved !== null && String(input.value.trim()) !== String(resolved)) input.value = resolved;
    });
  }
  function replayClass(el, cls) { el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); }
  window.replayClass = replayClass;

  function syncSearchCancel() {
    var wrap = document.querySelector('.search-input-wrap');
    var input = document.querySelector('.topbar-search input[name="q"]');
    if (wrap && input) wrap.classList.toggle('has-text', input.value.length > 0);
  }
  window.syncSearchCancel = syncSearchCancel;

  function updateOverflowPadding() {
    $$('.sidebar-scroll').forEach(function(el) {
      var inner = el.querySelector('.sidebar-inner');
      if (!inner) return;
      var extraPad = parseFloat(getComputedStyle(inner).paddingBottom) || 0;
      el.classList.toggle('no-overflow', inner.scrollHeight - extraPad <= el.clientHeight);
    });
    var main = document.querySelector('.main');
    if (main) {
      /* Use the real spacer height so mobile doesn't hide bottom padding eagerly. */
      var spacer = main.classList.contains('no-overflow') ? 0
        : (parseFloat(getComputedStyle(main, '::after').height) || 0);
      main.classList.toggle('no-overflow', main.scrollHeight - spacer <= main.clientHeight);
    }
  }

  /* Content height changes after the fact (KaTeX renders), so
     re-check the overflow padding whenever it does. */
  var _sidebarWidthAnim = false; // true while a sidebar width transition runs
  (function() {
    if (typeof ResizeObserver === 'undefined') return;
    var raf = null;
    var ro = new ResizeObserver(function() {
      if (_sidebarWidthAnim || raf) return;
      raf = requestAnimationFrame(function() { raf = null; updateOverflowPadding(); updateDimNameFits(); });
    });
    ['.main-inner', '.sidebar-inner'].forEach(function(sel) {
      $$(sel).forEach(function(el) { ro.observe(el); });
    });
  })();

  /* Hide dim-name labels when ANY row lacks room (all-or-nothing keeps
     columns aligned). Hysteresis stops flicker at the threshold. */
  var _dimNameState = { hidden: null };
  var HYSTERESIS_PX = 8;
  function naturalWidth(name) {
    var prev = name.getAttribute('style') || '';
    name.style.position = 'absolute';
    name.style.visibility = 'hidden';
    name.style.whiteSpace = 'nowrap';
    name.style.flex = '0 0 auto';
    var w = name.offsetWidth;
    name.setAttribute('style', prev);
    return w;
  }
  function updateDimNameFits() {
    /* At most one layout pass per frame + 150ms trailing. */
    var now = Date.now(), wait = 150 - (now - (updateDimNameFits._last || 0));
    if (updateDimNameFits._raf) return;
    if (wait > 0) {
      if (!updateDimNameFits._timer) updateDimNameFits._timer = setTimeout(function() {
        updateDimNameFits._timer = null; updateDimNameFits._last = Date.now(); _updateDimNameFitsInner();
      }, wait);
      return;
    }
    updateDimNameFits._raf = requestAnimationFrame(function() {
      updateDimNameFits._raf = null; updateDimNameFits._last = Date.now(); _updateDimNameFitsInner();
    });
  }
  function _updateDimNameFitsInner() {
    var rows = $$('.filter-dim-row');
    if (!rows.length) return;
    /* Un-hide first: .no-dim-name uses display:none which measures as 0. */
    if (rows[0].classList.contains('no-dim-name')) rows.forEach(function(r) { r.classList.remove('no-dim-name'); });
    var anyOverflow = false, minSlack = Infinity;
    rows.forEach(function(row) {
      var name = row.querySelector('.dim-name');
      if (!name) return;
      var fixed = 0;
      $$(':scope > *', row).forEach(function(el) { if (el !== name) fixed += el.getBoundingClientRect().width; });
      var style = getComputedStyle(row);
      fixed += (parseFloat(style.columnGap || style.gap) || 0) * (row.children.length - 1);
      var slack = row.clientWidth - fixed - naturalWidth(name);
      if (slack < 0) anyOverflow = true;
      if (slack < minSlack) minSlack = slack;
    });
    var shouldHide = _dimNameState.hidden === null ? anyOverflow
      : _dimNameState.hidden ? !(minSlack >= HYSTERESIS_PX) : anyOverflow;
    _dimNameState.hidden = shouldHide;
    rows.forEach(function(row) { row.classList.toggle('no-dim-name', shouldHide); });
  }

  function renderLatexEl(el) {
    if (!el || !el.parentNode || typeof katex === 'undefined') return;
    var src = el.getAttribute('data-latex');
    if (src == null || src === '') {
      el.classList.remove('latex-observe');
      return;
    }
    try {
      var fit = el.classList.contains('const-value');
      katex.render(src, el, {
        displayMode: el.classList.contains('formula-eqn'),
        throwOnError: false,
        macros: window._KATEX_MACROS || {},
        strict: fit ? false : undefined,
        trust: function(ctx) { return ctx.command === '\\htmlClass'; }
      });
      el.removeAttribute('data-latex');
      el.classList.remove('latex-observe');
      if (fit) recheckConstantValues();
    } catch (e) { /* leave for retry */ }
  }

  function renderLatexIn(el) {
    if (!el || typeof katex === 'undefined') return;
    el.querySelectorAll('.latex-observe').forEach(renderLatexEl);
  }
  window.renderLatexEl = renderLatexEl;
  window.renderLatexIn = renderLatexIn;

  function renderMathInContent(root) {
    root = root || document.querySelector('#main-content');
    if (!root) return;
    if (typeof katex !== 'undefined') renderLatexIn(root);
    if (typeof renderMathInElement === 'function') {
      try { renderMathInElement(root, { delimiters: [{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}], macros: window._KATEX_MACROS || {} }); } catch(e) {}
    }
  }
  window.renderMathInContent = renderMathInContent;

  /* Run fn now if KaTeX already loaded, else once .katex-ready lands. */
  function onKatexReady(fn) {
    if (typeof katex !== 'undefined' || document.documentElement.classList.contains('katex-ready')) { fn(); return; }
    var mo = new MutationObserver(function() {
      if (document.documentElement.classList.contains('katex-ready')) { mo.disconnect(); fn(); }
    });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
  }
  window.onKatexReady = onKatexReady;

  var _pendingFetch = null;

  /* Post-swap UI sync shared by every SPA navigation and first load. */
  function syncContent(url) {
    renderMathInContent();
    refreshIcons();
    restoreAllFromUrl();
    updateOverflowPadding();
    updateDimNameFits();
    syncDockPills();
    syncViewTabLinks();
    if (!url) return;
    var want = url.indexOf('/search') !== -1 ? '' : (isFormulasView() ? 'formulas' : 'quantities');
    $$('.view-tab').forEach(function(t) {
      t.classList.toggle('active', !!want && (t.getAttribute('href') || '').indexOf(want) !== -1);
    });
  }

  function syncPageStyles(doc) {
    var want = {};
    $$('link[rel="stylesheet"]', doc.head).forEach(function(l) { want[l.getAttribute('href')] = true; });
    $$('link[rel="stylesheet"]', document.head).forEach(function(l) {
      if (want[l.getAttribute('href')]) delete want[l.getAttribute('href')];
      else l.remove();
    });
    Object.keys(want).forEach(function(href) {
      var l = document.createElement('link');
      l.rel = 'stylesheet'; l.href = href;
      document.head.appendChild(l);
    });
  }

  /* Single SPA page loader: aborts in-flight loads so rapid filter drags can't race. */
  function reexecScripts(dst) {
    /* Re-execute real JS only; leave data blocks (units table payload) untouched. */
    $$('script', dst).forEach(function(oldScript) {
      var t = (oldScript.getAttribute('type') || '').toLowerCase();
      if (t && ['text/javascript', 'application/javascript', 'module'].indexOf(t) === -1) return;
      var s = document.createElement('script');
      if (oldScript.src) s.src = oldScript.src;
      else s.textContent = oldScript.textContent;
      oldScript.parentNode.replaceChild(s, oldScript);
    });
  }
  /* /create hijacks #sidebar-left-inner with the token picker; restore the
     filter sidebar from the fetched page when navigating away, then
     rebind its element listeners (they were attached to replaced nodes). */
  function restoreCreateSidebar(doc) {
    ['sidebar-left-inner'].forEach(function(id) {
      var fresh = doc.getElementById(id), cur = document.getElementById(id);
      if (fresh && cur && cur.innerHTML !== fresh.innerHTML) cur.innerHTML = fresh.innerHTML;
    });
    /* Drop morph controls bound to detached nodes. */
    window._morphSelects = (window._morphSelects || []).filter(function(ctrl) {
      return document.contains(ctrl.menu);
    });
    if (typeof window._bindSidebarLeft === 'function') window._bindSidebarLeft();
    var sortMenu = $('sort-menu'), sortTrigger = $('sort-trigger');
    if (sortMenu && sortTrigger && typeof window._morphSelect === 'function') {
      window._morphSelect(sortTrigger, sortMenu).sync =
        function() { window._renderSortMenu(sortMenu, sortMenu.dataset.value); };
    }
    if (typeof window.initCSelects === 'function') window.initCSelects();
    renderMathInContent(document.getElementById('sidebar-left-inner'));
  }
  function loadPage(url, push) {
    if (_pendingFetch) _pendingFetch.abort();
    var controller = new AbortController();
    _pendingFetch = controller;
    function done() { if (_pendingFetch === controller) _pendingFetch = null; }
    fetch(url, { signal: controller.signal }).then(function(r) {
      if (!r.ok) { window.location.href = url; return null; }
      return r.text();
    }).then(function(html) {
      if (!html) return;
      var doc = new DOMParser().parseFromString(html, 'text/html');
      var newContent = doc.getElementById('main-content');
      if (!newContent) { window.location.href = url; return; }
      syncPageStyles(doc);
      var newTitle = doc.querySelector('title');
      if (newTitle) document.title = newTitle.textContent;
      var dst = $('main-content');
      dst.innerHTML = newContent.innerHTML;
      reexecScripts(dst);
      dst.scrollTop = 0;
      try {
        var fromCreate = window.location.pathname === '/create';
        var toPath = new URL(url, window.location.origin).pathname;
        if (fromCreate && toPath !== '/create') restoreCreateSidebar(doc);
      } catch (e) {}
      if (push && !(window.history.state && window.history.state.url === url)) history.pushState({url: url}, '', url);
      syncContent(url);
    }).catch(function(err) {
      if (!err || err.name !== 'AbortError') window.location.href = url;
    }).finally(done);
  }
  window.loadPage = loadPage;

  function navigateTo(url, isPop) {
    if (!isPop && window.location.pathname + window.location.search === url) return;
    /* Keep the query visible on search results; clear it when navigating away. */
    var si = document.querySelector('.topbar-search input[name="q"]');
    if (si) {
      var target = new URL(url, window.location.origin);
      si.value = target.pathname === '/search' ? (target.searchParams.get('q') || '') : '';
      syncSearchCancel();
    }
    var qs = $('qty-search');
    if (qs) qs.value = '';
    loadPage(url, !isPop);
  }
  window._navigateTo = navigateTo;

  /* Preserve current filter params across SPA link clicks (except q,
     which only belongs to /search, and list paging, which always
     restarts from the first chunk); link params win on conflict. */
  function mergeLinkQs(href) {
    var parts = href.split('?');
    var params = new URLSearchParams(window.location.search);
    window.SFUtils.stripSearchParam(params, false);
    window.SFUtils.stripPagingParams(params);
    if (parts[1]) new URLSearchParams(parts[1]).forEach(function(v, k) {
      if (k === 'page' || k === 'per_page') return;
      params.set(k, v);
    });
    var qs = params.toString();
    return parts[0] + (qs ? '?' + qs : '');
  }

  /* Address bar untouched, so a reload restarts from chunk one. */
  function loadMoreChunk(btn) {
    if (!btn || btn.dataset.loading) return;
    var more_bar = btn.closest('[data-load-more]');
    var list_container = document.querySelector('[data-list-container]');
    if (!more_bar || !list_container) return;
    btn.dataset.loading = '1';
    window.SFApi.getText(btn.getAttribute('href')).then(function(html) {
      var doc = new DOMParser().parseFromString(html, 'text/html');
      var items = doc.querySelector('[data-list-container]');
      if (items) list_container.insertAdjacentHTML('beforeend', items.innerHTML);
      var next = doc.querySelector('[data-load-more]');
      if (next) more_bar.innerHTML = next.innerHTML;
      else btn.remove();
      renderLatexIn(list_container);
      refreshIcons();
      updateOverflowPadding();
    }).catch(function() { delete btn.dataset.loading; });
  }

  (function() {
    var searchForm = document.querySelector('.topbar-search form');
    var searchInput = searchForm ? searchForm.querySelector('input[name="q"]') : null;
    var suggestionsEl = $('search-suggestions');
    var suggestHighlight = -1, suggestItems = [], _suggestController = null;

    function closeSuggestions() {
      suggestItems = [];
      if (suggestionsEl) { suggestionsEl.classList.remove('open'); suggestionsEl.innerHTML = ''; }
      suggestHighlight = -1;
    }
    function goSuggestion(suggestion) {
      closeSuggestions();
      searchInput.value = suggestion.heading;
      if (searchInput) searchInput.blur();
      navigateTo('/' + suggestion.kind + '/' + suggestion.id);
    }
    function fetchSuggestions(q) {
      if (!suggestionsEl) return;
      if (!q) { closeSuggestions(); return; }
      if (_suggestController) _suggestController.abort();
      var ctrl = _suggestController = new AbortController();
      window.SFApi.getJSON('/api/search-suggestions?q=' + encodeURIComponent(q), { signal: ctrl.signal })
        .then(function(data) { if (!ctrl.signal.aborted) renderSuggestions(data); })
        .catch(function(err) { if (!err || err.name !== 'AbortError') closeSuggestions(); });
    }
    function renderSuggestions(data) {
      closeSuggestions();
      suggestItems = data.suggestions || [];
      if (!suggestItems.length || !suggestionsEl) return;
      var esc = window.SFUtils.escapeHtml;
      suggestionsEl.innerHTML = suggestItems.map(function(s, i) {
        return '<div class="search-suggestion" tabindex="-1" data-idx="' + i + '"><span>' + esc(s.heading) + '</span><span class="ss-kind">' + esc(s.kind) + '</span></div>';
      }).join('');
      suggestionsEl.classList.add('open');
    }

    function moveHighlight(items, dir) {
      suggestHighlight = dir > 0 ? Math.min(suggestHighlight + 1, items.length - 1) : Math.max(suggestHighlight - 1, -1);
      items.forEach(function(el, i) { el.classList.toggle('highlighted', i === suggestHighlight); });
      if (suggestHighlight >= 0) items[suggestHighlight].scrollIntoView({ block: 'nearest' });
    }

    if (searchInput && suggestionsEl) {
      var debouncedSuggest = window.SFUtils.debounce(function() { fetchSuggestions(searchInput.value.trim()); }, 150);
      searchInput.addEventListener('input', function() { syncSearchCancel(); debouncedSuggest(); });
      searchInput.addEventListener('keydown', function(e) {
        var items = suggestionsEl.querySelectorAll('.search-suggestion');
        if (!suggestionsEl.classList.contains('open') || !items.length) return;
        if (e.key === 'ArrowDown') { e.preventDefault(); moveHighlight(items, 1); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); moveHighlight(items, -1); }
        else if (e.key === 'Enter' && suggestHighlight >= 0) { e.preventDefault(); items[suggestHighlight].click(); }
      });
      searchInput.addEventListener('blur', function() { setTimeout(function() { suggestionsEl.classList.remove('open'); }, 200); });
      searchInput.addEventListener('focus', function() { if (searchInput.value.trim()) fetchSuggestions(searchInput.value.trim()); });
      suggestionsEl.addEventListener('click', function(e) {
        var row = e.target.closest('.search-suggestion');
        var s = row && suggestItems[+row.getAttribute('data-idx')];
        if (s) goSuggestion(s);
      });
    }

    if (searchForm) {
      searchForm.addEventListener('submit', function(e) {
        e.preventDefault();
        if (suggestionsEl) suggestionsEl.classList.remove('open');
        if (searchInput) searchInput.blur();
        var q = searchInput ? encodeURIComponent(searchInput.value.trim()) : '';
        navigateTo(q ? '/search?q=' + q : '/search');
      });
    }

    document.body.addEventListener('click', function(e) {
      var moreBtn = e.target.closest('[data-load-more-btn]');
      if (moreBtn) { e.preventDefault(); loadMoreChunk(moreBtn); return; }
      var link = e.target.closest('a');
      if (!link) return;
      var href = link.getAttribute('href');
      if (!href || /^(https?:)?\/\/|^#|^mailto:|^javascript:/.test(href) ||
          link.hasAttribute('download') || link.getAttribute('target') === '_blank' ||
          link.hasAttribute('data-spa-full')) return; /* data-spa-full opts out (full reload) */
      if (e.button === 1 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      navigateTo(href === '/' ? '/formulas' : mergeLinkQs(href));
    });
    window.addEventListener('popstate', function() { navigateTo(window.location.href, true); });
  })();

  /* Restore helpers live at IIFE top level (not nested in initPage) so
     syncContent() can reuse them on every SPA swap. */
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
      if (excludeAll || idsParam === '') return;
      if (idsParam === null) roots.forEach(function(node) { _topicTree.checkNode(node, true); });
      else idsParam.split(',').forEach(function(id) {
        var node = _topicTree.getNodeById(id);
        if (node) _topicTree.checkNode(node, true);
      });
    } finally {
      window._restoringFilters = false;
    }
  }

  function restoreFiltersFromUrl() {
    var url = new URL(window.location);
    window._dimensionSymbols.forEach(function(d) {
      var row = document.querySelector('.filter-dim-row[data-dim="' + d + '"]');
      if (!row) return;
      var foundOp = 'eq', foundVal = null;
      ['eq', 'geq', 'leq'].forEach(function(op) {
        var v = url.searchParams.get(d + '_' + op);
        if (v !== null) { foundOp = op; foundVal = v; }
      });
      row.querySelector('.dim-op').value = foundOp;
      row.querySelector('.dim-val').value = (foundVal !== null ? foundVal : '');
    });

    window._qtySelected = (url.searchParams.get('qty') || '').split(',').filter(Boolean);
    window.renderQtyChips();
    var qr = $('qty-results');
    if (qr) qr.classList.remove('open');

    var dMin = parseInt(url.searchParams.get('diff_min')), dMax = parseInt(url.searchParams.get('diff_max'));
    var dMinEl = $('diff-min'), dMaxEl = $('diff-max');
    if (!isNaN(dMin) && dMinEl) dMinEl.value = dMin;
    if (!isNaN(dMax) && dMaxEl) dMaxEl.value = dMax;
    syncDiff();
  }

  function restoreAllFromUrl() {
    restoreFiltersFromUrl();
    restoreTreeFromUrl();
    syncFilterStates();
  }

  function initPage() {
    refreshIcons();
    initCSelects();
    initUnitsTables();
    syncSearchCancel();
    var sortMenu = $('sort-menu'), sortTrigger = $('sort-trigger');
    if (sortMenu && sortTrigger) {
      window._morphSelect(sortTrigger, sortMenu).sync =
        function() { window._renderSortMenu(sortMenu, sortMenu.dataset.value); };
    }
    syncSidebarIcon('left');
    syncSidebarIcon('right');
    document.documentElement.classList.remove('suppress-transitions');
    syncContent(window.location.href);

    layoutConstantValues();
    var mainContentEl = $('main-content');
    if (mainContentEl) {
      new MutationObserver(function() { recheckConstantValues(); })
        .observe(mainContentEl, { childList: true });
    }
    /* KaTeX re-flows the dim-symbol after auto-render; re-measure once done. */
    onKatexReady(function() {
      renderMathInContent();
      recheckConstantValues();
      requestAnimationFrame(function() {
        requestAnimationFrame(function() { updateDimNameFits(); });
      });
    });
    window.addEventListener('resize', function() {
      updateOverflowPadding();
      updateDimNameFits();
      layoutConstantValues();
    });
  }
  window._bootTopicTree = function() {
    try {
      if (typeof ensureTopicTree === 'function') ensureTopicTree();
      if (typeof restoreAllFromUrl === 'function') restoreAllFromUrl();
      else {
        if (typeof restoreTreeFromUrl === 'function') restoreTreeFromUrl();
        if (typeof syncFilterStates === 'function') syncFilterStates();
      }
    } catch (e) {}
    try { refreshIcons(); } catch (e) {}
  };

  initPage();
  if (document.readyState === 'complete') window._bootTopicTree();
  else window.addEventListener('load', window._bootTopicTree);

  function currentBreakpoint() {
    var w = window.innerWidth;
    return w >= 1024 ? 'pc' : w >= 768 ? 'tablet' : 'mobile';
  }

  function isSidebarOpen(side) { return window.SFUtils.sidebarOpenAttr(side); }
  function setSidebarState(side, open) {
    var el = $('sidebar-' + side);
    if (!el) return;
    el.setAttribute('data-open', open ? '1' : '0');
    var bp = currentBreakpoint();
    /* PC: both sidebars collapse in-flow. Tablet: left still collapses
       in-flow, right is a fixed overlay. Mobile: both are bottom sheets. */
    var isOverlay = bp === 'mobile' || (bp === 'tablet' && side === 'right');
    var isCollapsible = bp === 'pc' || (bp === 'tablet' && side === 'left');
    el.classList.toggle('collapsed', isCollapsible && !open);
    el.classList.toggle('open', isOverlay && open);
    // Pause RO recalcs during the width animation; one recalc afterwards.
    if (isCollapsible && !document.documentElement.classList.contains('suppress-transitions')) {
      _sidebarWidthAnim = true;
      clearTimeout(setSidebarState._t);
      setSidebarState._t = setTimeout(function() { _sidebarWidthAnim = false; updateOverflowPadding(); updateDimNameFits(); }, 230);
    }
  }

  function syncAfterSidebarToggle(side) {
    syncBackdrop();
    syncSidebarIcon(side);
    syncDockPills();
  }

  function setSidebarOpen(side, open) {
    var el = $('sidebar-' + side);
    if (!el) return;
    if (open && currentBreakpoint() === 'mobile') {
      var other = side === 'left' ? 'right' : 'left';
      if (isSidebarOpen(other)) setSidebarOpen(other, false);
    }
    if (open) exitSearch();
    setSidebarState(side, open);
    syncAfterSidebarToggle(side);
  }
  function toggleSidebar(side) { setSidebarOpen(side, !isSidebarOpen(side)); }
  window.toggleSidebar = toggleSidebar;
  function closeSidebar(side) { setSidebarOpen(side, false); }

  /* Shared overlay closer for the shortcuts Esc chain. */
  function closeAllOverlays() {
    var closed = false;
    function shut(el) { if (el && el.classList.contains('open')) { el.classList.remove('open'); closed = true; } }
    (window._morphSelects || []).forEach(function(ctrl) {
      if (ctrl.isOpen()) { ctrl.close(); ctrl.trigger.focus(); closed = true; }
    });
    ['formula-sql-modal', 'sql-modal', 'search-suggestions', 'qty-results', 'formula-copy-menu', 'settings-menu'].forEach(function(id) { shut($(id)); });
    return closed;
  }
  window._closeOverlays = closeAllOverlays;

  function syncBackdrop() {
    var bp = $('sidebar-backdrop');
    if (!bp) return;
    var layoutBp = currentBreakpoint();
    var anyOpen = layoutBp === 'tablet' ? isSidebarOpen('right')
      : isSidebarOpen('left') || isSidebarOpen('right');
    bp.classList.toggle('open', anyOpen && layoutBp !== 'pc');
  }

  function syncSidebarIcon(side) {
    var el = $('sidebar-' + side);
    var iconWrap = $(side + '-sidebar-icon');
    if (!el || !iconWrap) return;
    var closed = !isSidebarOpen(side);
    // Pre-rendered in base.html: flip instead of a full lucide scan.
    var openIcon = iconWrap.querySelector('[data-icon-open]'), closeIcon = iconWrap.querySelector('[data-icon-close]');
    if (openIcon && closeIcon) { openIcon.hidden = !closed; closeIcon.hidden = closed; return; }
    iconWrap.innerHTML = '<i data-lucide="panel-' + side + '-' + (closed ? 'open' : 'close') + '" width="18" height="18"></i>';
    refreshIcons();
  }

  function hasActiveFilters() {
    var dMinEl = $('diff-min'), dMaxEl = $('diff-max');
    if (!dMinEl || !dMaxEl) return false;
    var diffMin = parseInt(dMinEl.value), diffMax = parseInt(dMaxEl.value);
    return window.SFUtils.filtersActive(dimVals().map(dimResolved),
      (window._qtySelected && window._qtySelected.length) || 0, diffMin, diffMax);
  }

  function hasTreeFilter() {
    return !!(_topicTree && _topicTreeMode === 'checkbox' && !allRootNodesChecked());
  }

  function syncPills(dock, name, open, active) {
    $$('[data-pill="' + name + '"]', dock).forEach(function(btn) {
      btn.classList.toggle('open', !!open);
      btn.classList.toggle('active', !!active);
    });
  }

  function topbarEl() { return document.querySelector('.topbar'); }
  function searchField() { var tb = topbarEl(); return tb && tb.querySelector('.topbar-search input'); }

  function syncDockPills() {
    var dock = $('mobile-dock');
    if (!dock || dock.offsetParent === null) return;
    var view = isFormulasView() ? 'formulas' : 'quantities';
    var onCreate = window.location.pathname === '/create';
    $$('[data-dock-view]', dock).forEach(function(btn) {
      btn.classList.toggle('active', !onCreate && btn.getAttribute('data-dock-view') === view);
      btn.classList.remove('open');
    });
    syncPills(dock, 'filter', isSidebarOpen('left'), hasActiveFilters());
    syncPills(dock, 'tree', isSidebarOpen('right'), hasTreeFilter());
    var topbar = topbarEl();
    syncPills(dock, 'search', topbar && topbar.classList.contains('expand-search'),
      new URL(window.location).searchParams.has('q'));
  }

  function dockSetView(view) {
    var target = window.SFUtils.viewUrl(view, false);
    if (typeof window._navigateTo === 'function') window._navigateTo(target);
    else window.location.href = target;
  }

  function enterSearch() {
    closeSidebar('left');
    closeSidebar('right');
    var topbar = topbarEl();
    topbar.classList.add('expand-search');
    var input = searchField();
    if (input) input.focus();
    syncDockPills();
  }
  function exitSearch(focusAfter) {
    topbarEl().classList.remove('expand-search');
    var input = searchField();
    if (input) { input.value = ''; input.blur(); }
    syncSearchCancel();
    syncDockPills();
    if (focusAfter && input) input.focus();
  }
  function dockToggleSearch() { topbarEl().classList.contains('expand-search') ? exitSearch() : enterSearch(); }
  /* Long-press pills reset their panel: filter clears dim/qty/diff,
     tree selects all, search strips q. Short taps still toggle. */
  (function() {
    var timer = null, pressedEl = null, LONG_PRESS_MS = 500;
    function longPressAction(pill) {
      pill._longPressed = true;
      var kind = pill.getAttribute('data-pill');
      if (kind === 'filter') ['dim-reset', 'qty-reset', 'diff-reset'].forEach(function(id) { $(id).click(); });
      else if (kind === 'tree') $('tree-select-all').click();
      else if (kind === 'search') {
        var url = new URL(window.location);
        url.searchParams.delete('q');
        loadPage((isFormulasView() ? '/formulas' : '/quantities') + url.search, true);
        exitSearch();
      }
    }
    document.addEventListener('pointerdown', function(e) {
      var pill = e.target.closest('[data-pill]');
      if (!pill) return;
      pressedEl = pill;
      timer = setTimeout(function() { if (pressedEl) longPressAction(pressedEl); }, LONG_PRESS_MS);
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
        e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
      }
    }, true);
  })();

  function toggleSettings(e) {
    e.stopPropagation();
    $('settings-menu').classList.toggle('open');
  }

  /* Controls inside the settings menu must not keep focus (Chromium
     focuses buttons on mousedown; Space would re-trigger e.g. Report). */
  (function() {
    var menu = $('settings-menu');
    if (!menu) return;
    menu.addEventListener('mousedown', function(e) {
      if (e.target.closest('button, a, input, select')) e.preventDefault();
    });
  })();
  function toggleSortMenu(e) {
    e.stopPropagation();
    var menu = $('sort-menu');
    if (menu && menu._morphCtrl) menu._morphCtrl.toggle();
  }

  /* Icon animations: .icon-play added on press, removed on animationend. */
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
    var sortMenu = $('sort-menu');
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
    var labelEl = $('sort-trigger-label');
    if (labelEl) window._bumpLabel(labelEl);
    applyFilters();
  }

  /* The X button clears the input and re-focuses it; q only belongs to
     /search so strip it from the URL too. */
  function exitSearchAction() {
    if (/[?&]q=/.test(window.location.search)) {
      var clean = window.SFUtils.stripQFromUrl(window.location.href);
      if (window.location.pathname === '/search') {
        if (typeof window._navigateTo === 'function') window._navigateTo(clean);
        else window.location.href = clean;
      } else {
        history.replaceState({url: clean}, '', clean);
      }
    }
    exitSearch(true);
  }

  var CLICK_ACTIONS = {
    'toggle-sidebar-left': function() { toggleSidebar('left'); },
    'toggle-sidebar-right': function() { toggleSidebar('right'); },
    'exit-search': exitSearchAction,
    'dock-toggle-search': dockToggleSearch,
    'toggle-settings': toggleSettings,
    'toggle-sort-menu': toggleSortMenu,
    'toggle-copy-menu': toggleCopyMenu,
    'open-formula-sql': function() { var m = $('formula-copy-menu'); if (m) m.classList.remove('open'); var sql = $('formula-sql-modal'); var body = sql && sql.querySelector('.modal-body'); if (body) body.scrollTop = 0; window.SFUtils.setModal('formula-sql-modal', true); },
    'close-formula-sql': function() { window.SFUtils.setModal('formula-sql-modal', false); },
    'open-bug-report': function() { window.open('https://github.com/Creeperman3000/Scifind/issues/new', '_blank'); },
    'sort-pick': function(e, el) { pickSort(el.getAttribute('data-sort')); },
    'copy-formula-latex': function() { copyFormula('latex'); },
    'copy-formula-unicode': function() { copyFormula('unicode'); },
    'copy-formula-image-png': function() { copyFormula('png'); },
    'copy-formula-image-svg': function() { copyFormula('svg'); },
    'copy-formula-sql-export': function(e, el) { window.SFUtils.copySqlBlock(el); },
    'copy-token-sql-export': function(e, el) { window.SFUtils.copySqlBlock(el); },
    'remove-qty-chip': function(e, el) { removeQtyChip(el.getAttribute('data-qty')); },
    'add-qty-chip': function(e, el) { addQtyChip(el.getAttribute('data-qty')); },
    'close-overlays': function() {
      /* Tablet backdrop belongs to the right overlay only; the left
         sidebar stays in-flow and must not collapse with it. */
      if (currentBreakpoint() === 'tablet') { closeSidebar('right'); return; }
      closeSidebar('left'); closeSidebar('right');
    },
    'dock-set-view': function(e, el) { dockSetView(el.getAttribute('data-dock-view')); },
    'dock-toggle-panel': function(e, el) { toggleSidebar(el.getAttribute('data-target')); },
    'toggle-si-prefixes': function(e, el) { toggleSiPrefixes(el); },
    'units-sort': function(e, el) { sortUnitsTable(el); },
    'units-ref-pick': function(e, el) { pickUnitsRef(el); }
  };
  window.SFUtils.registerActions(CLICK_ACTIONS);
  window.SFUtils.registerOverlayCloser(function(e) {
    var settingsWrap = document.querySelector('.settings-wrap');
    if (settingsWrap && !settingsWrap.contains(e.target)) $('settings-menu').classList.remove('open');
    window._morphSelects.forEach(function(ctrl) {
      if (!ctrl.trigger.contains(e.target) && !ctrl.menu.contains(e.target)) ctrl.close();
    });
    var copyMenu = $('formula-copy-menu');
    if (copyMenu && !e.target.closest('.formula-box *') && e.target !== copyMenu && !copyMenu.contains(e.target)) {
      copyMenu.classList.remove('open');
    }
  });
  window.SFUtils.installSingleClickListener();
  var CHANGE_ACTIONS = {
    'switch-theme': switchTheme,
    'switch-lang': function(v) { reloadWithCookie('sf_locale', v); },
    'switch-dim-mode': function(v) { reloadWithCookie('sf_dim_mode', v); },
    'switch-unit-system': function(v) { reloadWithCookie('sf_unit_system', v); },
    'set-export-format': function(v) { setCookie('sf_export_format', v); }
  };
  document.addEventListener('change', function(e) {
    var el = e.target.closest('[data-action]');
    if (!el) return;
    var action = el.getAttribute('data-action');
    if (CHANGE_ACTIONS[action]) { CHANGE_ACTIONS[action](el.value, el); return; }
    if (action === 'dim-filter-change') {
      if (el.classList.contains('dim-val')) resolveDimExprs();
      dimFilterChange();
    }
  });
  document.addEventListener('input', function(e) {
    var el = e.target.closest('[data-action]');
    if (!el) return;
    /* dim value fields apply only on change (Enter/unfocus), not while typing */
    if (el.getAttribute('data-action') === 'dim-filter-change') {
      if (!el.classList.contains('dim-val')) dimFilterChange();
    } else if (el.getAttribute('data-action') === 'sync-diff') syncDiff();
  });

  function prefersDark() { return window.matchMedia('(prefers-color-scheme: dark)').matches; }
  function applyTheme(dark) { document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light'); }

  function switchTheme(theme) {
    var dark = theme === 'dark' ? true : theme === 'light' ? false : prefersDark();
    if (theme === 'dark' || theme === 'light') localStorage.setItem('sf-theme', theme);
    else { localStorage.removeItem('sf-theme'); document.documentElement.removeAttribute('data-theme'); }
    applyTheme(dark);
  }

  (function() {
    var t = localStorage.getItem('sf-theme');
    if (t) { switchTheme(t); var st = $('setting-theme'); if (st) st.value = t; return; }
    if (prefersDark()) applyTheme(true);
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
      if (!localStorage.getItem('sf-theme')) applyTheme(e.matches);
    });
  })();

  function reloadWithCookie(name, value) {
    setCookie(name, value);
    window.location.reload();
  }
  (function() {
    var isResizing = false, currentSide = null, startX = 0, startWidth = 0;
    function sb(side) { return $('sidebar-' + side); }

    ['left', 'right'].forEach(function(side) {
      var handle = $('sidebar-resize-' + side);
      if (!handle) return;
      handle.addEventListener('mousedown', function(e) {
        isResizing = true; currentSide = side;
        startX = e.clientX; startWidth = sb(side).getBoundingClientRect().width;
        document.body.style.cursor = 'col-resize'; document.body.style.userSelect = 'none';
      });
      handle.addEventListener('dblclick', function() {
        var s = sb(side);
        s.style.width = ''; s.style.transition = '';
        s.querySelector('.sidebar-inner').style.width = '';
      });
    });

    document.addEventListener('mousemove', function(e) {
      if (!isResizing) return;
      var delta = currentSide === 'left' ? e.clientX - startX : startX - e.clientX;
      var newWidth = Math.max(180, Math.min(500, startWidth + delta));
      var sidebar = sb(currentSide);
      sidebar.style.width = newWidth + 'px'; sidebar.style.transition = 'none';
      sidebar.querySelector('.sidebar-inner').style.width = newWidth + 'px';
    });

    document.addEventListener('mouseup', function() {
      if (!isResizing) return;
      isResizing = false; currentSide = null;
      document.body.style.cursor = ''; document.body.style.userSelect = '';
      $$('.sidebar').forEach(function(s) { s.style.transition = ''; });
      updateOverflowPadding(); updateDimNameFits();
    });
  })();

  (function() {
    /* Only re-sync when the layout actually changed: the soft keyboard
       fires resizes with unchanged width/breakpoint, which would
       force-close the open bottom sheets. */
    var lastBp = null, lastWidth = null;

    function syncOnResize() {
      if (!$('sidebar-left') || !$('sidebar-right')) return;
      var bp = currentBreakpoint(), w = window.innerWidth;
      if (bp === lastBp && w === lastWidth) return;
      lastBp = bp; lastWidth = w;
      document.documentElement.classList.add('suppress-transitions');
      setSidebarState('left', bp !== 'mobile');
      setSidebarState('right', bp === 'pc');
      syncBackdrop(); syncSidebarIcon('left'); syncSidebarIcon('right'); syncDockPills();
      void document.documentElement.offsetWidth;
      document.documentElement.classList.remove('suppress-transitions');
    }

    ['(min-width: 768px)', '(min-width: 1024px)', '(width < 768px)'].forEach(function(q) {
      var m = window.matchMedia(q);
      if (m.addEventListener) m.addEventListener('change', syncOnResize);
      else m.addListener(syncOnResize);
    });
    window.addEventListener('resize', syncOnResize);
    syncOnResize();
  })();

  /* Mobile bottom-sheet drag: grip or top-of-list content drags down to
     dismiss (25% height or a quick flick); upward motion stays a scroll. */
  (function() {
    var COMMIT_RATIO = 0.25, FLICK_VELOCITY = 0.5, FLICK_MIN_DISTANCE = 24;
    var RUBBER_BAND = 0.15, ENGAGE_DISTANCE = 12;
    var INTERACTIVE = 'button, a, input, select, textarea, label';
    var startY = 0, currentY = 0, lastY = 0, lastT = 0, velocity = 0;
    var dragging = false, target = null, engaged = false, activePointerId = null;

    function engage(sheet) { engaged = true; sheet.style.transition = 'none'; sheet.classList.add('dragging'); }
    function onDown(e) {
      if (dragging || (e.button !== undefined && e.button !== 0) || currentBreakpoint() !== 'mobile') return;
      var t = e.target;
      if (!t || !t.closest) return;
      var sheet = t.closest('.sidebar.left, .sidebar.right');
      if (!sheet || !sheet.classList.contains('open')) return;
      var onHandle = !!t.closest('.sheet-handle');
      if (!onHandle && t.closest(INTERACTIVE)) return;
      var scrollArea = sheet.querySelector('.sidebar-scroll');
      if (!onHandle && (!scrollArea || scrollArea.scrollTop !== 0)) return;
      dragging = true; target = sheet; activePointerId = e.pointerId;
      startY = currentY = lastY = e.clientY; lastT = e.timeStamp; velocity = 0; engaged = false;
      if (onHandle) engage(sheet);
    }
    function onMove(e) {
      if (!dragging || !target || e.pointerId !== activePointerId) return;
      var y = e.clientY, dt = e.timeStamp - lastT;
      if (dt > 0) velocity = 0.6 * ((y - lastY) / dt) + 0.4 * velocity;
      lastY = y; lastT = e.timeStamp; currentY = y;
      var dy = y - startY;
      if (!engaged) {
        if (dy <= ENGAGE_DISTANCE) { if (dy < -ENGAGE_DISTANCE) { dragging = false; target = null; } return; }
        engage(target);
      }
      target.style.transform = 'translateY(' + (dy > 0 ? dy : dy * RUBBER_BAND) + 'px)';
    }
    function settle(sheet, toY) {
      /* Animate from the finger's position; clearing transform would snap back first. */
      sheet.style.transition = 'transform var(--dur-base) var(--ease-in-out)';
      sheet.style.transform = 'translateY(' + toY + 'px)';
      var done = false;
      function cleanup() { if (done) return; done = true; sheet.style.transition = ''; sheet.style.transform = ''; }
      sheet.addEventListener('transitionend', function(ev) { if (ev.propertyName === 'transform') cleanup(); }, { once: true });
      setTimeout(cleanup, 400);
    }
    function onUp(cancelled, e) {
      if (!dragging || !target) return;
      if (e && e.pointerId !== undefined && e.pointerId !== activePointerId) return;
      var sheet = target, side = sheet.id === 'sidebar-left' ? 'left' : 'right';
      var dy = Math.max(0, currentY - startY), wasEngaged = engaged;
      dragging = false; target = null; engaged = false;
      sheet.classList.remove('dragging');
      if (!wasEngaged) return;
      if (!cancelled && (dy > (sheet.offsetHeight || 1) * COMMIT_RATIO || (dy > FLICK_MIN_DISTANCE && velocity > FLICK_VELOCITY))) {
        if (navigator.vibrate) navigator.vibrate(10);
        settle(sheet, (sheet.offsetHeight || 1) + 32);
        setSidebarState(side, false); syncAfterSidebarToggle(side);
      } else settle(sheet, 0);
    }
    $$('.sidebar.left, .sidebar.right').forEach(function(s) { s.addEventListener('pointerdown', onDown); });
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', function(e) { onUp(false, e); });
    window.addEventListener('pointercancel', function(e) { onUp(true, e); });
    document.addEventListener('keydown', function(e) {
      var t = e.target && e.target.closest ? e.target.closest('.sheet-handle') : null;
      if (!t || (e.key !== 'Enter' && e.key !== ' ')) return;
      e.preventDefault();
      var sheet = t.closest('.sidebar.left, .sidebar.right');
      if (!sheet) return;
      setSidebarState(sheet.id === 'sidebar-left' ? 'left' : 'right', false);
      syncAfterSidebarToggle(sheet.id === 'sidebar-left' ? 'left' : 'right');
    });
  })();
})();
