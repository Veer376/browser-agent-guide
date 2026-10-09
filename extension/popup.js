const $ = id => document.getElementById(id);
let config, binding, retry, busy = false;
async function api(path, data) {
  const response = await fetch(config.url + path, {method:data ? 'POST' : 'GET',
    headers:{Authorization:'Bearer ' + config.token, ...(data ? {'Content-Type':'application/json'} : {})},
    ...(data ? {body:JSON.stringify(data)} : {}), signal:AbortSignal.timeout(3000)});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'Connection failed.');
  return value;
}
function status(text = '', error = false) {
  $('status').textContent = text;
  $('status').hidden = !text;
  $('status').classList.toggle('error', error);
}
function sendState() {$('send').disabled = busy || !$('message').value.trim();}
async function checkTab() {
  const [tab] = await chrome.tabs.query({active:true,currentWindow:true});
  if (tab?.id !== binding.tab) throw new Error('Active tab changed. Refresh to reconnect.');
  const group = tab.groupId >= 0 ? await chrome.tabGroups.get(tab.groupId) : null;
  if (group?.title !== 'Playwright · ' + binding.session) throw new Error('Tab session changed. Refresh to reconnect.');
}
async function showQueue() {
  const {messages} = await api('/messages', {tab:binding.tab,instance:binding.instance});
  $('pending').textContent = messages.length;
  $('queue-section').hidden = !messages.length;
  $('queue').replaceChildren();
  for (const message of messages) {
    const row = document.createElement('div'); row.className = 'queue-item';
    const text = document.createElement('p'); text.textContent = message.text; text.title = message.text;
    const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'icon-button remove';
    remove.setAttribute('aria-label','Remove queued message'); remove.title = 'Remove message';
    remove.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="m7 7 10 10M17 7 7 17"/></svg>';
    remove.addEventListener('click', async () => {
      remove.disabled = true;
      try {
        await checkTab();
        const result = await api('/message/remove',{tab:binding.tab,instance:binding.instance,id:message.id});
        status(result.status === 'delivered' ? 'This message was already delivered.' : '');
        await showQueue();
      } catch(e) {status(e.message,true);remove.disabled = false;}
    });
    row.append(text,remove); $('queue').append(row);
  }
}
async function refresh() {
  $('refresh').disabled = true;
  status('Connecting…');
  try {
    const result = await chrome.runtime.sendNativeMessage('com.playwright.guidance', {operation:'connect'});
    if (result?.error) throw new Error(result.error);
    const value = result?.connection;
    if (value?.url !== 'http://127.0.0.1:8799' || !/^[A-Za-z0-9_-]{43}$/.test(value?.token || '')) throw new Error('Run pw guidance enable to connect.');
    config = value;
    await chrome.storage.local.remove('pairing');
    const [tab] = await chrome.tabs.query({active:true,currentWindow:true});
    if (!Number.isInteger(tab?.id)) throw new Error('No active browser tab.');
    const previous = binding;
    binding = (await api('/tab/' + tab.id)).binding;
    if (!binding) throw new Error('No agent connected to this tab. Reconnect its Playwright session.');
    await checkTab();
    $('session').textContent = binding.session;
    $('session').title = binding.session;
    if (previous?.instance !== binding.instance || previous?.tab !== binding.tab) {
      const drafts = (await chrome.storage.local.get('drafts')).drafts || {};
      retry = drafts[binding.instance + ':' + binding.tab] || null;
      $('message').value = retry?.text || '';
    }
    await showQueue();
    $('connected').hidden = false;
    status(); sendState();
  } catch(e) {$('connected').hidden = true;status(e.message,true);}
  finally {$('refresh').disabled = false;}
}
$('form').addEventListener('submit', async event => {
  event.preventDefault();
  const text = $('message').value;
  if (busy || !text.trim()) return;
  busy = true; sendState(); status();
  try {
    await checkTab();
    const key = binding.instance + ':' + binding.tab;
    retry = retry?.text === text ? retry : {id:crypto.randomUUID(),text};
    const drafts = (await chrome.storage.local.get('drafts')).drafts || {};
    drafts[key] = retry;
    await chrome.storage.local.set({drafts});
    const result = await api('/message', {tab:binding.tab,instance:binding.instance,...retry});
    delete drafts[key]; await chrome.storage.local.set({drafts});
    if ($('message').value === text) $('message').value = '';
    retry = null;
    if (result.status === 'delivered') status('Already delivered.');
    if (result.status === 'cancelled') status('This message was removed.');
    await showQueue();
  } catch(e) {status(e.message + ' Your draft is kept.',true);}
  finally {busy = false;sendState();}
});
$('message').addEventListener('input', sendState);
$('message').addEventListener('keydown', event => {
  if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {event.preventDefault();$('form').requestSubmit();}
});
$('refresh').addEventListener('click',refresh);
refresh();
