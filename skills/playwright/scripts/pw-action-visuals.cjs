// Reuse Playwright's input instrumentation and isolated overlay, without recording
// video or adding a delay to input. Only the adapter's pinned daemon is modified.
const vm = require('node:vm');
const {cursorMarkup} = require('./visual-system/cursor.cjs');
const {CSS} = require('./visual-system/motion.cjs');
const {attachAgent} = require('./visual-system/agent.cjs');
const {normalizeTheme} = require('./visual-system/theme.cjs');

const THEME = normalizeTheme(process.env.PW_AGENT_THEME);

function classifyAction(name) {
  if (/screenshot/.test(name)) return 'screenshot';
  if (/snapshot|_find$|verify_|wait_for/.test(name)) return 'reading';
  if (/evaluate|run_code/.test(name)) return 'inspecting';
  if (/type|press|fill|replace/.test(name)) return 'typing';
  if (/wheel|scroll/.test(name)) return 'scrolling';
  return '';
}

async function broadcast(context, phase, toolName, ok = true, recorder) {
  const kind = classifyAction(toolName);
  // Ignore unrelated commands: the pointer's own move handler keeps the
  // character responsive for click/hover.
  if (!kind) return;
  await Promise.all(context.pages().map(async page => {
    if (typeof page.evaluate !== 'function') return;
    try {
      await page.evaluate(({phase, kind, ok}) => {
        window.dispatchEvent(new CustomEvent('pw-agent-command', {detail: {phase, kind, ok}}));
      }, {phase, kind, ok});
    } catch {
      recorder?.emit('agent_activity_unavailable');
    }
  }));
}

function replaceOnce(source, anchor, replacement) {
  if (source.split(anchor).length !== 2)
    throw new Error('pw action visuals: unsupported Playwright CLI build; reconnect with the pinned CLI.');
  return source.replace(anchor, replacement);
}

async function prepare(context, recorder) {
  const pending = new WeakMap();
  const enable = page => {
    if (!pending.has(page)) {
      pending.set(page, page.screencast.showActions({duration: 700, position: 'top-right', fontSize: 12, cursor: 'pointer'})
        .catch(() => recorder?.emit('action_visuals_unavailable')));
    }
    return pending.get(page);
  };
  context.on('page', enable);
  await Promise.all(context.pages().map(enable));
  // Newly created pages finish setup before the next CLI command uses them.
  return () => Promise.all(context.pages().map(enable));
}

function instrument(source, recorder) {
  const anchor = 'async function startCliDaemonServer(sessionName, browserContext, browserInfo2, contextConfig, clientInfo, mcpClientInfo, options) {';
  globalThis.__pwActionVisuals = {
    prepare: context => prepare(context, recorder),
    broadcast: (context, phase, name, ok) => broadcast(context, phase, name, ok, recorder),
  };
  source = replaceOnce(source, anchor, anchor + '\n  const pwVisualsReady = await globalThis.__pwActionVisuals.prepare(browserContext);');
  source = replaceOnce(source, 'const response2 = await backend.callTool(toolName, toolParams, abortController.signal);',
    `await pwVisualsReady();
          await globalThis.__pwActionVisuals.broadcast(browserContext, 'begin', toolName);
          let response2;
          try {
            response2 = await backend.callTool(toolName, toolParams, abortController.signal);
          } finally {
            await globalThis.__pwActionVisuals.broadcast(browserContext, 'finish', toolName, !!response2 && !response2.isError);
          }`);
  source = replaceOnce(source,
    'await new Promise((f) => injected2.utils.builtins.setTimeout(f, duration));\n          injected2.setScreencastAnnotation(null);',
    '// Keep the cursor at the last action point; the next input moves it.');
  source = replaceOnce(source, 'point,\n          box,\n          actionTitle: actionTitle2,',
    'point,\n          box: undefined,\n          actionTitle: "",');
  let modified = 0;
  source = source.replace(/source\d* = ('(?:\\.|[^'\\])*');/g, (assignment, literal) => {
    if (!literal.includes('setScreencastAnnotation') || !literal.includes('_createCursorSvg')) return assignment;
    let injected = vm.runInNewContext(literal, Object.create(null), {timeout: 1000});
    const style = injected.match(/var highlight_default = ("(?:\\.|[^"\\])*");/);
    if (!style) throw new Error('pw action visuals: missing overlay stylesheet.');
    injected = replaceOnce(injected, style[0], 'var highlight_default = ' + JSON.stringify(JSON.parse(style[1]) + CSS) + ';');
    const start = injected.indexOf('  _createCursorSvg(document) {');
    const end = injected.indexOf('  showActionTitle(', start);
    if (start < 0 || end < 0) throw new Error('pw action visuals: missing cursor renderer.');
    const cursorFactory = `  _createCursorSvg(document) {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 46 48");
    svg.innerHTML = ${JSON.stringify(cursorMarkup())};
    return svg;
  }
`;
    injected = injected.slice(0, start) + cursorFactory + injected.slice(end);
    injected = replaceOnce(injected,
      'this._actionCursorElement.appendChild(this._createCursorSvg(document));',
      `this._actionCursorElement.appendChild(this._createCursorSvg(document));
    this.__pwAgent = (${attachAgent.toString()})(this._actionCursorElement, document, this._injectedScript.window, ${JSON.stringify(THEME)});`);
    injected = replaceOnce(injected, 'this._actionCursorElement.style.visibility = "visible";',
      'this._actionCursorElement.style.visibility = "visible";\n    this.__pwAgent?.pointer(x, y);');
    injected = replaceOnce(injected, 'highlight.showActionPoint(annotation.point.x, annotation.point.y, fadeDuration);', 'highlight.hideActionPoint();');
    modified++;
    return assignment.slice(0, assignment.indexOf('=')) + '= ' + JSON.stringify(injected) + ';';
  });
  if (modified !== 1) throw new Error('pw action visuals: unsupported injected overlay build.');
  return source;
}

module.exports = {CSS, prepare, instrument, classifyAction, broadcast};
