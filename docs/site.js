const routes = {
  companion: {
    number: '293', foot: 'Mapping actions with Companion', heading: 'Full MX2 integration.',
    copy: 'Companion translates the MX2’s controls for djay, manages deck and pad modes, and provides native RGB feedback. Choose Native or MIDI in the app, then use the matching mode on the controller.',
    points: ['Virtual device: MX2 for djay', 'Mapping: Native RGB or Visual Complete', 'SHIFT layers, four pad banks and guided setup'],
    download: 'downloads/MX2-Companion-0.5.0-macOS-arm64.dmg', label: 'Download the Mac app'
  },
  classic: {
    number: '293', foot: 'Actions with the Terminal bridge running', heading: 'The pre-app MIDI setup.',
    copy: 'Use the original Visual Complete mapping with the Terminal MIDI bridge. It creates the MX2 for djay virtual device and handles deck modes, SHIFT, pad banks and feedback.',
    points: ['Launcher: DEMARRER-MX2.command', 'Virtual device: MX2 for djay', 'Mapping: Traktor MX2 - Visual Complete', 'Terminal must stay open; the mapping is not standalone'],
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

const overviewGroups = {
  decks: {
    name: 'Playback & jogs', context: 'On each deck',
    copy: 'PLAY, CUE and the tempo controls stay on their own deck. Use TT for touch-sensitive scratching, or JOG for movement without scratch touch.',
    normal: 'Touch and turn the platter to scratch in TT mode. Release to resume; rotate without scratch touch to move or nudge.',
    shift: 'Turn the jog to seek through the track. Hold the SHIFT button on that side only.',
    link: 'View playback & jog mapping'
  },
  library: {
    name: 'Browse & load', context: 'Beside each FX row',
    copy: 'Find tracks, navigate sources and load onto the deck on that side. The nearby buttons handle queue focus, marking, preview and the library view.',
    normal: 'Turn BROWSE to select a track. Press it to load the track onto this deck.',
    shift: 'Turn BROWSE to select library sources. SHIFT + press loads without instant double.',
    link: 'View library mapping'
  },
  loops: {
    name: 'Loops & beatjump', context: 'Two encoders below each jog',
    copy: 'MOVE is the left encoder; SIZE is the right. Turning an encoder and pressing it are separate actions.',
    normal: 'Turn MOVE to beatjump; press for loop in/out. Turn SIZE to change loop length; press to toggle autoloop.',
    shift: 'Turn MOVE to reposition an active loop. Turn SIZE to change the beatjump distance.',
    link: 'View loop & beatjump mapping'
  },
  effects: {
    name: 'Deck effects', context: 'Top row on each deck',
    copy: 'The first button and knob act across three FX slots. The next three pairs address FX1, FX2 and FX3 individually.',
    normal: 'Buttons toggle slot states; knobs adjust combined Wet/Dry or the individual slot parameter.',
    shift: 'Button 1 toggles overall deck FX. Buttons 2–4 select the next effect in their own slot.',
    link: 'View deck FX mapping'
  },
  pads: {
    name: 'Performance pads', context: 'Eight pads on each deck',
    copy: 'Choose HOTCUES, STEMS, PATTERN or FLUX LOOP independently on each side. Pad numbers run 1–4 across the top, then 5–8 below.',
    normal: 'Jump to cues, mute or solo Neural Mix parts, trigger samples, or hold bounce loops from 1/32 to 4 beats.',
    shift: 'Delete cues, swap stem mute/solo, stop samples, or toggle persistent loops, depending on the selected bank.',
    link: 'View all four pad banks'
  },
  mixer: {
    name: 'Mixer & monitoring', context: 'Centre section',
    copy: 'Each channel has its own gain, EQ, level and headphone cue. The centre FX selector changes the channel effect knobs and ON buttons.',
    normal: 'Mix deck A and B, adjust the main output, and set headphone preview with CUE MIX and CUE VOL.',
    shift: 'Mixer controls keep their normal actions. Set main audio to channels 1–2 and headphones to 3–4 in djay.',
    link: 'View mixer & channel FX mapping'
  }
};

function selectOverview(name) {
  const group = overviewGroups[name];
  if (!group) return;
  document.querySelectorAll('[data-overview]').forEach(button => {
    const selected = button.dataset.overview === name;
    button.classList.toggle('is-selected', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
  for (const field of ['name', 'context', 'copy', 'normal', 'shift']) {
    document.getElementById('overview-' + field).textContent = group[field];
  }
  const link = document.getElementById('overview-read');
  link.href = '#mapping-' + name;
  link.textContent = group.link + ' ↗';
}

document.querySelectorAll('[data-overview]').forEach(button => {
  button.addEventListener('click', () => selectOverview(button.dataset.overview));
});

document.getElementById('overview-read').addEventListener('click', event => {
  const target = document.querySelector(event.currentTarget.getAttribute('href'));
  if (!target) return;
  target.open = true;
  requestAnimationFrame(() => target.querySelector('summary').focus({preventScroll: true}));
});

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
