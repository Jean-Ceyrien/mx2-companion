const routes = {
  companion: {
    number: '293', foot: 'Mapping actions with Companion', heading: 'Full MX2 integration.',
    copy: 'Companion translates the MX2’s controls for djay, manages deck and pad modes, and provides native RGB feedback. Choose Native or MIDI in the app, then use the matching mode on the controller.',
    points: ['Virtual device: MX2 for djay', 'Mapping: Native RGB or Visual Complete', 'SHIFT layers, four pad banks and guided setup'],
    download: 'downloads/MX2-Companion-0.5.0-macOS-arm64.dmg', label: 'Download the Mac app'
  },
  classic: {
    number: '293', foot: 'Actions in the original MIDI setup', heading: 'The pre-app MIDI setup.',
    copy: 'Use the original Visual Complete mapping with the Terminal MIDI bridge. It creates the MX2 for djay virtual device and handles deck modes, SHIFT, pad banks and feedback.',
    points: ['Launcher: DEMARRER-MX2.command', 'Virtual device: MX2 for djay', 'Mapping: Traktor MX2 - Visual Complete', 'Keep the Terminal window open while mixing'],
    download: 'downloads/MX2-Classic-MIDI-0.5.0.zip', label: 'Download Classic MIDI'
  }
};

function selectRoute(name) {
  const route = routes[name];
  if (!route) return;
  document.querySelectorAll('[data-route]').forEach(button => {
    const selected = button.dataset.route === name;
    button.classList.toggle('selected', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
  document.getElementById('route-number').textContent = route.number;
  document.getElementById('route-foot').textContent = route.foot;
  document.getElementById('route-heading').textContent = route.heading;
  document.getElementById('route-copy').textContent = route.copy;
  const points = document.getElementById('route-points');
  points.replaceChildren(...route.points.map(point => {
    const li = document.createElement('li');
    li.textContent = point;
    return li;
  }));
  const download = document.getElementById('route-download');
  download.setAttribute('href', route.download);
  download.textContent = route.label + ' ↗';
}

document.querySelectorAll('[data-route]').forEach(button => button.addEventListener('click', () => selectRoute(button.dataset.route)));

if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const blocks = document.querySelectorAll('.section-intro, .route-picker, .route-content, .product-shot, .install-card, .question-list details, .closing, .footer-mark, .footer-links');
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.classList.add('revealed');
        observer.unobserve(entry.target);
      }
    }
  }, {threshold: 0.12});
  blocks.forEach(block => {
    block.classList.add('reveal-pending');
    observer.observe(block);
  });
}
