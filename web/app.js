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
  function dimVals() { return dimValInputs().map(function(input) { return input.value.trim(); }); }
  /* A dim field counts as set only if it resolves to an integer — this
     keeps half-typed expressions like "-" from looking like a filter. */
  function dimResolved(v) { return evalDimExpr(v) !== null; }

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

     Hysteresis (HYSTERESIS_PX): once hidden, names stay hidden until
     every name has at least that many pixels of spare room, and vice
     versa once shown. Without it, dragging across the threshold
     flickers the names on every ResizeObserver tick. */
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
      var needsFitLayout = el.classList.contains('const-value');
      var opts = {
        displayMode: display,
        throwOnError: false,
        macros: window._KATEX_MACROS || {},
        trust: function(ctx) { return ctx.command === '\\htmlClass'; }
      };
      if (needsFitLayout) opts.strict = false;
      katex.render(src, el, opts);
      el.removeAttribute('data-latex');
      el.classList.remove('latex-observe');
      if (needsFitLayout) recheckConstantValues();
    } catch (e) { /* leave for retry */ }
  }

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
      });       } catch(e) { /* best-effort: KaTeX auto-render may retry later */ }
    }
  }
  window.renderMathInContent = renderMathInContent;

  /* Run fn now if KaTeX already loaded, else once .katex-ready lands. */
  function onKatexReady(fn) {
    if (typeof katex !== 'undefined' || document.documentElement.classList.contains('katex-ready')) {
      fn();
      return;
    }
    var mo = new MutationObserver(function() {
      if (document.documentElement.classList.contains('katex-ready')) {
        mo.disconnect();
        fn();
      }
    });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
  }

  var _pendingFetch = null;

  /* Post-swap UI sync shared by every SPA navigation (filters, links,
     search): re-render math, restore filter widgets from the URL and
     re-sync pills/tabs/overflow. Also used by initPage() on first load,
     so boot and post-swap stay in step (merged from boot.js). */
  function syncContent(url) {
    renderMathInContent();
    refreshIcons();
    restoreAllFromUrl();
    updateOverflowPadding();
    updateDimNameFits();
    syncDockPills();
    syncViewTabLinks();
  }
  function afterPageSwap(url) {
    syncContent(url);
    var isSearch = url.indexOf('/search') !== -1;
    var isFormulas = isFormulasView();
    document.querySelectorAll('.view-tab').forEach(function(t) {
      if (isSearch) {
        t.classList.remove('active');
      } else {
        t.classList.toggle('active', isFormulas ? t.getAttribute('href').indexOf('formulas') !== -1 : t.getAttribute('href').indexOf('quantities') !== -1);
      }
    });
  }

  /* Keep <head> stylesheets in step with the target page so SPA
     navigation renders identically to a full load (single base.css
     since create.css was merged; kept for forward-compat). */
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

  /* Single SPA page loader: fetches the target, swaps #main-content and
     re-runs UI sync. Replaces the old filter-only fetchContent and the
     link-only navigateTo body, which duplicated each other. Aborts an
     in-flight load so rapid filter drags can't race. */
  function loadPage(url, push) {
    if (_pendingFetch) _pendingFetch.abort();
    var controller = new AbortController();
    _pendingFetch = controller;
    fetch(url, { signal: controller.signal }).then(function(r) {
      if (!r.ok) { window.location.href = url; return null; }
      return r.text();
    }).then(function(html) {
      if (!html) return;
      var doc = new DOMParser().parseFromString(html, 'text/html');
      syncPageStyles(doc);
      var newTitle = doc.querySelector('title');
      if (newTitle) document.title = newTitle.textContent;
      var newContent = doc.getElementById('main-content');
      if (!newContent) { window.location.href = url; return; }
      var dst = document.getElementById('main-content');
      dst.innerHTML = newContent.innerHTML;
      Array.from(dst.querySelectorAll('script')).forEach(function(oldScript) {
        /* Re-execute real JS only; leave data blocks (units table payload) untouched. */
        var t = (oldScript.getAttribute('type') || '').toLowerCase();
        if (t && t !== 'text/javascript' && t !== 'application/javascript' && t !== 'module') return;
        var newScript = document.createElement('script');
        if (oldScript.src) newScript.src = oldScript.src;
        else newScript.textContent = oldScript.textContent;
        oldScript.parentNode.replaceChild(newScript, oldScript);
      });
      dst.scrollTop = 0;
      if (push && !(window.history.state && window.history.state.url === url)) history.pushState({url: url}, '', url);
      afterPageSwap(url);
    }).catch(function(err) {
      if (err && err.name === 'AbortError') return;
      window.location.href = url;
    }).then(function() { if (_pendingFetch === controller) _pendingFetch = null; });
  }
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
      loadPage(url, !isPop);
    }
    document.body.addEventListener('click', function(e) {
      var link = e.target.closest('a');
      if (!link) return;
      var href = link.getAttribute('href');
      /* data-spa-full opts the link out of SPA navigation (full reload) */
      if (!href || href.startsWith('http') || href.startsWith('//') || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('javascript:') || link.hasAttribute('download') || link.getAttribute('target') === '_blank' || link.hasAttribute('data-spa-full')) return;
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

  /* ---- First-load boot (merged from boot.js; runs once) ----
     One-time widget init + restore-from-URL + observers. Post-swap
     sync reuses syncContent()/afterPageSwap() above. */
  function initPage() {
    refreshIcons();
    initCSelects();
    initUnitsTables();
    syncSearchCancel();
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
    layoutConstantValues();
    var mainContentEl = document.getElementById('main-content');
    if (mainContentEl) {
      new MutationObserver(function() { recheckConstantValues(); })
        .observe(mainContentEl, { childList: true });
    }
    /* KaTeX re-flows the dim-symbol after auto-render; re-measure once it
       has finished so the names show/hide correctly. */
    function recheckAfterKatex() {
      recheckConstantValues();
      requestAnimationFrame(function() {
        requestAnimationFrame(function() { updateDimNameFits(); });
      });
    }
    onKatexReady(recheckAfterKatex);
    window.addEventListener('resize', function() {
      updateOverflowPadding();
      updateDimNameFits();
      layoutConstantValues();
    });
  }
  initPage();

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
            loadPage(target, true);
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
      case 'open-formula-sql': openFormulaSqlModal(); break;
      case 'close-formula-sql': closeFormulaSqlModal(); break;
      case 'copy-formula-sql-export':
      case 'copy-token-sql-export': copySqlBlock(el); break;
      case 'remove-qty-chip': removeQtyChip(el.getAttribute('data-qty')); break;
      case 'add-qty-chip': addQtyChip(el.getAttribute('data-qty')); break;
      case 'close-overlays': closeSidebar('left'); closeSidebar('right'); break;
      case 'dock-set-view': dockSetView(el.getAttribute('data-dock-view')); break;
      case 'dock-toggle-panel': toggleSidebar(el.getAttribute('data-target')); break;
      case 'toggle-si-prefixes': toggleSiPrefixes(el); break;
      case 'units-ref-pick': pickUnitsRef(el); break;
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
      case 'switch-unit-system': switchUnitSystem(el.value); break;
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

  function switchUnitSystem(system) {
    setCookie('sf_unit_system', system);
    window.location.reload();
  }
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
      /* Content grabs only become drags from the top of the list;
         elsewhere the gesture belongs to native scrolling. */
      var scrollArea = sheet.querySelector('.sidebar-scroll');
      if (!onHandle && (!scrollArea || scrollArea.scrollTop !== 0)) return;
      dragging = true;
      target = sheet;
      engaged = onHandle;
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
         transform would snap the sheet back to rest first. */
      sheet.style.transition = 'transform var(--dur-base) var(--ease-in-out)';
      sheet.style.transform = 'translateY(' + toY + 'px)';
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
})();
