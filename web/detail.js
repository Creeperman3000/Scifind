/* eslint-disable no-undef */
'use strict';
/* Conversion cells are rendered server-side; picking a different
   reference row just swaps the pre-computed LaTeX (no client math). */

  function $(id) { return window.SFUtils.byId(id); }
  function $$(sel, root) { return window.SFUtils.bySel(sel, root); }
  function t(path, fallback) { return window.SFUtils.t(path, fallback); }

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
      var unitId = tr.getAttribute('data-unit-id');
      var isRef = unitId === unitsState.ref;
      tr.classList.toggle('is-ref', isRef);
      var btn = tr.querySelector('.units-ref-btn');
      if (btn) {
        btn.disabled = isRef;
        btn.setAttribute('aria-pressed', isRef ? 'true' : 'false');
      }
      var td = tr.querySelector('td.uv-conv');
      if (!td) return;
      if (isRef) { _setUnitsCell(td, null); return; }
      var latex = (unitsState.latex_by_ref[unitId] || {})[unitsState.ref];
      _setUnitsCell(td, latex);
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
      var unitsState = { ref: tableData.ref, latex_by_ref: {}, ref_labels: {} };
      (tableData.entries || []).concat(tableData.si_entries || []).forEach(function(entry) {
        unitsState.latex_by_ref[entry.id] = entry.latex_by_ref || {};
        unitsState.ref_labels[entry.id] = _stripHtml(entry.label || entry.name || entry.id);
      });
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
    var unitId = btn.getAttribute('data-unit-id');
    if (unitId == null || !section._unitsState.latex_by_ref[unitId]) return;
    section._unitsState.ref = unitId;
    _syncUnitsSection(section);
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
      for (var i = 0; i < muts.length; i++) {
        var added = muts[i].addedNodes;
        for (var j = 0; j < added.length; j++) {
          var n = added[j];
          if (n.nodeType !== 1 || !n.querySelector) continue;
          if (n.matches('table[data-units-dynamic]') || n.querySelector('table[data-units-dynamic]')) {
            initUnitsTables(mc);
            return;
          }
        }
      }
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
      var guard = decs.length + 1;
      while (box.scrollWidth > box.clientWidth && guard-- > 0) {
        var last = null;
        for (var i = decs.length - 1; i >= 0; i--) {
          if (decs[i].style.display !== 'none') { last = decs[i]; break; }
        }
        if (!last) break;
        last.style.display = 'none';
      }
      var visible = decs.filter(function(sp) { return sp.style.display !== 'none'; });
      if (dot) dot.style.display = visible.length ? '' : 'none';
      var anchor = visible.length ? visible[visible.length - 1]
        : (dot && dot.style.display !== 'none') ? dot : val.querySelector('.cv-int');
      if (!anchor) return;
      var vRect = val.getBoundingClientRect();
      var mantEnd = anchor.getBoundingClientRect().right - vRect.left;
      if (!vRect.width || mantEnd <= 0) return;
      var fadeW = Math.max(40, Math.min(mantEnd * 0.25, 160));
      var solid = Math.max(mantEnd - fadeW, 0);
      /* Digits dissolve; the exponent restores to opaque after the band. */
      var grad = 'linear-gradient(90deg, #000 0, #000 ' + solid.toFixed(1) +
                 'px, transparent ' + (mantEnd + 1).toFixed(1) + 'px';
      var timesEl = val.querySelector('.cv-times');
      if (timesEl) {
        var tStart = timesEl.getBoundingClientRect().left - vRect.left;
        grad += ', #000 ' + Math.max(tStart - 1, mantEnd + 1).toFixed(1) + 'px';
      }
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
    var latex = $('formula-tex');
    if (!latex) return;
    var tex = latex.textContent;
    var labelMap = { latex: 'LaTeX', unicode: 'Unicode', png: 'PNG', svg: 'SVG' };
    if (fmt === 'latex') {
      window.SFUtils.copyText(tex, labelMap[fmt]);
      return;
    }
    var doCopy = null;
    if (fmt === 'unicode') {
      doCopy = import('https://cdn.jsdelivr.net/npm/unicodeit@0.7.5/+esm').then(function(mod) {
        return navigator.clipboard.writeText(mod.replace(tex));
      });
    } else if (fmt === 'png' || fmt === 'svg') {
      var url = 'https://latex.codecogs.com/' + fmt + '.latex?' + encodeURIComponent((fmt === 'png' ? '\\dpi{3000}' : '') + tex);
      doCopy = fetch(url).then(window.SFApi.checkOk).then(function(r) { return r.blob(); }).then(function(blob) {
        var item = {};
        item['image/' + fmt] = blob;
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
