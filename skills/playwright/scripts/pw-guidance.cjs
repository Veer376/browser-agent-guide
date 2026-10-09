// Register Chrome tab identities from the trusted extension bridge, not the DOM.
const fs = require('node:fs');
const path = require('node:path');
const {randomUUID} = require('node:crypto');

function instrument(source, recorder) {
  const config = JSON.parse(fs.readFileSync(path.join(process.env.PW_GUIDANCE_ROOT, 'pairing.json'), 'utf8'));
  const instance = randomUUID();
  const tabs = new Map();
  const owner = process.env.PW_GUIDANCE_OWNER || null;
  const session = process.env.PW_SESSION_LABEL;
  async function send(endpoint, data) {
    try {
      const response = await fetch(config.url + endpoint, {method:'POST',
        headers:{'Content-Type':'application/json', Authorization:'Bearer ' + (config.bridgeToken || config.token)},
        body:JSON.stringify(data), signal:AbortSignal.timeout(1000)});
      if (!response.ok) throw new Error('registration failed');
    } catch {
      recorder?.emit('guidance_registration_unavailable');
    }
  }
  globalThis.__pwGuidance = {
    async register(tab, target) {
      tabs.set(tab, target);
      await send('/binding', {tab, target, session, owner, instance, pid:process.pid});
    },
    async activate(context) {
      await Promise.all([...tabs].map(([tab,target]) => this.register(tab,target)));
      context.on('close', () => {for (const tab of tabs.keys()) void this.remove(tab);});
    },
    async remove(tab) {
      tabs.delete(tab);
      await send('/unbind', {tab, instance});
    }
  };
  const replace = (anchor, replacement) => {
    if (source.split(anchor).length !== 2)
      throw new Error('pw guidance: unsupported Playwright CLI build; reconnect with the pinned CLI.');
    source = source.replace(anchor, replacement);
  };
  replace('this._tabSessions.set(tabId, tabSession);', 'this._tabSessions.set(tabId, tabSession);\n        await globalThis.__pwGuidance.register(tabId, targetInfo?.targetId || "");');
  replace('onTabRemoved(tabId) {', 'onTabRemoved(tabId) {\n        void globalThis.__pwGuidance.remove(tabId);');
  const anchor = 'async function startCliDaemonServer(sessionName, browserContext, browserInfo2, contextConfig, clientInfo, mcpClientInfo, options) {';
  replace(anchor, anchor + '\n  await globalThis.__pwGuidance.activate(browserContext);');
  return source;
}

module.exports = {instrument};
