/* Native keyboard-accessible toggle for the shared static header. */
(function () {
  'use strict';

  function initializeHeader(header) {
    if (header.dataset.menuReady === 'true') return;
    var toggle = header.querySelector('.lc-site-header__toggle');
    var menu = header.querySelector('.lc-site-header__nav');
    if (!toggle || !menu) return;
    header.dataset.menuReady = 'true';

    function closeMenu() {
      header.classList.remove('is-menu-open');
      toggle.setAttribute('aria-expanded', 'false');
    }

    toggle.addEventListener('click', function () {
      var open = header.classList.toggle('is-menu-open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    menu.addEventListener('click', function (event) {
      if (event.target.closest('a')) closeMenu();
    });
    header.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        closeMenu();
        toggle.focus();
      }
    });
  }

  function initialize() {
    document.querySelectorAll('.lc-site-header').forEach(initializeHeader);
    initializeMaps();
  }

  function initializeMaps() {
    var mapUrl = new URL('https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3976.688238066331!2d-74.08646999999999!3d4.649582599999999!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x8e3f9bb707b10b4f:0x907eb94750b808cb!2sD%27%20Castell!5e0!3m2!1ses!2sco!4v1790481462640!5m2!1ses!2sco');
    var mapParameters = mapUrl.searchParams.get('pb') || '';
    if (mapUrl.protocol !== 'https:' || mapUrl.origin !== 'https://www.google.com' || mapUrl.pathname !== '/maps/embed' || !mapParameters.includes('!2d-74.08646999999999!3d4.649582599999999')) return;

    document.querySelectorAll('[data-lc-map-button]').forEach(function (button) {
      if (button.dataset.mapReady === 'true') return;
      var containerId = button.getAttribute('aria-controls');
      var container = containerId && document.getElementById(containerId);
      if (!container || containerId === button.id) return;
      button.dataset.mapReady = 'true';

      button.addEventListener('click', function () {
        if (container.querySelector('iframe')) return;
        var frame = document.createElement('iframe');
        frame.src = mapUrl.href;
        frame.title = button.dataset.mapTitle || 'Mapa de la ubicación de Light Color en Google Maps';
        frame.loading = 'lazy';
        frame.referrerPolicy = 'strict-origin-when-cross-origin';
        frame.setAttribute('allowfullscreen', '');
        container.replaceChildren(frame);
      }, { once: true });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else {
    initialize();
  }
}());
