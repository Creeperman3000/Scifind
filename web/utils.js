(function() {
  'use strict';

  function byId(id) { return document.getElementById(id); }
  function bySel(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }
  function on(idOrEl, ev, fn) {
    var el = typeof idOrEl === 'string' ? byId(idOrEl) : idOrEl;
    if (el) el.addEventListener(ev, fn);
  }
  function setParam(sp, k, v, keep) { if (keep) sp.set(k, v); else sp.delete(k); }
  function toggleCls(idOrEl, cls, cond) {
    var el = typeof idOrEl === 'string' ? byId(idOrEl) : idOrEl;
    if (el) el.classList.toggle(cls, !!cond);
  }

  var _ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function(c) { return _ESC[c]; });
  }

  function t(path, fallback) {
    var cur = window._localeUI || {};
    var parts = String(path).split('.');
    for (var i = 0; i < parts.length; i++) {
      if (cur && typeof cur === 'object' && parts[i] in cur) cur = cur[parts[i]];
      else return fallback;
    }
    return cur == null ? fallback : cur;
  }

  function debounce(fn, ms) {
    var timer = null;
    return function() {
      var ctx = this, args = arguments;
      if (timer) clearTimeout(timer);
      timer = setTimeout(function() { timer = null; fn.apply(ctx, args); }, ms);
    };
  }

  function copyText(text, label) {
    if (!(navigator.clipboard && navigator.clipboard.writeText)) return;
    var okMsg = t('toast.copied', 'Copied');
    var failMsg = t('toast.copy_failed', 'Copy failed');
    navigator.clipboard.writeText(text).then(
      function() { if (typeof window.showToast === 'function') window.showToast(okMsg + (label ? ' ' + label : ''), 'success'); },
      function(e) { if (typeof window.showToast === 'function') window.showToast(failMsg + ': ' + (e && e.message || e), 'error'); }
    );
  }

  function setModal(id, open) {
    var modal = typeof id === 'string' ? byId(id) : id;
    if (modal) modal.classList.toggle('open', !!open);
  }

  // Single owner for promise-based copies (codecogs PNG/SVG, API-fallback unicode):
  // same toast contract as copyText (toast.copied / toast.copy_failed).
  function copyPromise(promise, label) {
    if (!promise || typeof promise.then !== 'function') return;
    promise.then(
      function() { if (typeof window.showToast === 'function') window.showToast(t('toast.copied', 'Copied') + (label ? ' ' + label : ''), 'success'); },
      function(e) { if (typeof window.showToast === 'function') window.showToast(t('toast.copy_failed', 'Copy failed') + ': ' + ((e && e.message) || e), 'error'); }
    );
  }

  // Single owner for SQL <pre> blocks (formula + create modals).
  function copySqlBlock(btn) {
    var block = btn && btn.closest ? btn.closest('.sql-block') : null;
    var pre = block ? block.querySelector('pre') : null;
    if (!pre || !pre.textContent.trim()) return;
    copyText(pre.textContent, 'SQL');
  }

  function copyPreById(id, label) {
    var pre = typeof id === 'string' ? byId(id) : id;
    if (!pre || !pre.textContent.trim()) return;
    copyText(pre.textContent, label || 'SQL');
  }

  // Single data-action registry + central click dispatch (single listener,
  // create-priority). Pre-handlers (create token/topic/tr-copy) run first;
  // overlay closers run next; then the action registry.
  var _actions = {};
  function registerActions(table) {
    Object.keys(table || {}).forEach(function(k) { _actions[k] = table[k]; });
  }
  function dispatchAction(action, el, e) {
    var fn = _actions[action];
    if (typeof fn === 'function') { fn(e, el); return true; }
    return false;
  }
  function actionEl(e) {
    if (!e || !e.target || !e.target.closest) return null;
    return e.target.closest('[data-action]');
  }
  var _preHandlers = [];
  var _overlayClosers = [];
  var _installed = false;
  function registerPreHandler(fn) { _preHandlers.push(fn); }
  function registerOverlayCloser(fn) { _overlayClosers.push(fn); }
  function handleDocumentClick(e) {
    var i;
    for (i = 0; i < _preHandlers.length; i++) {
      try { if (_preHandlers[i](e) === true) return; } catch (err) {}
    }
    for (i = 0; i < _overlayClosers.length; i++) {
      try { _overlayClosers[i](e); } catch (err) {}
    }
    var el = actionEl(e);
    if (!el) return;
    dispatchAction(el.getAttribute('data-action'), el, e);
  }
  function installSingleClickListener() {
    if (_installed) return;
    _installed = true;
    document.addEventListener('click', handleDocumentClick);
  }

  // Shared qty-result inner spans (same CSS contract server + client).
  function qtyResultInner(symbolLatex, nameText) {
    var sym = symbolLatex
      ? '<span class="qty-result-sym">' + symbolLatex + '</span>'
      : '<span class="qty-result-sym"></span>';
    return sym + '<span class="qty-result-name">' + escapeHtml(nameText || '') + '</span>';
  }

  // Filter-URL param hygiene shared by list navigations.
  var PAGING_PARAMS = ['page', 'per_page', 'all'];
  var TOPIC_PARAMS = ['subbranch', 'topic', 'id', 'exclude_all'];
  function stripPagingParams(params) {
    PAGING_PARAMS.forEach(function(k) { params.delete(k); });
    return params;
  }
  function stripTopicParams(params) {
    TOPIC_PARAMS.forEach(function(k) { params.delete(k); });
    return params;
  }
  function stripSearchParam(params, keepQ) {
    if (!keepQ) params.delete('q');
    return params;
  }
  // Pure predicate shared by hasActiveFilters + syncFilterStates.
  function filtersActive(dims, qtyCount, diffMin, diffMax) {
    var dimOn = (dims || []).some(function(v) { return v === true; });
    return dimOn || (qtyCount || 0) > 0 || diffMin > 1 || diffMax < 10;
  }
  // Single-source slug helpers mirroring export.resolve_formula_id + constants.is_slug.
  function slugify(s) {
    return String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  }
  function isSlug(s) {
    return /^[a-z0-9]+(?:_[a-z0-9]+)*$/.test(s || '');
  }
  // Single sidebar/nav owner: attr-based open check + pure URL builders.
  // isSidebarOpen/sidebarClosed previously disagreed on class checks; the attr
  // is set together with classes in setSidebarState, so the attr is canonical.
  function sidebarOpenAttr(side) {
    var el = document.getElementById('sidebar-' + side);
    return !el || el.getAttribute('data-open') !== '0';
  }
  function stripQFromUrl(url) {
    var u = url instanceof URL ? url : new URL(url, window.location.origin);
    u.searchParams.delete('q');
    var qs = u.searchParams.toString();
    return u.pathname + (qs ? '?' + qs : '');
  }
  function viewUrl(view, stripQ) {
    var u = new URL(window.location);
    if (stripQ) u.searchParams.delete('q');
    var qs = u.searchParams.toString();
    return (view === 'quantities' ? '/quantities' : '/formulas') + (qs ? '?' + qs : '');
  }
  function clearSearchInput(blur) {
    var si = document.querySelector('.topbar-search input[name="q"]');
    if (si) { si.value = ''; if (blur) si.blur(); }
    if (typeof window.syncSearchCancel === 'function') window.syncSearchCancel();
    var topbar = document.querySelector('.topbar');
    if (topbar) topbar.classList.remove('expand-search');
  }

  window.SFUtils = {
    byId: byId,
    bySel: bySel,
    on: on,
    setParam: setParam,
    toggleCls: toggleCls,
    escapeHtml: escapeHtml,
    t: t,
    debounce: debounce,
    copyText: copyText,
    copyPromise: copyPromise,
    copySqlBlock: copySqlBlock,
    copyPreById: copyPreById,
    setModal: setModal,
    registerActions: registerActions,
    dispatchAction: dispatchAction,
    registerPreHandler: registerPreHandler,
    registerOverlayCloser: registerOverlayCloser,
    installSingleClickListener: installSingleClickListener,
    qtyResultInner: qtyResultInner,
    stripPagingParams: stripPagingParams,
    stripTopicParams: stripTopicParams,
    stripSearchParam: stripSearchParam,
    filtersActive: filtersActive,
    slugify: slugify,
    isSlug: isSlug,
    sidebarOpenAttr: sidebarOpenAttr,
    stripQFromUrl: stripQFromUrl,
    viewUrl: viewUrl,
    clearSearchInput: clearSearchInput
  };
})();
