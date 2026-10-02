'use strict';
(function() {
  var ID_RE = /^[A-Za-z0-9_.\-]{1,80}$/;
  // ?sel= is the store: every mutation re-mints and replaceStates the URL
  // (debounced); a failed mint reverts the mutation so URL == state.
  // _SAFETY caps bound hostile input, not users.
  var _SAFETY_IDS = 5000, _SAFETY_CUSTOMS = 500;
  function freshStore() {
    return { f: {}, cf: [], off: {}, q: {}, cq: [], qoff: {}, selF: [], selQ: [] };
  }
  var store = freshStore();
  var urlSeq = 0, mintTimer = null, urlDirty = false, pendingBackup = null;

  var ui = { selectMode: false };
  try { ui.selectMode = sessionStorage.getItem('sf_select_mode') === '1'; } catch (e) {}

  function uniq(arr) {
    var seen = Object.create(null);
    return arr.filter(function(x) { if (seen[x]) return false; seen[x] = 1; return true; }).slice(0, _SAFETY_IDS);
  }
  function cleanIds(arr) {
    return uniq((arr || []).map(function(s) { return String(s || '').trim(); }).filter(function(s) { return ID_RE.test(s); }));
  }
  function getF() { return cleanIds(store.selF); }
  function getQ() { return cleanIds(store.selQ); }
  function isSelectMode() { return !!ui.selectMode; }
  function isShowOnly() {
    try { return new URL(location.href).searchParams.get('show_selected') === '1'; }
    catch (e) { return false; }
  }
  function setSelectMode(on) {
    ui.selectMode = !!on;
    try {
      if (on) sessionStorage.setItem('sf_select_mode', '1');
      else sessionStorage.removeItem('sf_select_mode');
    } catch (e) {}
  }
  // All mutations go through here: optimistic UI, debounced URL sync, revert on failure.
  function commit(mutator) {
    if (!urlDirty) pendingBackup = JSON.stringify(store);
    mutator();
    urlDirty = true;
    syncUI();
    if (isDialogOpen()) { refreshLists(); schedulePreview(true); }
    scheduleUrlSync();
  }
  function scheduleUrlSync() {
    if (mintTimer) clearTimeout(mintTimer);
    mintTimer = setTimeout(function() { mintTimer = null; syncUrlNow(); }, 250);
  }
  function adoptToken(token) {
    if (mintTimer) { clearTimeout(mintTimer); mintTimer = null; }
    urlSeq++;
    try {
      var url = new URL(location.href);
      if (token) url.searchParams.set('sel', token);
      else url.searchParams.delete('sel');
      history.replaceState({ url: url.toString() }, '', url);
      if (typeof window.syncViewTabLinks === 'function') window.syncViewTabLinks();
    } catch (e) {}
    urlDirty = false;
    pendingBackup = null;
    syncUI();
    if (isDialogOpen()) { refreshLists(); schedulePreview(true); }
    if (isShowOnly()) {
      var listUrl = new URL(location.href);
      if (typeof window.loadPage === 'function') window.loadPage(listUrl.pathname + listUrl.search, false);
      else nav(listUrl.pathname + listUrl.search);
    }
  }
  function syncUrlNow(after) {
    if (mintTimer) { clearTimeout(mintTimer); mintTimer = null; }
    if (!hasSelection()) {
      urlDirty = false;
      pendingBackup = null;
      if (isShowOnly()) { showUrl(true); if (after) after(true); return; }
      try {
        var emptyUrl = new URL(location.href);
        if (emptyUrl.searchParams.has('sel')) {
          emptyUrl.searchParams.delete('sel');
          history.replaceState({ url: emptyUrl.toString() }, '', emptyUrl);
          if (typeof window.syncViewTabLinks === 'function') window.syncViewTabLinks();
        }
      } catch (e) {}
      if (after) after(true);
      return;
    }
    var seq = ++urlSeq;
    postPayload('/api/selection-share', selectionPayload()).then(function(data) {
      if (seq !== urlSeq) { if (after) after(true); return; }
      var token = data && data.sel;
      if (!token) throw new Error('mint failed');
      adoptToken(token);
      if (after) after(true);
    }).catch(function() {
      if (seq !== urlSeq) { if (after) after(false); return; }
      try { store = JSON.parse(pendingBackup || '{}'); }
      catch (e) { store = freshStore(); }
      if (!store || typeof store !== 'object') store = freshStore();
      urlDirty = false;
      pendingBackup = null;
      syncUI();
      if (isDialogOpen()) { renderLists(); schedulePreview(true); }
      if (window.showToast) window.showToast(t('print.reverted'), 'error');
      if (after) after(false);
    });
  }
  function ensureUrlSynced(after) {
    if (!urlDirty && !mintTimer) { if (after) after(true); return; }
    syncUrlNow(after);
  }
  function updateSelection(key, arr) {
    var ids = cleanIds(arr);
    commit(function() {
      if (key === 'selected_formulas') store.selF = ids;
      else store.selQ = ids;
    });
    if (!hasSelection() && isShowOnly()) showUrl(true);
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
    if (window.showToast) window.showToast((i === -1 ? t('select.added') : t('select.removed')) + ': ' + name, 'info');
  }
  function setSlotIcon(wrapId, icon, size) {
    var wrap = document.getElementById(wrapId);
    if (!wrap) return;
    var cur = wrap.querySelector('[data-lucide]');
    if (cur && cur.getAttribute('data-lucide') === icon) return;
    wrap.innerHTML = '<i data-lucide="' + icon + '" width="' + (size || 18) + '" height="' + (size || 18) + '"></i>';
    refreshIcons();
  }
  function syncUI() {
    var f = getF(), q = getQ(), total = f.length + q.length;
    var customN = 0;
    try { customN = snapshotCount(); } catch (e) { customN = 0; }
    var printTotal = total + customN;
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
      var tip = t('tooltip.select_mode');
      setSlotIcon('select-toggle-icon', 'list-checks', 18);
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
        showBtn.disabled = printTotal === 0;
        setSlotIcon('show-selected-icon', showOnly ? 'eye-off' : 'eye', 18);
        showBtn.classList.toggle('active', showOnly);
        setAttr(showBtn, 'aria-pressed', showOnly ? 'true' : 'false');
        var stip = showOnly
          ? t('tooltip.show_all')
          : t('tooltip.show_selected');
        if (showBtn.title !== stip) showBtn.title = stip;
        setAttr(showBtn, 'aria-label', stip);
      }
    }
    var shareBtn = document.getElementById('share-btn');
    if (shareBtn) {
      if (!mode) {
        shareBtn.classList.add('hidden');
      } else {
        shareBtn.classList.remove('hidden');
        shareBtn.disabled = printTotal === 0;
      }
    }
    var pb = document.getElementById('print-btn');
    if (pb) {
      pb.classList.toggle('hidden', !mode && !customN);
      pb.disabled = printTotal === 0;
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
  var FILTER_SCOPE_STRIP = ['page', 'per_page', 'sort', 'sel', 'show_selected'];
  function selectAllKey(view) {
    var url = new URL(location.href);
    FILTER_SCOPE_STRIP.forEach(function(k) { url.searchParams.delete(k); });
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
    FILTER_SCOPE_STRIP.forEach(function(k) { url.searchParams.delete(k); });
    url.searchParams.set('view', view);
    window.SFApi.getJSON('/api/filter-ids?' + url.searchParams.toString()).then(function(data) {
      selAll.loading = false;
      selAll.pendingKey = null;
      selAll.key = key;
      selAll.ids = ((data && data.ids) || []).filter(function(id) { return ID_RE.test(id); });
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
    var cur = view === 'formulas' ? getF() : getQ();
    var any = cur.length > 0;
    var tip = any
      ? t('print.deselect_all')
      : t('print.add_all');
    if (btn.title !== tip) btn.title = tip;
    setAttr(btn, 'aria-label', tip);
    if (!any) ensureFilteredIds(view);
    btn.classList.toggle('active', any);
    setAttr(btn, 'aria-pressed', any ? 'true' : 'false');
  }
  function onSelectAll() {
    var view = listView();
    if (!view || !isSelectMode() || !window.SFApi) return;
    var key = view === 'formulas' ? 'selected_formulas' : 'selected_quantities';
    var cur = key === 'selected_formulas' ? getF() : getQ();
    if (cur.length) {
      updateSelection(key, []);
      if (window.showToast) window.showToast(t('select.removed') + ': ' + cur.length, 'info');
      return;
    }
    ensureFilteredIds(view, function(ids) {
      if (!ids.length) return;
      var add = ids.filter(function(id) { return cur.indexOf(id) === -1; });
      if (!add.length) return;
      packSelectAll(key, cur, add);
    });
  }
  // Bulk add packs the largest fitting prefix; the store is only touched after a good mint.
  function packSelectAll(key, cur, add) {
    var isF = key === 'selected_formulas';
    var total = add.length;
    var payloadFor = function(count) {
      var p = selectionPayload();
      var ids = cur.concat(add.slice(0, count));
      if (isF) p.f = ids; else p.q = ids;
      return { payload: p, ids: ids };
    };
    var applyIds = function(ids, token) {
      if (isF) store.selF = ids; else store.selQ = ids;
      adoptToken(token);
    };
    var addedMsg = function(n) {
      if (window.showToast) window.showToast(t('select.added') + ': ' + n, 'info');
    };
    var partialMsg = function(kept) {
      if (!window.showToast) return;
      window.showToast(t('print.added_partial')
        .replace('{kept}', kept).replace('{total}', total), 'info');
    };
    var probe = function(count) {
      var c = payloadFor(count);
      return postPayload('/api/selection-share', c.payload).then(function(data) {
        if (!data || !data.sel) throw new Error('mint failed');
        return { ids: c.ids, token: data.sel };
      });
    };
    probe(total).then(function(found) {
      applyIds(found.ids, found.token);
      addedMsg(total);
    }).catch(function() {
      var guess = estimateFitCount(total);
      var finish = function(kept) {
        if (kept <= 0) {
          if (window.showToast) window.showToast(t('print.link_full'), 'error');
          return;
        }
        probe(kept).then(function(found) {
          applyIds(found.ids, found.token);
          partialMsg(kept);
        }).catch(function() {
          if (window.showToast) window.showToast(t('print.link_full'), 'error');
        });
      };
      var step = function(lo, hi) {
        if (hi - lo <= 1) return finish(lo);
        var mid = (lo + hi) >> 1;
        probe(mid).then(function() { step(mid, hi); }, function() { step(lo, mid); });
      };
      if (guess <= 0 || guess >= total) return step(0, total);
      probe(guess).then(function() { step(guess, total); }, function() { step(0, guess); });
    });
  }
  function estimateFitCount(total) {
    try {
      var sel = new URL(location.href).searchParams.get('sel') || '';
      var perId = 12;
      var base = getF().length + getQ().length;
      if (sel && base > 0) perId = Math.max(6, (sel.length - 200) / base);
      var guess = Math.floor((8000 - sel.length - 200) / perId);
      return Math.min(total, Math.max(0, guess));
    } catch (e) { return 0; }
  }
  function onToggle() {
    setSelectMode(!isSelectMode());
    syncUI();
  }
  function showUrl(exit) {
    var url = new URL(location.href);
    if (exit) {
      url.searchParams.delete('show_selected');
      if (!hasSelection()) url.searchParams.delete('sel');
    } else if (url.pathname === '/formulas' || url.pathname === '/quantities') {
      url.searchParams.set('show_selected', '1');
    } else {
      url.pathname = getF().length ? '/formulas' : '/quantities';
      url.search = '?sel=' + encodeURIComponent(url.searchParams.get('sel') || '') + '&show_selected=1';
    }
    nav(url.pathname + (url.searchParams.toString() ? '?' + url.searchParams.toString() : ''));
  }
  function onShowToggle() {
    if (!isSelectMode()) return;
    if (isShowOnly()) { showUrl(true); return; }
    if (!hasSelection()) return;
    ensureUrlSynced(function(ok) {
      if (!ok) return;
      var sel = '';
      try { sel = new URL(location.href).searchParams.get('sel') || ''; } catch (e) {}
      if (!sel) {
        if (window.showToast) window.showToast(t('print.share_failed'), 'error');
        return;
      }
      showUrl(false);
    });
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
    if (seg) { dlg.layout = seg.getAttribute('data-playout'); syncDlgControls(); schedulePreview(); return; }
    var pvt = closest(e, '#dlg-preview-toggle');
    if (pvt) {
      var layout = document.getElementById('print-layout');
      var on = layout ? !layout.classList.contains('show-preview') : false;
      if (layout) layout.classList.toggle('show-preview', on);
      setPreviewToggle(pvt, on);
      if (on) schedulePreview(true);
      return;
    }
    if (closest(e, '#print-add-all')) {
      var boxes = document.querySelectorAll('#print-qlist input[data-print-check]');
      var off = document.querySelectorAll('#print-qlist input[data-print-check]:not(:checked)');
      if (boxes.length && !off.length) updateSelection('selected_quantities', []);
      else {
        var news = ((dlg.data && dlg.data.in_formula_new) || []).map(function(x) { return x.id; }).filter(function(id) { return ID_RE.test(id) && getQ().indexOf(id) === -1; });
        if (news.length) packSelectAll('selected_quantities', getQ(), news);
      }
      return;
    }
    if (closest(e, '#print-add-formula')) { openFormulaEditor(null); return; }
    if (closest(e, '#print-add-quantity')) { openQuantityEditor(null); return; }
    var edF = closest(e, '[data-edit-formula]');
    if (edF) { e.preventDefault(); e.stopPropagation(); openFormulaEditor(edF.getAttribute('data-edit-formula')); return; }
    var edQ = closest(e, '[data-edit-quantity]');
    if (edQ) { e.preventDefault(); e.stopPropagation(); openQuantityEditor(edQ.getAttribute('data-edit-quantity')); return; }
    if (closest(e, '#pe-cancel')) { closeEdit(); return; }
    if (closest(e, '#pe-apply')) { applyEditModal(); return; }
    if (closest(e, '#pe-remove')) { removeEditModal(); return; }
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
          pic.innerHTML = '<i data-lucide="chevron-' + (expanding ? 'up' : 'down') + '" width="16" height="16"></i>';
          refreshIcons();
        }
      }
      return;
    }
    var ov = dlgEl();
    if (ov && ov.classList.contains('open') && e.target === ov) closeDialog();
    var em = editEl();
    if (em && em.classList.contains('open') && e.target === em) closeEdit();
  }, true);

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && isEditOpen()) { e.stopPropagation(); closeEdit(); return; }
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

  var dlg = { layout: 'l2', cols: 4, rows: 16, borders: true, paper: null, data: null, loading: false, pendingRefresh: false, knownF: {}, knownQ: {} };
  var previewTimer = null, katexRetryArmed = false, renderSeq = 0;
  // User zoom factor on top of the auto fit-to-width (uses native CSS `zoom`, no library).
  // Zoom lives on the inner wrapper so the scroll container keeps native scrollbars.
  var previewZoom = 1, previewFit = 1, zoomArmed = false, pinchD0 = 0, pinchZ0 = 1;
  function zoomEl() {
    var pv = document.getElementById('print-preview');
    return pv ? pv.querySelector('.pview-zoom') : null;
  }
  function fitZoomFor(pv) {
    var first = pv.querySelector('.pview-page'), zEl = pv.querySelector('.pview-zoom');
    if (!first || !zEl || !('zoom' in zEl.style)) return 1;
    var cs = getComputedStyle(pv);
    var avail = pv.clientWidth - (parseFloat(cs.paddingLeft) || 0) - (parseFloat(cs.paddingRight) || 0);
    var z = avail / first.offsetWidth;
    return (isFinite(z) && z > 0 && z < 4 && Math.abs(z - 1) > 0.01) ? z : 1;
  }
  function applyPreviewZoom() {
    var zEl = zoomEl();
    if (!zEl || !('zoom' in zEl.style)) return;
    var z = previewFit * previewZoom;
    zEl.style.zoom = (Math.abs(z - 1) > 0.01) ? z : '';
  }
  function setPreviewZoom(nz, cx, cy) {
    var pv = document.getElementById('print-preview');
    if (!pv) return;
    nz = Math.min(4, Math.max(0.4, nz));
    if (nz === previewZoom) return;
    var r = pv.getBoundingClientRect(), oz = previewFit * previewZoom;
    var cs = getComputedStyle(pv);
    var ox = (parseFloat(cs.borderLeftWidth) || 0) + (parseFloat(cs.paddingLeft) || 0);
    var oy = (parseFloat(cs.borderTopWidth) || 0) + (parseFloat(cs.paddingTop) || 0);
    var sx = (pv.scrollLeft + (cx === undefined ? r.width / 2 : cx - r.left) - ox) / (oz || 1);
    var sy = (pv.scrollTop + (cy === undefined ? r.height / 2 : cy - r.top) - oy) / (oz || 1);
    previewZoom = nz;
    applyPreviewZoom();
    var z = previewFit * previewZoom;
    pv.scrollLeft = sx * z + ox - ((cx === undefined ? r.width / 2 : cx - r.left));
    pv.scrollTop = sy * z + oy - ((cy === undefined ? r.height / 2 : cy - r.top));
  }
  function ensurePreviewZoom() {
    var pv = document.getElementById('print-preview');
    if (!pv || zoomArmed) return;
    zoomArmed = true;
    // Mouse / trackpad: Ctrl+wheel (browsers also send this for pinch gestures).
    pv.addEventListener('wheel', function(e) {
      if (!e.ctrlKey) return;
      e.preventDefault();
      setPreviewZoom(previewZoom * Math.exp(-e.deltaY * 0.002), e.clientX, e.clientY);
    }, { passive: false });
    // Fingers: two-finger pinch.
    var dist = function(t) {
      var dx = t[0].clientX - t[1].clientX, dy = t[0].clientY - t[1].clientY;
      return Math.sqrt(dx * dx + dy * dy);
    };
    pv.addEventListener('touchstart', function(e) {
      if (e.touches.length === 2) { pinchD0 = dist(e.touches); pinchZ0 = previewZoom; }
    }, { passive: true });
    pv.addEventListener('touchmove', function(e) {
      if (e.touches.length !== 2 || !pinchD0) return;
      e.preventDefault();
      var d = dist(e.touches);
      if (d > 0) setPreviewZoom(pinchZ0 * d / pinchD0,
        (e.touches[0].clientX + e.touches[1].clientX) / 2,
        (e.touches[0].clientY + e.touches[1].clientY) / 2);
    }, { passive: false });
    pv.addEventListener('touchend', function(e) { if (e.touches.length < 2) pinchD0 = 0; }, { passive: true });
    pv.addEventListener('dblclick', function() { setPreviewZoom(1); });
  }

  function isEditedF(id) { return !!(id && store.f[id]); }
  function isEditedQ(id) { return !!(id && store.q[id]); }
  function cleanText(v, max) {
    v = String(v == null ? '' : v);
    return v.length > max ? v.slice(0, max) : v;
  }
  function cleanTokens(t) {
    if (!Array.isArray(t) || !t.length || t.length > 500) return null;
    var out = [];
    for (var i = 0; i < t.length; i++) {
      var tok = t[i];
      if (!Array.isArray(tok) || !tok.length) return null;
      var kind = tok[0];
      if (kind === 'q') {
        if (tok.length < 2 || tok.length > 5 || !ID_RE.test(tok[1] || '')) return null;
        var parts = [cleanText(tok[2] || '', 100), cleanText(tok[3] || '', 200), cleanText(tok[4] || '', 200)];
        while (parts.length && !parts[parts.length - 1]) parts.pop();
        out.push(['q', tok[1]].concat(parts));
      } else if (kind === 'c' || kind === 'o') {
        if (tok.length !== 2 || !ID_RE.test(tok[1] || '')) return null;
        out.push([kind, tok[1]]);
      } else if (kind === 'n') {
        if (tok.length !== 2 || typeof tok[1] !== 'number' || !(isFinite(tok[1]))) return null;
        out.push(['n', tok[1]]);
      } else return null;
    }
    return out;
  }
  function cleanFormulaSnap(s) {
    if (!s || typeof s !== 'object') return null;
    var name = cleanText(s.n || '', 200).trim();
    var tokens = s.t == null ? null : cleanTokens(s.t);
    if (s.t != null && tokens === null) return null;
    var eq = cleanText(s.e || '', 2000).trim();
    if (!name && !tokens) return null;
    var out = {};
    if (name) out.n = name;
    if (tokens) out.t = tokens;
    if (eq) out.e = eq;
    return out;
  }
  function cleanQuantitySnap(s) {
    if (!s || typeof s !== 'object') return null;
    var out = {};
    var name = cleanText(s.n || '', 200).trim();
    var sym = cleanText(s.s || '', 100).trim();
    var unit = cleanText(s.u || '', 200).trim();
    if (name) out.n = name;
    if (sym) out.s = sym;
    if (unit) out.u = unit;
    return Object.keys(out).length ? out : null;
  }
  function cleanFormulaCustom(c) {
    if (!c || typeof c !== 'object' || !ID_RE.test(c.i || '')) return null;
    var snap = cleanFormulaSnap(c);
    if (!snap || !snap.t) return null;
    snap.i = c.i;
    return snap;
  }
  function cleanQuantityCustom(c) {
    if (!c || typeof c !== 'object' || !ID_RE.test(c.i || '')) return null;
    var snap = cleanQuantitySnap(c);
    if (!snap) return null;
    snap.i = c.i;
    return snap;
  }
  function snapshotCount() {
    var n = 0, i, id;
    for (i = 0; i < store.cf.length; i++) { id = store.cf[i].i; if (id && !store.off[id]) n++; }
    for (i = 0; i < store.cq.length; i++) { id = store.cq[i].i; if (id && !store.qoff[id]) n++; }
    return n;
  }
  function hasSelection() { return !!(getF().length || getQ().length || snapshotCount()); }
  function cleanStoreMap(obj, cleanFn) {
    var out = {};
    if (!obj || typeof obj !== 'object') return out;
    Object.keys(obj).slice(0, _SAFETY_IDS).forEach(function(k) {
      if (!ID_RE.test(k)) return;
      var entry = cleanFn(obj[k]);
      if (entry) out[k] = entry;
    });
    return out;
  }
  function cleanStoreCustomList(arr, cleanFn) {
    var out = [], seen = Object.create(null);
    if (!Array.isArray(arr)) return out;
    arr.slice(0, _SAFETY_CUSTOMS).forEach(function(c) {
      var entry = cleanFn(c);
      if (entry && !seen[entry.i]) { seen[entry.i] = 1; out.push(entry); }
    });
    return out;
  }
  function applyPayloadToStore(p) {
    store = freshStore();
    if (!p || typeof p !== 'object') return;
    (p.f || []).forEach(function(id) {
      if (ID_RE.test(id) && store.selF.indexOf(id) === -1 && store.selF.length < _SAFETY_IDS) store.selF.push(id);
    });
    (p.q || []).forEach(function(id) {
      if (ID_RE.test(id) && store.selQ.indexOf(id) === -1 && store.selQ.length < _SAFETY_IDS) store.selQ.push(id);
    });
    Object.keys(p.fo || {}).forEach(function(id) {
      var snap = cleanFormulaSnap(p.fo[id]);
      if (ID_RE.test(id) && snap) store.f[id] = snap;
    });
    cleanStoreCustomList(p.cf || [], cleanFormulaCustom).forEach(function(entry) { store.cf.push(entry); });
    Object.keys(p.qo || {}).forEach(function(id) {
      var snap = cleanQuantitySnap(p.qo[id]);
      if (ID_RE.test(id) && snap) store.q[id] = snap;
    });
    cleanStoreCustomList(p.cq || [], cleanQuantityCustom).forEach(function(entry) { store.cq.push(entry); });
    Object.keys(p.off || {}).forEach(function(id) { if (ID_RE.test(id)) store.off[id] = 1; });
    Object.keys(p.qoff || {}).forEach(function(id) { if (ID_RE.test(id)) store.qoff[id] = 1; });
  }
  var readGen = 0;
  function readUrlToStore() {
    var gen = ++readGen;
    var token = '';
    try { token = new URL(location.href).searchParams.get('sel') || ''; } catch (e) {}
    // A navigation supersedes any pending sync from the previous view.
    if (mintTimer) { clearTimeout(mintTimer); mintTimer = null; }
    urlSeq++;
    store = freshStore();
    urlDirty = false;
    pendingBackup = null;
    if (!token || !window.SFApi) return Promise.resolve();
    return window.SFApi.getJSON('/api/selection-resolve?sel=' + encodeURIComponent(token)).then(function(p) {
      if (gen !== readGen || urlDirty) return; // user already mutated; URL stays truth
      applyPayloadToStore(p);
    }).catch(function() {
      if (gen !== readGen || urlDirty) return;
      store = freshStore();
      try {
        var badUrl = new URL(location.href);
        if (badUrl.searchParams.has('sel')) {
          badUrl.searchParams.delete('sel');
          history.replaceState({ url: badUrl.toString() }, '', badUrl);
        }
      } catch (e) {}
    });
  }

  var PAPERS_MM = { letter: [215.9, 279.4], legal: [215.9, 355.6], tabloid: [279.4, 431.8],
    a0: [841, 1189], a1: [594, 841], a2: [420, 594], a3: [297, 420], a4: [210, 297], a5: [148, 210], a6: [105, 148] };
  function printGeom() {
    var paper = PAPERS_MM[dlg.paper] ? dlg.paper : 'a4';
    var pw = PAPERS_MM[paper][0], ph = PAPERS_MM[paper][1];
    var textW = Math.max(10, pw - 20), textH = Math.max(10, ph - 20);
    var cols = clamp(dlg.cols, 4, 1, 32), rows = clamp(dlg.rows, 16, 1, 32);
    var ruleW = dlg.borders ? 0.15 * (cols + 1) : 0, ruleH = dlg.borders ? 0.15 * (rows + 1) : 0;
    var tabsep = Math.max(0.8, Math.min(dlg.borders ? 2.0 : 4.0, (textW - ruleW - cols * 3.0) / (2.0 * cols)));
    var colW = Math.max(3.0, (textW - 2.0 * tabsep * cols - ruleW) / cols);
    return { paper: paper, pw: pw, ph: ph, textW: textW, textH: textH,
      left: Math.max(0, (pw - textW) / 2), top: Math.max(0, (ph - textH) / 2),
      cols: cols, rows: rows, tabsep: tabsep, colW: colW, cellH: Math.max(6.0, (textH - ruleH) / rows) };
  }
  function qtyEquation(e) {
    var u = e.unit_latex || '';
    return (e.symbol && u) ? e.symbol + '\\;(' + u + ')' : (e.symbol || u || '');
  }
  function printItems() {
    var items = [], fById = {}, qById = {};
    if (dlg.data) {
      (dlg.data.formulas || []).forEach(function(x) { fById[x.id] = x; });
      (dlg.data.quantities || []).forEach(function(x) { qById[x.id] = x; });
      (dlg.data.custom_quantities || []).forEach(function(x) { if (!qById[x.id]) qById[x.id] = x; });
    }
    var customF = {};
    store.cf.forEach(function(c) { if (c && c.i) customF[c.i] = c; });
    var customQ = {};
    store.cq.forEach(function(c) { if (c && c.i) customQ[c.i] = c; });
    var pushF = function(id) {
      if (fById[id]) items.push({ equation: fById[id].latex || '', name: fById[id].name || id });
      else if (dlg.knownF[id]) items.push({ equation: '', name: dlg.knownF[id].name || id });
      else if (customF[id]) items.push({ equation: '', name: customF[id].n || id });
    };
    var pushQ = function(id) {
      if (qById[id]) items.push({ equation: qtyEquation(qById[id]), name: qById[id].name || id });
      else if (dlg.knownQ[id]) items.push({ equation: '', name: dlg.knownQ[id].name || id });
      else if (customQ[id]) {
        var cc = customQ[id];
        items.push({ equation: qtyEquation({ symbol: cc.s || '', unit_latex: '' }), name: cc.n || id });
      }
    };
    getF().forEach(function(id) { if (!store.off[id]) pushF(id); });
    store.cf.forEach(function(c) { if (c && c.i && !store.off[c.i] && getF().indexOf(c.i) === -1) pushF(c.i); });
    getQ().forEach(function(id) { if (!store.qoff[id]) pushQ(id); });
    store.cq.forEach(function(c) { if (c && c.i && !store.qoff[c.i] && getQ().indexOf(c.i) === -1) pushQ(c.i); });
    return items;
  }
  function padCells(cells, n) {
    while (cells.length < n) cells.push(null);
    return cells;
  }
  function printPageList(g, items) {
    var per = g.cols * g.rows, pages = [];
    for (var i = 0; i < items.length; i += per) {
      var chunk = items.slice(i, i + per);
      if (dlg.layout === 'l3') {
        pages.push({ kind: 'eq', cells: padCells(chunk.map(function(it) { return { eq: it.equation }; }), per) });
        var full = padCells(chunk.slice(), per), back = [];
        for (var r = 0; r < g.rows; r++) {
          var row = full.slice(r * g.cols, (r + 1) * g.cols).reverse();
          for (var c = 0; c < row.length; c++) back.push(row[c] ? { name: row[c].name } : null);
        }
        pages.push({ kind: 'name', cells: back });
      } else if (dlg.layout === 'l1') {
        pages.push({ kind: 'eq', cells: padCells(chunk.map(function(it) { return { eq: it.equation }; }), per) });
      } else {
        pages.push({ kind: 'both', cells: padCells(chunk.map(function(it) { return { eq: it.equation, name: it.name }; }), per) });
      }
    }
    return pages;
  }
  function backNameSize(colW) {
    return colW >= 30 ? '14.4pt' : (colW >= 20 ? '12pt' : '10pt');
  }
  function printCellHtml(cell, kind, gap, size) {
    if (!cell) return '<div class="pcard pcard-empty" aria-hidden="true"></div>';
    var disp = dlg.layout === 'l1' ? '' : ' data-display="1"';
    var eq = cell.eq
      ? '<div class="pcard-eq"><span class="latex-observe" data-latex="' + esc(cell.eq) + '"' + disp + '></span></div>' : '';
    if (kind !== 'eq' && cell.name && !cell.eq)
      return '<div class="pcard"><div class="pcard-name pcard-name-back" style="font-size:'
        + backNameSize(size || 40) + '">' + esc(cell.name) + '</div></div>';
    var nm = (kind !== 'eq' && cell.name)
      ? '<div class="pcard-name"' + (cell.eq ? ' style="margin-top:' + gap + 'mm"' : '') + '>'
        + esc(cell.name) + '</div>' : '';
    return '<div class="pcard">' + eq + nm + '</div>';
  }
  var PVIEW_CSS = '.pview-page{position:relative;overflow:hidden;background:#fff;color:#000;font-size:11pt;line-height:1.25}'
    + '.pview-page,.pview-grid,.pcard{box-sizing:border-box}'
    + '.pview-grid{position:absolute;display:grid;background:#fff}'
    + '.pview-grid.bordered{gap:0;border-top:max(0.11mm,1px) solid #bfbfbf;border-left:max(0.11mm,1px) solid #bfbfbf}'
    + '.pview-grid.bordered .pcard{border-right:max(0.11mm,1px) solid #bfbfbf;border-bottom:max(0.11mm,1px) solid #bfbfbf}'
    + '.pcard{background:#fff;color:#000;display:flex;flex-direction:column;'
    + 'align-items:center;justify-content:center;text-align:center;'
    + 'padding:1mm;min-width:0;min-height:0;overflow:hidden}'
    + '.pcard-eq{max-width:100%;font-size:13.5pt;line-height:1.25;flex-shrink:0}'
    + '.pcard-eq .katex-display{margin:0}'
    + '.pcard-eq .katex{white-space:nowrap}'
    + '.pcard-name{font-size:8.5pt;line-height:1.3;overflow:hidden;overflow-wrap:anywhere;flex-shrink:0;max-height:min(35%,12mm);hyphens:auto;text-wrap:balance}'
    + '.pcard-name-back{max-height:none;line-height:1.25;text-align:center}';
  function ensurePreviewCss() {
    if (document.getElementById('sf-pview-css')) return;
    var st = document.createElement('style');
    st.id = 'sf-pview-css';
    st.textContent = PVIEW_CSS;
    document.head.appendChild(st);
  }
  function printGridHtml(g, page) {
    var gap = (Math.max(1.0, Math.min(4.0, 0.12 * (g.cellH || g.textH / g.rows))) * 0.35146).toFixed(2);
    var nogap = dlg.borders ? '' : 'gap:' + (2 * (g.tabsep || 2)).toFixed(2) + 'mm;';
    return '<div class="pview-grid' + (dlg.borders ? ' bordered' : '') + '"'
      + ' style="left:' + g.left + 'mm;top:' + g.top + 'mm;width:' + g.textW + 'mm;height:' + g.textH + 'mm;' + nogap
      + 'grid-template-columns:repeat(' + g.cols + ',minmax(0,1fr));'
      + 'grid-template-rows:repeat(' + g.rows + ',minmax(0,1fr))">'
      + page.cells.map(function(c) { return printCellHtml(c, page.kind, gap, g.colW); }).join('') + '</div>';
  }
  function printPageHtml(g, page) {
    return '<div class="pview-page" style="width:' + g.pw + 'mm;height:' + g.ph + 'mm">'
      + printGridHtml(g, page) + '</div>';
  }
  function baseSize(el) {
    var b = parseFloat(el.dataset.baseFs);
    if (!b) {
      b = parseFloat(getComputedStyle(el).fontSize) || 16;
      el.dataset.baseFs = b;
    }
    return b;
  }
  function curSize(el) { return parseFloat(el.style.fontSize) || baseSize(el); }
  function quantScale(r) {
    if (!(r > 0)) return 1;
    if (r >= 1.5) return 1.5;
    if (r < 0.55) return r;
    var tiers = [0.55, 0.70, 0.85, 1.0, 1.15, 1.3];
    for (var i = tiers.length - 1; i >= 0; i--) if (r >= tiers[i]) return tiers[i];
    return r;
  }
  function fitCards(root) {
    var dirty = Array.prototype.slice.call(root.querySelectorAll('.pcard'));
    var padV = 0, nmGap = 0;
    var probe = root.querySelector('.pcard');
    if (probe) {
      var pcs = getComputedStyle(probe);
      padV = (parseFloat(pcs.paddingTop) || 0) + (parseFloat(pcs.paddingBottom) || 0);
      var pnm = probe.querySelector('.pcard-name') || root.querySelector('.pcard-name');
      if (pnm) nmGap = parseFloat(getComputedStyle(pnm).marginTop) || 0;
    }
    for (var round = 0; round < 8 && dirty.length; round++) {
      var next = [], rest = [];
      var shrink = function(el, ratio) {
        var cur = curSize(el), px = Math.max(0.2, cur * ratio);
        if (px < cur - 0.1) { next.push([el, px]); return true; }
        return false;
      };
      dirty.forEach(function(card) {
        var eq = card.querySelector('.pcard-eq');
        var nm = card.querySelector('.pcard-name');
        var hit = false;
        if (eq) {
          var k = eq.querySelector('.katex');
          var tW = Math.max(k ? k.getBoundingClientRect().width : 0, eq.scrollWidth);
          var tH = k ? k.getBoundingClientRect().height : eq.scrollHeight;
          var r = Math.min(eq.clientWidth / Math.max(tW, 0.01),
            (card.clientHeight - padV - (nm ? nm.offsetHeight + nmGap : 0)) / Math.max(tH, 0.01));
          if (r < 0.995 && shrink(eq, r)) hit = true;
        }
        if (nm && nm.scrollHeight > nm.clientHeight + 1) {
          if (shrink(nm, nm.clientHeight / nm.scrollHeight)) hit = true;
        }
        if (!hit && eq && card.scrollHeight > card.clientHeight + 1) {
          if (shrink(eq, card.clientHeight / card.scrollHeight)) hit = true;
        }
        if (hit) rest.push(card);
      });
      if (!next.length) break;
      next.forEach(function(j) { j[0].style.fontSize = j[1] + 'px'; });
      dirty = rest;
    }
    Array.prototype.forEach.call(root.querySelectorAll('.pcard'), function(card) {
      var eq = card.querySelector('.pcard-eq');
      var nm = card.querySelector('.pcard-name:not(.pcard-name-back)');
      if (!eq) return;
      var base = baseSize(eq), cur = curSize(eq);
      if (!base) return;
      var k = eq.querySelector('.katex');
      var tW = k ? k.getBoundingClientRect().width : eq.scrollWidth;
      var tH = k ? k.getBoundingClientRect().height : eq.scrollHeight;
      var aH = card.clientHeight - padV - (nm ? nm.offsetHeight + nmGap : 0);
      if (eq.clientWidth <= 0 || aH <= 0 || tW <= 0 || tH <= 0) return;
      if (card.scrollHeight > card.clientHeight + 1 || eq.scrollWidth > eq.clientWidth + 1) return;
      var rCur = Math.min(eq.clientWidth / tW, aH / tH);
      if (rCur < 1.05) return;
      var sNew = quantScale(Math.min(rCur * (cur / base), 1.5));
      if (sNew > cur / base + 0.01) eq.style.fontSize = (base * sNew) + 'px';
    });
  }
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
  }
  function openDialog() {
    if (!hasSelection()) {
      if (window.showToast) window.showToast(t('print.empty'), 'error');
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
    printState(false, false);
    refreshIcons();
    renderLists();
    refreshLists();
    schedulePreview(true);
  }
  function closeDialog() {
    var el = dlgEl();
    if (el) el.classList.remove('open');
  }
  function setPreviewToggle(btn, on) {
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    btn.classList.toggle('active', on);
    btn.innerHTML = '<i data-lucide="' + (on ? 'arrow-left' : 'eye') + '" width="14" height="14"></i> ' +
      esc(on ? t('create.back') : t('print.preview'));
    refreshIcons();
  }
  function selectionPayload() {
    var fo = {}, qo = {}, cf = [], cq = [], off = {}, qoff = {};
    getF().forEach(function(id) { if (store.f[id]) fo[id] = store.f[id]; });
    getQ().forEach(function(id) { if (store.q[id]) qo[id] = store.q[id]; });
    store.cf.forEach(function(c) { if (c && c.i) cf.push(c); });
    store.cq.forEach(function(c) { if (c && c.i) cq.push(c); });
    Object.keys(store.off || {}).forEach(function(k) { if (ID_RE.test(k)) off[k] = 1; });
    Object.keys(store.qoff || {}).forEach(function(k) { if (ID_RE.test(k)) qoff[k] = 1; });
    return { f: getF(), q: getQ(), fo: fo, cf: cf, qo: qo, cq: cq, off: off, qoff: qoff };
  }
  function postPayload(url, obj) {
    var headers = { 'Accept': 'application/json', 'Content-Type': 'application/json' };
    if (window._csrfToken) headers['X-CSRF-Token'] = window._csrfToken;
    return fetch(url, { method: 'POST', headers: headers, body: JSON.stringify(obj) }).then(function(r) {
      if (!r.ok) return r.text().then(function(txt) {
        var err = new Error('request failed: ' + r.status);
        try { var d = JSON.parse(txt); if (d && d.error) err = new Error(d.error); } catch (e) {}
        err.status = r.status;
        throw err;
      });
      return r.json();
    });
  }
  function copyShareLink() {
    if (!hasSelection()) {
      if (window.showToast) window.showToast(t('print.empty'), 'error');
      return;
    }
    ensureUrlSynced(function(ok) {
      if (!ok) return;
      var link = location.href;
      var done = function(ok2) {
        if (window.showToast) window.showToast(ok2 ? t('print.share_copied') : t('print.share_failed'), ok2 ? 'success' : 'error');
      };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(link).then(function() { done(true); }, function() { done(false); });
      else {
        var ta = document.createElement('textarea');
        ta.value = link;
        document.body.appendChild(ta);
        try { ta.select(); done(document.execCommand('copy')); } catch (e) { done(false); }
        document.body.removeChild(ta);
      }
    });
  }
  function refreshLists() {
    if (!isDialogOpen() || typeof fetch === 'undefined') return;
    if (dlg.loading) { dlg.pendingRefresh = true; return; }
    dlg.loading = true;
    var done = function() {
      dlg.loading = false;
      if (dlg.pendingRefresh) { dlg.pendingRefresh = false; refreshLists(); }
      else renderPrintPreview();
    };
    try {
      postPayload('/api/selection-preview', selectionPayload()).then(function(data) {
        dlg.data = data;
        renderLists();
        done();
      }).catch(done);
    } catch (e) { done(); }
  }
  function setList(listId, wrapId, html) {
    var list = document.getElementById(listId);
    if (list) list.innerHTML = html;
    if (!wrapId) return;
    var wrap = document.getElementById(wrapId);
    if (wrap) wrap.style.display = html ? '' : 'none';
  }
  function nameOf(cache, id) { return cache[id] || { id: id, name: id }; }
  function checkRow(kind, entry, checked) {
    var sym = (kind === 'q' && entry.symbol)
      ? '<span class="print-row-sym"><span class="latex-observe" data-latex="' + esc(entry.symbol) + '"></span></span>' : '';
    var editTip = kind === 'f' ? t('print.edit_formula') : t('print.edit_quantity');
    var edited = kind === 'f' ? isEditedF(entry.id) : isEditedQ(entry.id);
    return '<li><label class="opt-check print-row' + (checked ? '' : ' is-off') + '">' +
      '<input type="checkbox" data-print-check="' + kind + ':' + esc(entry.id) + '"' + (checked ? ' checked' : '') + '>' +
      '<span class="box" aria-hidden="true"></span>' + sym +
      '<span class="print-row-name">' + esc(entry.name) + '</span>' +
      '<button type="button" class="filter-btn print-row-edit' + (edited ? ' is-edited' : '') + '" data-edit-' + (kind === 'f' ? 'formula' : 'quantity') + '="' + esc(entry.id) + '"' +
      ' title="' + esc(editTip) + '" aria-label="' + esc(editTip) + ': ' + esc(entry.name) + '">' +
      '<i data-lucide="pencil" width="14" height="14"></i></button></label></li>';
  }
  function renderLists() {
    syncDlgControls();
    var i, entry, id;
    var fD = (dlg.data && dlg.data.formulas) || [], qD = (dlg.data && dlg.data.quantities) || [],
        cD = (dlg.data && dlg.data.custom_quantities) || [],
        sD = (dlg.data && dlg.data.in_formula_new) || [];
    for (i = 0; i < fD.length; i++) { entry = fD[i]; dlg.knownF[entry.id] = { id: entry.id, name: entry.name }; }
    for (i = 0; i < qD.length; i++) { entry = qD[i]; dlg.knownQ[entry.id] = { id: entry.id, name: entry.name, symbol: entry.symbol }; }
    for (i = 0; i < cD.length; i++) { entry = cD[i]; if (!dlg.knownQ[entry.id]) dlg.knownQ[entry.id] = { id: entry.id, name: entry.name, symbol: entry.symbol }; }
    for (i = 0; i < sD.length; i++) { entry = sD[i]; if (!dlg.knownQ[entry.id]) dlg.knownQ[entry.id] = { id: entry.id, name: entry.name, symbol: entry.symbol }; }
    // Cap history so long sessions cannot grow the dialog lists unboundedly.
    (function capKnown(map, max) {
      var keys = Object.keys(map);
      if (keys.length > max) keys.slice(0, keys.length - max).forEach(function(k) { delete map[k]; });
    })(dlg.knownF, _SAFETY_IDS);
    (function capKnownQ(map, max) {
      var keys = Object.keys(map);
      if (keys.length > max) keys.slice(0, keys.length - max).forEach(function(k) { delete map[k]; });
    })(dlg.knownQ, _SAFETY_IDS);
    var fsel = getF(), qsel = getQ(), seen = Object.create(null), html = '';
    var focusKey = null;
    try {
      var ae = document.activeElement;
      if (ae && ae.matches && ae.matches('input[data-print-check]')) focusKey = ae.getAttribute('data-print-check');
    } catch (err) {}
    for (i = 0; i < fD.length; i++) { entry = fD[i]; if (fsel.indexOf(entry.id) !== -1 && !store.off[entry.id]) { seen[entry.id] = 1; html += checkRow('f', entry, true); } }
    for (i = 0; i < fsel.length; i++) { id = fsel[i]; if (!seen[id]) { seen[id] = 1; html += checkRow('f', nameOf(dlg.knownF, id), !store.off[id]); } }
    Object.keys(dlg.knownF).forEach(function(k) { if (!seen[k]) html += checkRow('f', dlg.knownF[k], false); });
    store.cf.forEach(function(c) {
      id = c.i;
      if (seen[id] || fsel.indexOf(id) !== -1) return;
      seen[id] = 1;
      html += checkRow('f', { id: id, name: c.n || id }, !store.off[id]);
    });
    setList('print-flist', null, html);
    seen = Object.create(null); html = '';
    var qAll = qD.concat(cD.filter(function(e) { return qD.indexOf(e) === -1; }));
    for (i = 0; i < qAll.length; i++) { entry = qAll[i]; if (qsel.indexOf(entry.id) !== -1 && !store.qoff[entry.id]) { seen[entry.id] = 1; html += checkRow('q', entry, true); } }
    for (i = 0; i < qsel.length; i++) { id = qsel[i]; if (!seen[id]) { seen[id] = 1; html += checkRow('q', nameOf(dlg.knownQ, id), !store.qoff[id]); } }
    for (i = 0; i < sD.length; i++) { entry = sD[i]; if (!seen[entry.id]) { seen[entry.id] = 1; html += checkRow('q', entry, false); } }
    Object.keys(dlg.knownQ).forEach(function(k) { if (!seen[k]) html += checkRow('q', dlg.knownQ[k], false); });
    store.cq.forEach(function(c) {
      id = c.i;
      if (seen[id] || qsel.indexOf(id) !== -1) return;
      seen[id] = 1;
      html += checkRow('q', { id: id, name: c.n || id, symbol: c.s || '' }, !store.qoff[id]);
    });
    setList('print-qlist', null, html);
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
    refreshIcons();
  }
  // ---- Edit modal (equation editor for formulas, fields for quantities) ----
  var editCtx = null;
  function editEl() { return document.getElementById('print-edit-modal'); }
  function isEditOpen() { var el = editEl(); return !!(el && el.classList.contains('open')); }
  function setEditModal(open) { if (window.SFUtils && window.SFUtils.setModal) window.SFUtils.setModal('print-edit-modal', open); }
  function closeEdit() { setEditModal(false); editCtx = null; }
  function editBtn(label, primary, id) {
    return '<button type="button" class="btn-' + (primary ? 'primary' : 'ghost') + ' btn-sm"' +
      (id ? ' id="' + id + '"' : '') + '>' + esc(label) + '</button>';
  }
  // One label wrapper on the shared dialog form stack (translate-form/detail-desc/tr-label-row).
  function peField(label, control) {
    return '<div class="detail-desc"><div class="tr-label-row"><span>' + esc(label) + '</span></div>' + control + '</div>';
  }
  // Same autosize as /create's autoGrow: no resize handle, grows with content.
  function peAutosize(el) {
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = el.scrollHeight + 'px';
  }
  function isCustomF(id) { return store.cf.some(function(c) { return c && c.i === id; }); }
  function isCustomQ(id) { return store.cq.some(function(c) { return c && c.i === id; }); }
  function dropSnapshot(kind, id) {
    var b = storeTriple(kind);
    dropSnap(b[0], b[1], b[2], id);
  }
  function removeEditModal() {
    if (!editCtx || !editCtx.id) return;
    var id = editCtx.id, kind = editCtx.kind;
    var wasCustom = kind === 'f' ? isCustomF(id) : isCustomQ(id);
    if (wasCustom) delete (kind === 'f' ? dlg.knownF : dlg.knownQ)[id];
    closeEdit();
    commit(function() { dropSnapshot(kind, id); });
    if (window.showToast) window.showToast(t('print.custom_removed'), 'info');
  }
  // Same cell classes as /create's override table; rows built inline (no second builder).
  function syncOverrideTable(variables) {
    var wrap = document.getElementById('pe-overrides');
    if (!wrap) return;
    var keys = ((variables || []).map(function(v) { return v.key; })).join(',');
    if (wrap.getAttribute('data-keys') === keys) return;
    wrap.setAttribute('data-keys', keys);
    var rows = (variables || []).map(function(v) {
      var key = v.key || '', symbol = v.symbol || '', name = v.name || v.id || '';
      return '<tr data-symbol="' + esc(symbol) + '" data-key="' + esc(key) + '"><td class="qty-sym-cell">' + (symbol ? '<span class="qty-symbol"></span> ' : '') + esc(name) + (v.alias ? '[' + esc(v.alias) + ']' : '')
        + '</td><td><input class="text-field" data-ov-field="symbol" data-ov-key="' + esc(key) + '" value="' + esc(v.symbol_overwrite || '') + '" placeholder="' + esc(symbol) + '"></td>'
        + '<td><input class="text-field" data-ov-field="name" data-ov-key="' + esc(key) + '" value="' + esc(v.name_overwrite || '') + '" placeholder="' + esc(name) + '"></td></tr>';
    }).join('');
    wrap.innerHTML = rows ? '<table class="var-table var-overrides-table"><colgroup><col class="var-c1"><col class="var-c2"><col class="var-c3"></colgroup><thead><tr><th>' + esc(t('detail.quantity')) + '</th><th>' + esc(t('create.column_symbol_override')) + '</th><th>' + esc(t('create.column_name_override')) + '</th></tr></thead><tbody>' + rows + '</tbody></table>' : '';
    if (typeof katex !== 'undefined') wrap.querySelectorAll('tr[data-symbol]').forEach(function(tr) {
      var sym = tr.querySelector('.qty-symbol');
      if (tr.dataset.symbol && sym) { try { katex.render(tr.dataset.symbol, sym, { displayMode: false, throwOnError: false }); } catch (e) {} }
    });
  }
  function collectOverrides() {
    var out = {};
    document.querySelectorAll('#print-edit-body input[data-ov-key]').forEach(function(inp) {
      var key = inp.getAttribute('data-ov-key'), field = inp.getAttribute('data-ov-field');
      if (!key || !field || !inp.value) return;
      (out[key] = out[key] || {})[field] = inp.value;
    });
    return out;
  }
  var peTimer = null, peSeq = 0;
  function scheduleFormulaParse() {
    if (!editCtx || editCtx.kind !== 'f') return;
    if (peTimer) clearTimeout(peTimer);
    peTimer = setTimeout(runFormulaParse, 300);
  }
  // No latex preview here (unlike /create): parse only feeds tokens + override table.
  function runFormulaParse(after) {
    if (!editCtx || editCtx.kind !== 'f') { if (after) after(null); return; }
    var equation = ((document.getElementById('pe-equation') || {}).value || '');
    if (!equation.trim()) { editCtx.tokens = null; if (after) after(null); return; }
    var mySeq = ++peSeq;
    postPayload('/api/formula-parse', { equation: equation, overrides: collectOverrides() }).then(function(data) {
      if (!editCtx || mySeq !== peSeq) return;
      editCtx.tokens = data.tokens || null;
      editCtx.parseError = '';
      syncOverrideTable(data.variables || []);
      if (after) after(data);
    }).catch(function(err) {
      if (!editCtx || mySeq !== peSeq) return;
      editCtx.tokens = null;
      editCtx.parseError = (err && err.message) || 'error';
      if (after) after(null);
    });
  }
  function editActions(kind, id, isNew) {
    var rm = '';
    if (!isNew) {
      var custom = kind === 'f' ? isCustomF(id) : isCustomQ(id);
      var snap = kind === 'f' ? store.f[id] : store.q[id];
      if (custom || snap) rm = editBtn(t(custom ? 'print.remove' : 'print.revert', custom ? 'Remove' : 'Revert'), false, 'pe-remove');
    }
    return rm + editBtn(t('print.cancel'), false, 'pe-cancel')
      + editBtn(t('print.apply'), true, 'pe-apply');
  }
  function openFormulaEditor(id) {
    if (!window.SFApi) return;
    editCtx = { kind: 'f', id: id || null, tokens: null, parseError: '' };
    var isNew = !id;
    var title = document.getElementById('print-edit-title');
    var body = document.getElementById('print-edit-body');
    var actions = document.getElementById('print-edit-actions');
    if (title) title.textContent = isNew ? t('print.new_formula') : t('print.edit_formula') + ': ' + id;
    var snap = id ? store.f[id] : null;
    var show = function(name, equation, variables) {
      if (!editCtx || editCtx.kind !== 'f') return;
      if (body) {
        body.innerHTML = '<div class="translate-form">'
          + (isNew ? peField(t('print.custom_id', 'ID'), '<input id="pe-id" class="text-field" autocomplete="off" spellcheck="false">') : '')
          + peField(t('create.name', 'Name'), '<input id="pe-name" class="text-field" autocomplete="off" spellcheck="false" value="' + esc(name || '') + '">')
          + peField(t('create.equation', 'Equation'), '<textarea id="pe-equation" class="text-field auto-grow" rows="2" spellcheck="false" autocomplete="off">' + esc(equation || '') + '</textarea>')
          + '<div id="pe-overrides" data-keys=""></div></div>';
        syncOverrideTable(variables || []);
      }
      if (actions) actions.innerHTML = editActions('f', id, isNew);
      setEditModal(true);
      refreshIcons();
      scheduleFormulaParse();
      var ta = document.getElementById('pe-equation');
      peAutosize(ta);
      if (ta && ta.focus) { try { ta.focus(); } catch (e) {} }
    };
    if (isNew) { show('', '', []); return; }
    if (snap && snap.e) {
      var cVars = [];
      (snap.t || []).forEach(function(tok, idx) {
        if (tok && tok[0] === 'q') cVars.push({ key: tok[1] + '|' + (tok[4] || '') + '|' + (idx + 1), id: tok[1], alias: tok[4] || '', symbol: '', name: tok[1], symbol_overwrite: tok[2] || '', name_overwrite: tok[3] || '' });
      });
      show(snap.n || '', snap.e, cVars);
      return;
    }
    window.SFApi.getJSON('/api/formula-tokens?id=' + encodeURIComponent(id)).then(function(data) {
      show(data.name || '', data.equation || '', data.variables || []);
    }).catch(function(err) {
      editCtx = null;
      if (window.showToast) window.showToast(window.SFApi.serverMessage(err, t('print.custom_invalid')), 'error');
    });
  }
  function openQuantityEditor(id) {
    editCtx = { kind: 'q', id: id || null };
    var isNew = !id;
    var title = document.getElementById('print-edit-title');
    var body = document.getElementById('print-edit-body');
    var actions = document.getElementById('print-edit-actions');
    if (title) title.textContent = isNew ? t('print.new_quantity') : t('print.edit_quantity') + ': ' + id;
    var show = function(name, symbol, unit) {
      if (!editCtx || editCtx.kind !== 'q') return;
      if (body) {
        body.innerHTML = '<div class="translate-form">'
          + (isNew ? peField(t('print.custom_id', 'ID'), '<input id="pe-id" class="text-field" autocomplete="off" spellcheck="false">') : '')
          + peField(t('print.name', 'Name'), '<input id="pe-name" class="text-field" autocomplete="off" spellcheck="false" value="' + esc(name || '') + '">')
          + peField(t('print.symbol', 'Symbol'), '<input id="pe-symbol" class="text-field" autocomplete="off" spellcheck="false" value="' + esc(symbol || '') + '">')
          + peField(t('print.unit', 'Unit'), '<input id="pe-unit" class="text-field" autocomplete="off" spellcheck="false" value="' + esc(unit || '') + '">') + '</div>';
      }
      if (actions) actions.innerHTML = editActions('q', id, isNew);
      setEditModal(true);
      refreshIcons();
      var ta = document.getElementById('pe-name');
      if (ta && ta.focus) { try { ta.focus(); } catch (e) {} }
    };
    if (isNew) { show('', '', ''); return; }
    var snap = store.q[id];
    if (snap) { show(snap.n || '', snap.s || '', snap.u || ''); return; }
    window.SFApi.getJSON('/api/quantity-fields?id=' + encodeURIComponent(id)).then(function(data) {
      show(data.name || '', data.symbol || '', data.unit || '');
    }).catch(function(err) {
      editCtx = null;
      if (window.showToast) window.showToast(window.SFApi.serverMessage(err, t('print.custom_invalid')), 'error');
    });
  }
  // One routing for overrides vs customs, shared by store and pre-mint payloads.
  function storeTriple(kind) {
    return kind === 'f' ? [store.f, store.cf, store.off] : [store.q, store.cq, store.qoff];
  }
  function placeSnap(snaps, customs, off, kind, id, snap) {
    var sel = kind === 'f' ? getF() : getQ();
    if (sel.indexOf(id) !== -1) snaps[id] = snap;
    else {
      for (var i = customs.length - 1; i >= 0; i--) if (!customs[i] || customs[i].i === id) customs.splice(i, 1);
      customs.push(Object.assign({ i: id }, snap));
    }
    delete off[id];
  }
  function dropSnap(snaps, customs, off, id) {
    delete snaps[id];
    delete off[id];
    for (var i = customs.length - 1; i >= 0; i--) if (customs[i] && customs[i].i === id) customs.splice(i, 1);
  }
  function saveSnap(kind, id, snap) {
    var b = storeTriple(kind);
    placeSnap(b[0], b[1], b[2], kind, id, snap);
  }
  function applyEditModal() {
    if (!editCtx || !window.SFApi) return;
    if (editCtx.kind === 'f') applyFormulaEditor();
    else applyQuantityEditor();
  }
  function payloadWithSnap(kind, id, snap, oldId) {
    var p = selectionPayload();
    var b = kind === 'f' ? [p.fo, p.cf, p.off] : [p.qo, p.cq, p.qoff];
    placeSnap(b[0], b[1], b[2], kind, id, snap);
    if (oldId && oldId !== id) dropSnap(b[0], b[1], b[2], oldId);
    return p;
  }
  function applySnapWithMint(kind, id, snap, oldId) {
    postPayload('/api/selection-share', payloadWithSnap(kind, id, snap, oldId)).then(function(data) {
      if (!data || !data.sel) throw new Error('mint failed');
      saveSnap(kind, id, snap);
      if (oldId && oldId !== id) dropSnapshot(kind, oldId);
      closeEdit();
      adoptToken(data.sel);
      if (window.showToast) window.showToast(t('print.custom_added') + ': ' + id, 'info');
    }).catch(function() {
      if (window.showToast) window.showToast(t('print.too_large'), 'error');
    });
  }
  function applyFormulaEditor() {
    var idInput = document.getElementById('pe-id');
    var id = editCtx.id || ((idInput && idInput.value) || '').trim();
    var name = ((document.getElementById('pe-name') || {}).value || '').trim();
    var equation = ((document.getElementById('pe-equation') || {}).value || '').trim();
    if (!ID_RE.test(id || '')) {
      if (window.showToast) window.showToast(t('print.custom_id') + ': a-z 0-9 _ . -', 'error');
      return;
    }
    if (!equation) {
      if (window.showToast) window.showToast(t('print.custom_invalid'), 'error');
      return;
    }
    runFormulaParse(function(data) {
      if (!data || !data.tokens) {
        if (window.showToast) window.showToast(editCtx.parseError || t('print.custom_invalid'), 'error');
        return;
      }
      var oldId = editCtx.id;
      var snapF = { n: name || id, t: data.tokens, e: equation };
      applySnapWithMint('f', id, snapF, oldId);
    });
  }
  function applyQuantityEditor() {
    var idInput = document.getElementById('pe-id');
    var id = editCtx.id || ((idInput && idInput.value) || '').trim();
    var name = ((document.getElementById('pe-name') || {}).value || '').trim();
    var symbol = ((document.getElementById('pe-symbol') || {}).value || '').trim().slice(0, 100);
    var unit = ((document.getElementById('pe-unit') || {}).value || '').trim().slice(0, 200);
    if (!ID_RE.test(id || '')) {
      if (window.showToast) window.showToast(t('print.custom_id') + ': a-z 0-9 _ . -', 'error');
      return;
    }
    var snap = cleanQuantitySnap({ n: name || id, s: symbol, u: unit });
    if (!snap) {
      if (window.showToast) window.showToast(t('print.custom_invalid'), 'error');
      return;
    }
    var oldId = editCtx.id;
    applySnapWithMint('q', id, snap, oldId);
  }
  function schedulePreview(immediate) {
    if (!isDialogOpen()) return;
    if (previewTimer) clearTimeout(previewTimer);
    previewTimer = setTimeout(function() { previewTimer = null; renderPrintPreview(); }, immediate ? 50 : 600);
  }
  function printState(load, ready) {
    var l = document.getElementById('print-loading');
    if (l) l.hidden = !load;
    var b = document.querySelector('[data-action="print-now"]');
    if (b) b.disabled = !ready;
  }
  function renderPrintPreview() {
    var pv = document.getElementById('print-preview');
    if (!pv || !isDialogOpen()) return;
    ensurePreviewCss();
    ensurePreviewZoom();
    var g = printGeom(), items = hasSelection() ? printItems() : [];
    pv.style.zoom = ''; // legacy cleanup: zoom now lives on .pview-zoom
    if (!items.length) {
      pv.innerHTML = '<p class="print-hint">' + esc(t('print.empty')) + '</p>';
      printState(false, false);
      return;
    }
    var mySeq = ++renderSeq;
    printState(true, false);
    pv.innerHTML = '<div class="pview-zoom">' + printPageList(g, items).map(function(p) { return printPageHtml(g, p); }).join('') + '</div>';
    if (window.renderLatexIn) window.renderLatexIn(pv);
    fitCards(pv);
    previewFit = fitZoomFor(pv);
    applyPreviewZoom();
    if (typeof katex === 'undefined' && window.onKatexReady && !katexRetryArmed
        && !document.documentElement.classList.contains('katex-ready')) {
      katexRetryArmed = true;
      window.onKatexReady(function() { katexRetryArmed = false; if (isDialogOpen()) renderPrintPreview(); });
    }
    var finish = function() {
      if (mySeq !== renderSeq || !isDialogOpen() || !pv.isConnected) return;
      var zEl = pv.querySelector('.pview-zoom');
      if (zEl) zEl.style.zoom = '';
      fitCards(pv);
      previewFit = fitZoomFor(pv);
      applyPreviewZoom();
      if (typeof katex === 'undefined' && !document.documentElement.classList.contains('katex-ready')) return;
      printState(false, true);
    };
    if (document.fonts && document.fonts.ready) {
      Promise.race([document.fonts.ready, new Promise(function(r) { setTimeout(r, 3000); })]).then(finish);
    } else {
      finish();
    }
    setTimeout(function() {
      if (mySeq !== renderSeq || !isDialogOpen() || !pv.isConnected) return;
      var b = document.querySelector('[data-action="print-now"]');
      if (b && b.disabled) printState(false, true);
    }, 10000);
  }
  function buildPrintDocument(g, pagesHtml) {
    var css = '@page{size:' + g.pw + 'mm ' + g.ph + 'mm;margin:0}'
      + 'html,body{margin:0;padding:0;background:#fff}'
      + '.pview-page{page-break-after:always;break-after:page}'
      + '.pview-page:last-child{page-break-after:auto;break-after:auto}'
      + PVIEW_CSS;
    return '<!DOCTYPE html><html lang="' + esc(document.documentElement.lang || 'en') + '"><head><meta charset="utf-8"><title>'
      + esc(t('print.title')) + '</title>'
      + '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.17.0/dist/katex.min.css">'
      + '<style>' + css + '</style></head><body>' + pagesHtml
      + '<script>window.addEventListener("load",function(){'
      + 'function done(){setTimeout(function(){window.print();},100);}'
      + 'if(document.fonts&&document.fonts.ready){'
      + 'Promise.race([document.fonts.ready,new Promise(function(r){setTimeout(r,2500);})]).then(done);}'
      + 'else{done();}});</' + 'script>'
      + '</body></html>';
  }
  function openPrintWindow() {
    var pv = document.getElementById('print-preview');
    var items = printItems();
    if (!items.length || !pv) {
      if (window.showToast) window.showToast(t('print.empty'), 'error');
      return;
    }
    var html = '';
    pv.querySelectorAll('.pview-page').forEach(function(pg) { html += pg.outerHTML; });
    if (!html) {
      if (window.showToast) window.showToast(t('print.failed'), 'error');
      return;
    }
    var w = window.open('', '_blank');
    if (!w) {
      if (window.showToast) window.showToast(t('print.popup_blocked'), 'error');
      return;
    }
    w.document.write(buildPrintDocument(printGeom(), html));
    w.document.close();
  }
  document.addEventListener('input', function(e) {
    if (e.target && (e.target.id === 'print-cols' || e.target.id === 'print-rows'))
      setSlider(e.target.id, e.target.id === 'print-cols' ? 'print-cols-fill' : 'print-rows-fill',
        e.target.id === 'print-cols' ? 'print-cols-val' : 'print-rows-val');
    if (e.target && e.target.id === 'pe-equation') peAutosize(e.target);
    if (e.target && (e.target.id === 'pe-equation' || (e.target.getAttribute && e.target.getAttribute('data-ov-key'))))
      scheduleFormulaParse();
  });
  document.addEventListener('change', function(e) {
    if (!e.target) return;
    if (e.target.matches && e.target.matches('input[data-print-check]')) {
      var parts = (e.target.getAttribute('data-print-check') || '').split(':');
      var kind = parts[0], pid = parts.slice(1).join(':');
      if (!ID_RE.test(pid)) return;
      var checked = e.target.checked;
      var inCustomF = store.cf.some(function(c) { return c && c.i === pid; });
      if (kind === 'f' && inCustomF) {
        commit(function() { if (checked) delete store.off[pid]; else store.off[pid] = 1; });
        return;
      }
      var inCustomQ = store.cq.some(function(c) { return c && c.i === pid; });
      if (kind === 'q' && inCustomQ) {
        commit(function() { if (checked) delete store.qoff[pid]; else store.qoff[pid] = 1; });
        return;
      }
      var key = kind === 'f' ? 'selected_formulas' : 'selected_quantities';
      var cur = key === 'selected_formulas' ? getF() : getQ();
      if (checked) {
        if (cur.indexOf(pid) === -1) updateSelection(key, cur.concat([pid]));
      } else updateSelection(key, cur.filter(function(x) { return x !== pid; }));
      return;
    }
    if (e.target.id === 'print-cols') { dlg.cols = clamp(e.target.value, 4, 1, 32); schedulePreview(); }
    else if (e.target.id === 'print-rows') { dlg.rows = clamp(e.target.value, 16, 1, 32); schedulePreview(); }
    else if (e.target.id === 'print-borders') { dlg.borders = !!e.target.checked; schedulePreview(); }
    else if (e.target.id === 'print-paper') { dlg.paper = e.target.value; schedulePreview(); }
  });

  window.SFUtils.registerActions({
    'toggle-select-mode': function(e) { e.stopPropagation(); onToggle(); },
    'toggle-show-selected': function(e) { e.stopPropagation(); onShowToggle(); },
    'context-select': function(e) { e.stopPropagation(); onContextSelect(); },
    'goto-print': function(e) { e.stopPropagation(); openDialog(); },
    'close-print': function(e) { e.stopPropagation(); closeDialog(); },
    'close-print-edit': function(e) { e.stopPropagation(); closeEdit(); },
    'print-now': function(e) { e.stopPropagation(); openPrintWindow(); },
    'share-selection': function(e) { e.stopPropagation(); copyShareLink(); }
  });

  // Read ?sel= into memory. Called on boot, SPA navigation, back/forward.
  function syncFromUrl() {
    readUrlToStore().then(function() {
      syncUI();
      if (isDialogOpen()) { refreshLists(); schedulePreview(true); }
    });
  }
  window.SFSelection = { syncFromUrl: syncFromUrl };

  readUrlToStore().then(function() { syncUI(); });

  new MutationObserver(syncUI).observe(document.getElementById('main-content') || document.documentElement, { childList: true, subtree: true });
  window.addEventListener('popstate', function() { syncFromUrl(); if (isDialogOpen()) { refreshLists(); schedulePreview(true); } });
  var resizeTimer = null;
  window.addEventListener('resize', function() {
    if (!isDialogOpen()) return;
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function() { resizeTimer = null; schedulePreview(true); }, 300);
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', syncUI);
  else syncUI();
})();
