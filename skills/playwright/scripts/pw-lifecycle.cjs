// Metadata only: never persist raw protocol parameters, URLs, or error strings.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const reasons = new Set(['target_closed', 'canceled_by_user', 'replaced_with_devtools',
  'Server stopped', 'Playwright client disconnected', 'Extension not connected',
  'Another CDP client already connected', 'All controlled tabs detached']);
const safeReason = value => {
  const text = Buffer.isBuffer(value) ? value.toString() : value;
  return reasons.has(text) ? text : text === '' ? 'empty' : 'unspecified';
};

function createRecorder(directory, session, launchCall) {
  const id = `${process.pid}-${crypto.randomUUID()}`;
  const record = {version: 1, session, pid: process.pid, launch_call_id: launchCall,
    started_at: new Date().toISOString(), events: []};
  let ready = false;
  const emit = (event, fields = {}) => {
    try {
      if (!ready) {
        fs.mkdirSync(directory, {recursive: true, mode: 0o700});
        ready = true;
      }
      record.events.push({at: new Date().toISOString(), event, ...fields});
      record.events = record.events.slice(-200);
      const target = path.join(directory, id + '.json');
      const temp = target + '.tmp';
      fs.writeFileSync(temp, JSON.stringify(record), {mode: 0o600});
      fs.renameSync(temp, target);
      // Independent files per daemon prevent concurrent sessions overwriting events.
      const files = fs.readdirSync(directory).filter(name => name.endsWith('.json'))
        .map(name => ({name, time: fs.statSync(path.join(directory, name)).mtimeMs}))
        .sort((a, b) => a.time - b.time);
      for (const file of files.slice(0, -20))
        fs.unlinkSync(path.join(directory, file.name));
    } catch { /* Logging must never change a browser action. */ }
  };
  const watched = new WeakSet();
  const watchPage = page => {
    if (watched.has(page)) return;
    watched.add(page);
    page.on('close', () => emit('page_closed'));
    page.on('crash', () => emit('page_crashed'));
  };
  return {
    emit,
    extension(method, params) {
      if (!Array.isArray(params)) return;
      if (method === 'chrome.debugger.onDetach') {
        const tab = params[0]?.tabId;
        emit('debugger_detached', {...(Number.isInteger(tab) ? {tab_id: tab} : {}), reason: safeReason(params[1])});
      } else if (method === 'chrome.tabs.onRemoved') {
        emit('tab_removed', {...(Number.isInteger(params[0]) ? {tab_id: params[0]} : {}), window_closing: params[1]?.isWindowClosing === true});
      } else if (method === 'extension.initialized') {
        emit('extension_initialized');
      } else if (method === 'chrome.tabs.onCreated' && Number.isInteger(params[0]?.id)) {
        emit('tab_announced', {tab_id: params[0].id});
      }
    },
    debuggerEvent(method, params) {
      if (!['Page.frameRequestedNavigation', 'Page.frameStartedNavigating'].includes(method)) return;
      const scheme = typeof params?.url === 'string' ? /^([a-z][a-z0-9+.-]*):/i.exec(params.url)?.[1]?.toLowerCase() : null;
      if (scheme && !['http', 'https', 'about', 'data', 'blob'].includes(scheme))
        emit('restricted_scheme_navigation', {method});
    },
    command(method) {
      if (['Target.closeTarget', 'Target.createTarget', 'Page.navigate'].includes(method))
        emit('cdp_command', {method});
    },
    socketClosed(code, reason) {
      emit('extension_socket_closed', {...(Number.isInteger(code) ? {code} : {}), reason: safeReason(reason)});
    },
    watch(context) {
      try {
        emit('daemon_started');
        context.pages().forEach(watchPage);
        context.on('page', watchPage);
        context.on('close', () => emit('context_closed'));
        context.browser()?.on('disconnected', () => emit('browser_disconnected'));
      } catch { emit('watch_unavailable'); }
    }
  };
}

function instrument(source, recorder) {
  const patches = [
    ['handleExtensionEvent(method, params2) {', 'handleExtensionEvent(method, params2) {\n        globalThis.__pwLifecycle.extension(method, params2);'],
    ['this._model.onDebuggerEvent(source12, cdpMethod, cdpParams);', 'globalThis.__pwLifecycle.debuggerEvent(cdpMethod, cdpParams);\n            this._model.onDebuggerEvent(source12, cdpMethod, cdpParams);'],
    ['async _handleCDPCommand(method, params2, sessionId) {', 'async _handleCDPCommand(method, params2, sessionId) {\n        globalThis.__pwLifecycle.command(method);'],
    ['_onClose(event) {\n        debugLogger2(', '_onClose(event) {\n        globalThis.__pwLifecycle.socketClosed(typeof event === "number" ? event : event?.code, typeof event === "number" ? arguments[1] : event?.reason);\n        debugLogger2('],
    ['async function startCliDaemonServer(sessionName, browserContext, browserInfo2, contextConfig, clientInfo, mcpClientInfo, options) {', 'async function startCliDaemonServer(sessionName, browserContext, browserInfo2, contextConfig, clientInfo, mcpClientInfo, options) {\n  globalThis.__pwLifecycle.watch(browserContext);'],
    ['this._closeExtensionConnection("Playwright client disconnected");', 'globalThis.__pwLifecycle.emit("playwright_socket_closed");\n          this._closeExtensionConnection("Playwright client disconnected");'],
    ['if (method === "stop") {', 'if (method === "stop") {\n          globalThis.__pwLifecycle.emit("daemon_stop_requested");']
  ];
  if (patches.some(([anchor]) => source.split(anchor).length !== 2)) {
    recorder.emit('instrumentation_unavailable');
    return source;
  }
  globalThis.__pwLifecycle = recorder;
  for (const [anchor, replacement] of patches) source = source.replace(anchor, replacement);
  // Recorded only once the browser daemon starts, rather than for every CLI load.
  return source;
}

module.exports = {createRecorder, instrument, safeReason};
