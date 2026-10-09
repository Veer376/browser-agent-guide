// The pinned Playwright CLI has no client-name option. Supply its session label
// at module load, without modifying the installed package or extension.
const fs = require('node:fs');
const Module = require('node:module');

if (process.env.PW_SESSION_LABEL) {
  const loadJavaScript = Module._extensions['.js'];
  Module._extensions['.js'] = function loadWithSessionLabel(module, filename) {
    if (!filename.replaceAll('\\', '/').endsWith('/playwright-core/lib/coreBundle.js'))
      return loadJavaScript(module, filename);
    let source = fs.readFileSync(filename, 'utf8');
    const anchor = 'clientName: guessClientName()';
    if (source.split(anchor).length !== 2)
      throw new Error('pw session label: unsupported Playwright CLI build; expected one client-name initialization.');
    source = source.replace(anchor, 'clientName: process.env.PW_SESSION_LABEL || guessClientName()');
    let recorder;
    if (process.env.PW_LIFECYCLE_DIR) {
      const lifecycle = require('./pw-lifecycle.cjs');
      recorder = lifecycle.createRecorder(process.env.PW_LIFECYCLE_DIR,
        process.env.PW_SESSION_LABEL, process.env.PW_DIAGNOSTIC_CALL_ID);
      source = lifecycle.instrument(source, recorder);
    }
    if (process.env.PW_BROWSER_COMPATIBILITY === '1')
      source = require('./pw-browser-compatibility.cjs').instrument(source, recorder);
    if (process.env.PW_ACTION_VISUALS === '1')
      source = require('./pw-action-visuals.cjs').instrument(source, recorder);
    if (process.env.PW_GUIDANCE_ROOT)
      source = require('./pw-guidance.cjs').instrument(source, recorder);
    return module._compile(source, filename);
  };
}
