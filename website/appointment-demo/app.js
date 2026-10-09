(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const initial = {visit: 'Annual wellness', date: '2026-10-12', time: '10:30 AM'};
  const selection = {...initial};
  const form = $('#booking-form');
  const menu = $('#menu-button');
  const navigation = $('#site-nav');

  const formatDate = (date, style = 'short') => {
    // Noon avoids date shifts across time zones.
    const options = style === 'long'
      ? {weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'}
      : {weekday: 'short', day: 'numeric', month: 'short'};
    return new Intl.DateTimeFormat('en-US', options).format(new Date(date + 'T12:00:00'));
  };

  const select = (kind, value) => {
    selection[kind] = value;
    $$('[data-' + kind + ']').forEach(button => {
      const isSelected = button.dataset[kind] === value;
      button.classList.toggle('is-selected', isSelected);
      button.setAttribute('aria-pressed', String(isSelected));
    });
    $('#summary-line').textContent = formatDate(selection.date) + ' · ' + selection.time;
    $('#form-error').textContent = '';
  };

  for (const kind of ['visit', 'date', 'time']) {
    $$('[data-' + kind + ']').forEach(button => {
      button.addEventListener('click', () => select(kind, button.dataset[kind]));
    });
  }

  const showStage = stage => {
    $('#booking-step').hidden = stage !== 'booking';
    $('#review-step').hidden = stage !== 'review';
    $('#confirmed-step').hidden = stage !== 'confirmed';
    $('#card-counter').textContent = stage === 'booking' ? '01 / 02' : stage === 'review' ? '02 / 02' : 'COMPLETE';
    $('#progress-bar').style.width = stage === 'booking' ? '50%' : '100%';
    if (stage !== 'booking')
      $('.booking-card').scrollIntoView({behavior: 'smooth', block: 'start'});
  };

  const reportInvalid = field => {
    const message = field.id === 'patient-name'
      ? 'Please enter your name (at least 2 characters).'
      : 'Please enter a valid email address to continue.';
    $('#form-error').textContent = message;
    field.setAttribute('aria-invalid', 'true');
    field.focus();
  };

  form.addEventListener('submit', event => {
    event.preventDefault();
    $('#form-error').textContent = '';
    const fields = [$('#patient-name'), $('#patient-email')];
    fields.forEach(field => field.removeAttribute('aria-invalid'));
    const invalidField = fields.find(field => !field.checkValidity());
    if (invalidField) return reportInvalid(invalidField);
    $('#review-visit').textContent = selection.visit;
    $('#review-date').textContent = formatDate(selection.date, 'long') + ' · ' + selection.time;
    $('#review-person').textContent = $('#patient-name').value.trim();
    $('#review-email').textContent = $('#patient-email').value.trim();
    showStage('review');
  });

  for (const field of [$('#patient-name'), $('#patient-email')]) {
    field.addEventListener('input', () => {
      field.removeAttribute('aria-invalid');
      $('#form-error').textContent = '';
    });
  }

  $('#edit-booking').addEventListener('click', () => {
    showStage('booking');
    $('#date-group').scrollIntoView({behavior: 'smooth', block: 'center'});
  });

  $('#confirm-booking').addEventListener('click', () => {
    $('#confirmed-date').textContent = formatDate(selection.date, 'long') + ' · ' + selection.time;
    $('#confirmed-person').textContent = $('#patient-name').value.trim() + ' · ' + selection.visit + ' with Dr. Maya Ellis';
    showStage('confirmed');
  });

  $('#start-over').addEventListener('click', () => {
    form.reset();
    for (const [kind, value] of Object.entries(initial)) select(kind, value);
    $('#form-error').textContent = '';
    for (const field of [$('#patient-name'), $('#patient-email')]) field.removeAttribute('aria-invalid');
    showStage('booking');
  });

  menu.addEventListener('click', () => {
    const expanded = menu.getAttribute('aria-expanded') === 'true';
    menu.setAttribute('aria-expanded', String(!expanded));
    menu.setAttribute('aria-label', expanded ? 'Open navigation' : 'Close navigation');
    navigation.classList.toggle('is-open', !expanded);
  });
  navigation.querySelectorAll('a').forEach(anchor => {
    anchor.addEventListener('click', () => {
      navigation.classList.remove('is-open');
      menu.setAttribute('aria-expanded', 'false');
      menu.setAttribute('aria-label', 'Open navigation');
    });
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && navigation.classList.contains('is-open')) {
      navigation.classList.remove('is-open');
      menu.setAttribute('aria-expanded', 'false');
      menu.setAttribute('aria-label', 'Open navigation');
      menu.focus();
    }
  });

  // No remote booking endpoint, persistence, analytics or personal-information submission.
})();
