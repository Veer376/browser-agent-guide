(() => {
  const $ = (id) => document.getElementById(id);

  // Palette choice affects presentation only; it never changes browser or agent state.
  const themeButton = $('theme-toggle');
  const setTheme = (dark) => {
    document.body.classList.toggle('dark', dark);
    themeButton.setAttribute('aria-label', dark ? 'Switch to light palette' : 'Switch to dark palette');
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = dark ? '#172222' : '#f3f2ee';
  };
  setTheme(false);
  themeButton.addEventListener('click', () => setTheme(!document.body.classList.contains('dark')));

  const menuButton = $('menu-toggle');
  const nav = $('nav-links');
  const setMenu = (open) => {
    nav.classList.toggle('open', open);
    menuButton.setAttribute('aria-expanded', String(open));
    menuButton.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
  };
  menuButton.addEventListener('click', () => setMenu(menuButton.getAttribute('aria-expanded') !== 'true'));
  nav.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => setMenu(false)));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && menuButton.getAttribute('aria-expanded') === 'true') {
      setMenu(false);
      menuButton.focus();
    }
  });
  window.matchMedia('(min-width: 761px)').addEventListener('change', (event) => {
    if (event.matches) setMenu(false);
  });

  // A truthful local-only illustration, not a connection to an actual agent.
  const queue = $('demo-queue');
  const deliver = $('demo-deliver');
  const reset = $('demo-reset');
  const note = $('demo-note');
  const noteStatus = $('demo-note-status');
  const status = $('demo-status');
  const states = ['draft', 'queued', 'delivered'];
  const render = (state) => {
    note.classList.toggle('queued', state === 'queued');
    note.classList.toggle('delivered', state === 'delivered');
    for (const name of states) $('step-' + name).classList.toggle('active', state === name);
    queue.disabled = state !== 'draft';
    deliver.disabled = state !== 'queued';
    if (state === 'draft') {
      noteStatus.textContent = 'DRAFT / NOT QUEUED';
      status.textContent = 'Draft note. Queue the guidance to explore the sequence.';
    } else if (state === 'queued') {
      noteStatus.textContent = 'QUEUED / NEXT SUPPORTED COMMAND';
      status.textContent = 'Illustrative queue: the agent has not read the note yet.';
    } else {
      noteStatus.textContent = 'DELIVERED / COMPLIANCE UNKNOWN';
      status.textContent = 'Illustrative delivery at a command boundary. This does not prove the agent followed the note.';
    }
  };
  queue.addEventListener('click', () => render('queued'));
  deliver.addEventListener('click', () => render('delivered'));
  reset.addEventListener('click', () => render('draft'));

  const copyButton = $('copy-command');
  const copyFeedback = $('copy-feedback');
  const command = $('install-command').textContent.trim();
  copyButton.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(command);
      copyFeedback.textContent = 'INSTALL COMMAND COPIED · MACOS SKILL AVAILABLE';
      copyButton.querySelector('span').textContent = 'Copied';
      copyButton.querySelector('use').setAttribute('href', '#check');
    } catch {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents($('install-command'));
      selection.removeAllRanges();
      selection.addRange(range);
      copyFeedback.textContent = 'COMMAND SELECTED · COPY WITH ⌘C / CTRL+C';
    }
  });
})();
