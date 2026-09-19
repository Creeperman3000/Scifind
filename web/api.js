(function() {
  'use strict';

  function csrfHeaders() {
    return window._csrfToken ? { 'X-CSRF-Token': window._csrfToken } : {};
  }

  function checkOk(r) {
    if (!r.ok) {
      var err = new Error('request failed: ' + r.status);
      err.status = r.status;
      err.response = r;
      throw err;
    }
    return r;
  }

  function getText(url, opts) {
    return fetch(url, opts).then(checkOk).then(function(r) { return r.text(); });
  }

  function mergeOpts(opts, extra) {
    var merged = extra || {};
    if (opts) {
      Object.keys(opts).forEach(function(k) { if (k !== 'headers') merged[k] = opts[k]; });
    }
    return merged;
  }

  function mergeHeaders(base, extra) {
    var headers = base || {};
    Object.keys(extra || {}).forEach(function(k) { headers[k] = extra[k]; });
    return headers;
  }

  function getJSON(url, opts) {
    var headers = mergeHeaders({ 'Accept': 'application/json' }, opts && opts.headers);
    return fetch(url, mergeOpts(opts, { headers: headers })).then(checkOk).then(function(r) { return r.json(); });
  }

  // On !ok throw enriched Error (.data/.html) so callers can surface the server message.
  function postJSON(url, fd, opts) {
    var csrf = csrfHeaders();
    var headers = mergeHeaders(mergeHeaders({ 'Accept': 'application/json' }, csrf), opts && opts.headers);
    if (window._csrfToken && fd && typeof fd.has === 'function' && !fd.has('_csrf_token')) {
      fd.set('_csrf_token', window._csrfToken);
    }
    var merged = mergeOpts(opts, { method: 'POST', body: fd, headers: headers });
    return fetch(url, merged).then(function(r) {
      var ct = (r.headers.get('content-type') || '').toLowerCase();
      var isJSON = ct.indexOf('application/json') !== -1;
      if (r.ok) {
        return isJSON ? r.json() : r.text().then(function(t) {
          try { return JSON.parse(t); } catch (e) { return { html: t }; }
        });
      }
      return r.text().then(function(t) {
        var err, data = null;
        try { data = JSON.parse(t); } catch (e) { data = null; }
        if (data && data.error) {
          err = new Error(data.error);
          err.code = data.code;
        } else {
          var m = /data-error="([^"]*)"/.exec(t);
          err = new Error(m ? m[1] : ('request failed: ' + r.status));
        }
        err.status = r.status;
        err.data = data;
        err.html = t;
        throw err;
      });
    });
  }

  function serverMessage(err, fallback) {
    if (err && err.message) return err.message;
    if (err && err.data && err.data.error) return err.data.error;
    return fallback;
  }

  window.SFApi = {
    checkOk: checkOk,
    getText: getText,
    getJSON: getJSON,
    postJSON: postJSON,
    serverMessage: serverMessage
  };
})();
