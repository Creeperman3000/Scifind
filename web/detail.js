/* eslint-disable no-undef */
'use strict';
/* Conversion cells ship for the default reference only; picking another
   reference fetches its column from /api/units-column (cached per column). */

  function $(id) { return window.SFUtils.byId(id); }
  function $$(sel, root) { return window.SFUtils.bySel(sel, root); }

  function _setUnitsCell(td, latex) {
    if (latex === null || latex === undefined) { td.innerHTML = '&ndash;'; return; }
    td.innerHTML = '';
    var span = document.createElement('span');
    span.className = 'latex-observe';
    span.setAttribute('data-latex', latex);
    td.appendChild(span);
    renderLatexEl(span);
  }

  /* One pass per table: ref highlight + button state + conversion cell. */
  function _syncUnitsTable(table, unitsState) {
    table.querySelectorAll('tbody tr[data-unit-id]').forEach(function(tr) {
      var unitId = tr.getAttribute('data-unit-id'), isRef = unitId === unitsState.ref;
      tr.classList.toggle('is-ref', isRef);
      var btn = tr.querySelector('.units-ref-btn');
      if (btn) { btn.disabled = isRef; btn.setAttribute('aria-pressed', isRef ? 'true' : 'false'); }
      var td = tr.querySelector('td.uv-conv');
      if (!td) return;
      if (unitsState.loading && !isRef) { td.textContent = '…'; return; }
      _setUnitsCell(td, isRef ? null : (unitsState.latex_by_ref[unitId] || {})[unitsState.ref]);
    });
  }

  function _syncUnitsSection(section) {
    var unitsState = section._unitsState;
    if (!unitsState) return;
    section.querySelectorAll('.units-ref-name').forEach(function(span) {
      span.textContent = unitsState.ref_labels[unitsState.ref] || '';
    });
    section.querySelectorAll('table[data-units-dynamic]').forEach(function(table) {
      _syncUnitsTable(table, unitsState);
    });
    if (typeof renderMathInContent === 'function') renderMathInContent();
  }

  function _stripHtml(raw) {
    var tmp = document.createElement('div');
    tmp.innerHTML = raw;
    return (tmp.textContent || tmp.innerText || '').trim();
  }

  function _setupUnitsTable(table) {
    var section = table.closest('.detail-section');
    var dataEl = section && section.querySelector('script.units-table-data');
    if (!dataEl) return;
    /* Both tables of a section share one reference-unit state, so a pick in either drives both. */
    if (!section._unitsState) {
      var tableData;
      try { tableData = JSON.parse(dataEl.textContent); } catch (e) { return; }
      var unitsState = { ref: tableData.ref, quantity: tableData.quantity,
        cols: {}, latex_by_ref: {}, ref_labels: {}, loading: false };
      (tableData.entries || []).concat(tableData.si_entries || []).forEach(function(entry) {
        var col = unitsState.latex_by_ref[entry.id] || (unitsState.latex_by_ref[entry.id] = {});
        col[tableData.ref] = entry.latex;
        unitsState.ref_labels[entry.id] = _stripHtml(entry.label || entry.name || entry.id);
      });
      unitsState.cols[tableData.ref] = true;
      section._unitsState = unitsState;
    }
    _syncUnitsSection(section);
  }

  function initUnitsTables(scope) {
    var root = scope || document;
    root.querySelectorAll('table[data-units-dynamic]').forEach(_setupUnitsTable);
    onKatexReady(function() {
      renderLatexIn(root);
      renderMathInContent();
    });
  }

  function pickUnitsRef(btn) {
    var section = btn.closest('.detail-section');
    if (!section || !section._unitsState) return;
    var st = section._unitsState;
    if (st.loading) return;
    var unitId = btn.getAttribute('data-unit-id');
    if (unitId == null || !st.latex_by_ref[unitId] || unitId === st.ref) return;
    if (st.cols[unitId]) { st.ref = unitId; _syncUnitsSection(section); return; }
    var prev = st.ref;
    st.ref = unitId;
    st.loading = true;
    _syncUnitsSection(section);
    _fetchUnitsColumn(st, unitId).then(function(ok) {
      st.loading = false;
      if (!ok) st.ref = prev;
      _syncUnitsSection(section);
    });
  }

  function _fetchUnitsColumn(st, ref) {
    var params = 'quantity=' + encodeURIComponent(st.quantity) + '&ref=' + encodeURIComponent(ref);
    Object.keys(st.latex_by_ref).forEach(function(id) { params += '&id=' + encodeURIComponent(id); });
    return fetch('/api/units-column?' + params, { headers: { Accept: 'application/json' } })
      .then(function(resp) { return resp.ok ? resp.json() : null; })
      .then(function(data) {
        if (!data || data.ref !== ref || !data.column) return false;
        Object.keys(data.column).forEach(function(id) {
          if (st.latex_by_ref[id]) st.latex_by_ref[id][ref] = data.column[id];
        });
        st.cols[ref] = true;
        return true;
      })
      .catch(function() { return false; });
  }

  var UNITS_SORT_COLS = { unit: ['name'], system: ['system'], conversion: ['offset', 'value'] };

  function _unitsSortState(section) {
    if (!section._unitsSort) {
      section._unitsSort = {
        order: ['system', 'offset', 'value', 'name'],
        dirs: { system: 1, offset: 1, value: 1, name: 1 },
        active: null
      };
    }
    return section._unitsSort;
  }

  function _rowSortVal(tr, key) {
    var d = tr.dataset || {};
    if (key === 'system') return [parseInt(d.sSys || '2', 10), d.sSysname || ''];
    if (key === 'offset' || key === 'value') {
      var v = parseFloat(key === 'offset' ? d.sAff : d.sVal);
      return isNaN(v) ? Infinity : v;
    }
    return d.sName || '';
  }

  function _cmpUnitsRows(a, b, st) {
    for (var i = 0; i < st.order.length; i++) {
      var k = st.order[i], dir = st.dirs[k] || 1, cmp = 0;
      if (k === 'system') {
        var av = _rowSortVal(a, 'system'), bv = _rowSortVal(b, 'system');
        cmp = (av[0] - bv[0]) || (av[1] < bv[1] ? -1 : av[1] > bv[1] ? 1 : 0);
      } else if (k === 'offset' || k === 'value') {
        cmp = _rowSortVal(a, k) - _rowSortVal(b, k);
      } else {
        var an = _rowSortVal(a, 'name'), bn = _rowSortVal(b, 'name');
        cmp = an < bn ? -1 : an > bn ? 1 : 0;
      }
      if (cmp) return dir * cmp;
    }
    return 0;
  }

  function _syncUnitsSortIcons(section) {
    var st = _unitsSortState(section);
    section.querySelectorAll('.units-sort-btn').forEach(function(btn) {
      var col = btn.getAttribute('data-col'), keys = UNITS_SORT_COLS[col] || [];
      var icon = 'chevrons-up-down';
      if (col && col === st.active && keys.length) {
        icon = (st.dirs[keys[0]] || 1) === 1 ? 'chevron-up' : 'chevron-down';
      }
      btn.innerHTML = '<i data-lucide="' + icon + '" width="14" height="14"></i>';
    });
    if (typeof refreshIcons === 'function') refreshIcons();
  }

  function sortUnitsTable(btn) {
    var section = btn.closest('.detail-section');
    var keys = section && UNITS_SORT_COLS[btn.getAttribute('data-col')];
    if (!section || !keys) return;
    var st = _unitsSortState(section);
    if (st.active === btn.getAttribute('data-col')) {
      keys.forEach(function(k) { st.dirs[k] = -(st.dirs[k] || 1); });
    } else {
      st.order = keys.concat(st.order.filter(function(k) { return keys.indexOf(k) < 0; }));
      keys.forEach(function(k) { st.dirs[k] = 1; });
      st.active = btn.getAttribute('data-col');
    }
    section.querySelectorAll('table[data-units-dynamic] tbody').forEach(function(tb) {
      var pin = tb.querySelector('.si-toggle-row');
      Array.prototype.slice.call(tb.querySelectorAll('tr[data-unit-id]'))
        .sort(function(a, b) { return _cmpUnitsRows(a, b, st); })
        .forEach(function(r) { tb.insertBefore(r, pin); });
    });
    _syncUnitsSortIcons(section);
  }

  function toggleSiPrefixes(trigger) {
    var section = trigger.closest('.detail-section');
    var table = section && section.querySelector('.si-prefix-table');
    if (!table) return;
    var open = table.classList.toggle('si-expanded');
    var row = table.querySelector('.si-toggle-row');
    if (row) {
      row.setAttribute('aria-expanded', open ? 'true' : 'false');
      row.setAttribute('title', row.getAttribute(open ? 'data-less' : 'data-more') || '');
    }
  }

  (function() {
    var mc = $('main-content');
    if (!mc || typeof MutationObserver === 'undefined') return;
    new MutationObserver(function(muts) {
      var found = muts.some(function(m) {
        return Array.prototype.some.call(m.addedNodes, function(n) {
          return n.nodeType === 1 && n.querySelector &&
            (n.matches('table[data-units-dynamic]') || n.querySelector('table[data-units-dynamic]'));
        });
      });
      if (found) initUnitsTables(mc);
    }).observe(mc, { childList: true, subtree: true });
  })();
  /* Big constant display: integer/dot/digits are \htmlClass-wrapped server-side.
     Hide trailing decimals until the box fits, then fade them via a gradient
     mask anchored at the mantissa's right edge so the \times10^ stays opaque.
     Hiding (not deleting) lets resizes bring trimmed digits back. */
  function layoutConstantValues() {
    $$('.constant-box').forEach(function(box) {
      var val = box.querySelector('.const-value');
      if (!val) return;
      var decs = Array.prototype.slice.call(val.querySelectorAll('.cv-dec'));
      var dot = val.querySelector('.cv-dot');
      if (!decs.length && !dot) return;
      decs.forEach(function(sp) { sp.style.display = ''; });
      if (dot) dot.style.display = '';
      val.style.maskImage = val.style.webkitMaskImage = '';
      var vis = decs.slice(), guard = decs.length + 1;
      while (box.scrollWidth > box.clientWidth && vis.length && guard-- > 0) vis.pop().style.display = 'none';
      if (dot) dot.style.display = vis.length ? '' : 'none';
      var anchor = vis.length ? vis[vis.length - 1]
        : (dot && dot.style.display !== 'none') ? dot : val.querySelector('.cv-int');
      if (!anchor) return;
      var vRect = val.getBoundingClientRect();
      var mantEnd = anchor.getBoundingClientRect().right - vRect.left;
      if (!vRect.width || mantEnd <= 0) return;
      var fadeW = Math.max(40, Math.min(mantEnd * 0.25, 160)), solid = Math.max(mantEnd - fadeW, 0);
      /* Digits dissolve; the exponent restores to opaque after the band. */
      var grad = 'linear-gradient(90deg, #000 0, #000 ' + solid.toFixed(1) + 'px, transparent ' + (mantEnd + 1).toFixed(1) + 'px';
      var timesEl = val.querySelector('.cv-times');
      if (timesEl) grad += ', #000 ' + Math.max(timesEl.getBoundingClientRect().left - vRect.left - 1, mantEnd + 1).toFixed(1) + 'px';
      val.style.webkitMaskImage = val.style.maskImage = grad + ')';
    });
  }
  function recheckConstantValues() {
    /* Two RAFs so layout settles after KaTeX writes new DOM. */
    requestAnimationFrame(function() {
      requestAnimationFrame(function() { layoutConstantValues(); });
    });
  }
  function copyFormula(fmt) {
    var menu = $('formula-copy-menu');
    if (menu) menu.classList.remove('open');
    var latex = $('formula-tex');
    if (!latex) return;
    var tex = latex.textContent;
    var labelMap = { latex: 'LaTeX', unicode: 'Unicode', png: 'PNG', svg: 'SVG' };
    if (fmt === 'latex') { window.SFUtils.copyText(tex, labelMap[fmt]); return; }
    var doCopy = null;
    if (fmt === 'unicode') {
      /* Server pre-renders Unicode for the formula page; the live create
         preview has no precomputed span, so convert via the API instead. */
      var pre = $('formula-unicode');
      if (pre && pre.textContent) { window.SFUtils.copyText(pre.textContent, labelMap[fmt]); return; }
      doCopy = window.SFApi.getJSON('/api/latex2unicode?tex=' + encodeURIComponent(tex))
        .then(function(data) { return navigator.clipboard.writeText(data.unicode); });
    } else if (fmt === 'png' || fmt === 'svg') {
      var url = 'https://latex.codecogs.com/' + fmt + '.latex?' + encodeURIComponent((fmt === 'png' ? '\\dpi{3000}' : '') + tex);
      doCopy = fetch(url).then(window.SFApi.checkOk).then(function(r) { return r.blob(); }).then(function(blob) {
        var item = {}; item['image/' + fmt] = blob;
        return navigator.clipboard.write([new ClipboardItem(item)]);
      });
    }
    if (doCopy) window.SFUtils.copyPromise(doCopy, labelMap[fmt] || fmt);
  }

  function toggleCopyMenu(e) {
    e.stopPropagation();
    var menu = $('formula-copy-menu');
    if (menu) menu.classList.toggle('open');
  }
