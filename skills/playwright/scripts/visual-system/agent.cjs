// This function is serialized into Playwright's injected cursor world.
// It deliberately uses only DOM/JS built-ins (no Node imports) and creates a
// distinct agent pill attached to the existing Playwright cursor element.
function attachAgent(cursor, document, win, theme = 'auto') {
  if (cursor.__pwAgent) return cursor.__pwAgent;
  cursor.dataset.pwTheme = theme;
  cursor.dataset.pwAgentState = 'idle';

  const pill = document.createElement('span');
  pill.className = 'pw-agent-pill';
  pill.setAttribute('aria-hidden', 'true');
  const eyes = document.createElement('span');
  eyes.className = 'pw-agent-eyes';
  for (let i = 0; i < 2; i++) {
    const eye = document.createElement('i');
    eye.className = 'pw-agent-eye';
    eyes.appendChild(eye);
  }
  pill.appendChild(eyes);
  for (let i = 0; i < 2; i++) {
    const z = document.createElement('span');
    z.className = 'pw-agent-z pw-agent-z-' + (i + 1);
    z.textContent = 'z';
    pill.appendChild(z);
  }
  cursor.appendChild(pill);

  let idleTimer = null;
  let finishTimer = null;
  let sleepingTimers = [];
  let active = false;
  let previouslyVisible = false;
  let lastPosition = null;
  let lastMode = '';
  const clear = () => {
    if (idleTimer !== null) win.clearTimeout(idleTimer);
    if (finishTimer !== null) win.clearTimeout(finishTimer);
    idleTimer = finishTimer = null;
    sleepingTimers.forEach(id => win.clearTimeout(id));
    sleepingTimers = [];
  };
  const setState = mode => {
    if (cursor.dataset.pwAgentState === mode && mode.startsWith('scroll-')) {
      cursor.dataset.pwAgentState = 'idle';
      // Restart the one-shot gaze for a consecutive action in the same direction.
      void eyes.offsetWidth;
    }
    cursor.dataset.pwAgentState = mode;
    lastMode = mode;
  };
  const nap = () => {
    if (active || cursor.style.visibility === 'hidden') return;
    setState('heavy');
    const plan = [
      ['jolt', 1350], ['alert', 2050], ['exhausted', 2700],
      ['nod', 3400], ['jolt', 5000], ['exhausted', 5700],
      ['falling', 6150], ['sleep', 8100],
    ];
    for (const [state, delay] of plan)
      sleepingTimers.push(win.setTimeout(() => { if (!active) setState(state); }, delay));
  };
  const scheduleIdle = () => {
    if (idleTimer !== null) win.clearTimeout(idleTimer);
    idleTimer = win.setTimeout(nap, 12000);
  };
  const restore = () => {
    if (active) return;
    setState('idle');
    scheduleIdle();
  };
  const wake = () => {
    if (['sleep', 'heavy', 'falling', 'nod', 'exhausted'].includes(lastMode)) {
      setState('wake');
      return true;
    }
    return false;
  };
  const positionAt = element => {
    if (!element?.getBoundingClientRect) return;
    const r = element.getBoundingClientRect();
    if (!r.width || !r.height) return;
    // Use the field itself as the target, never a fabricated cursor location.
    const x = Math.max(4, Math.min(win.innerWidth - 106, r.left + Math.min(22, r.width / 5)));
    const y = Math.max(4, Math.min(win.innerHeight - 70, r.top + Math.min(15, r.height / 2)));
    cursor.style.transition = 'top 370ms ease, left 370ms ease';
    cursor.style.left = x + 'px';
    cursor.style.top = y + 'px';
    cursor.style.visibility = 'visible';
    lastPosition = {x, y};
  };
  const announce = payload => {
    if (!payload || (payload.phase !== 'begin' && payload.phase !== 'finish')) return;
    clear();
    if (payload.phase === 'begin') {
      active = true;
      previouslyVisible = cursor.style.visibility !== 'hidden';
      if (payload.kind === 'screenshot') {
        // No cursor/pill contamination in screenshots used for automation.
        cursor.style.visibility = 'hidden';
        return;
      }
      const wasSleep = wake();
      const kind = payload.kind || 'idle';
      if (kind) setState(kind);
      if (kind === 'typing' && document.activeElement)
        positionAt(document.activeElement);
      if (wasSleep && kind === 'idle')
        finishTimer = win.setTimeout(() => setState('idle'), 740);
    } else {
      active = false;
      if (payload.kind === 'screenshot')
        cursor.style.visibility = previouslyVisible ? 'visible' : 'hidden';
      if (payload.ok === false) {
        restore();
        return;
      }
      if (payload.kind === 'screenshot' && previouslyVisible)
        setState('capture');
      finishTimer = win.setTimeout(restore, 680);
    }
  };
  const onAction = event => announce(event.detail);
  const isEditable = el => !!el && (el.isContentEditable ||
    el.matches?.('input:not([type="hidden"]),textarea,[contenteditable="true"]'));
  const onFocus = e => {
    if (active && isEditable(e.target)) positionAt(e.target);
  };
  const onTyping = e => {
    if (active && isEditable(e.target)) setState('typing');
  };
  const onWheel = e => {
    if (!active) return;
    const vertical = Math.abs(e.deltaY) >= Math.abs(e.deltaX);
    setState(vertical ? (e.deltaY > 0 ? 'scroll-down' : 'scroll-up') :
      (e.deltaX > 0 ? 'scroll-right' : 'scroll-left'));
  };
  const onScroll = () => {
    if (active && cursor.dataset.pwAgentState === 'scrolling')
      setState('scroll-down');
  };
  win.addEventListener('pw-agent-command', onAction);
  document.addEventListener('focusin', onFocus, true);
  document.addEventListener('input', onTyping, true);
  document.addEventListener('wheel', onWheel, {capture: true, passive: true});
  document.addEventListener('scroll', onScroll, true);
  const controller = {
    announce,
    pointer(x, y) {
      if (!active) {
        clear();
        const dx = lastPosition ? x - lastPosition.x : 0;
        const dy = lastPosition ? y - lastPosition.y : 0;
        if (Math.hypot(dx, dy) > 12) {
          setState(Math.abs(dx) >= Math.abs(dy) ?
            (dx > 0 ? 'glance-right' : 'glance-left') :
            (dy > 0 ? 'glance-down' : 'glance-up'));
          finishTimer = win.setTimeout(restore, 520);
        } else {
          restore();
        }
      }
      lastPosition = {x, y};
    },
    state() {return {mode: lastMode, active, visible: cursor.style.visibility !== 'hidden', position: lastPosition};},
    dispose() {
      clear();
      win.removeEventListener('pw-agent-command', onAction);
      document.removeEventListener('focusin', onFocus, true);
      document.removeEventListener('input', onTyping, true);
      document.removeEventListener('wheel', onWheel, true);
      document.removeEventListener('scroll', onScroll, true);
    },
  };
  cursor.__pwAgent = controller;
  return controller;
}

module.exports = {attachAgent};
