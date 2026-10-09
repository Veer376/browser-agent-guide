// Opt automation-owned pages out of Local System's extension-owned embeds.
// Chrome rejects debugger attachment while a different extension owns a subframe.
function markAutomationPage() {
  function mark() {
    if (!document.documentElement) return false;
    document.documentElement.setAttribute('data-pw-browser-automation', '1');
    return true;
  }
  if (mark()) return;
  const observer = new MutationObserver(() => {
    if (mark()) observer.disconnect();
  });
  observer.observe(document, {childList: true});
}

function instrument(source, recorder) {
  const anchor = 'async function startCliDaemonServer(sessionName, browserContext, browserInfo2, contextConfig, clientInfo, mcpClientInfo, options) {';
  if (source.split(anchor).length !== 2)
    throw new Error('pw browser compatibility: unsupported Playwright CLI build; reconnect with the pinned CLI.');
  globalThis.__pwBrowserCompatibility = {
    async prepare(context) {
      await context.addInitScript({content: '(' + markAutomationPage.toString() + ')();'});
      recorder?.emit('automation_page_compatibility_enabled');
    }
  };
  return source.replace(anchor, anchor + '\n  await globalThis.__pwBrowserCompatibility.prepare(browserContext);');
}

module.exports = {markAutomationPage, instrument};
