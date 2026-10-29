/* Shared header, map consent and visitor-driven maps are initialized in shared.js. */
(function () {
  'use strict';
  var section = document.querySelector('.home-testimonials');
  var carousel = section && section.querySelector('.home-testimonials__viewport');
  var stopButton = section && section.querySelector('.home-testimonials__stop');
  var status = section && section.querySelector('.home-testimonials__status');
  var slides = carousel ? Array.prototype.slice.call(carousel.querySelectorAll('.home-testimonial')) : [];
  if (!carousel || !stopButton || slides.length < 2) return;

  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  var userPaused = false;
  var focusPaused = false;
  var hoverPaused = false;
  var timer = null;
  var slideIndex = 0;
  var delay = 10000;

  function syncStopControl() {
    var stopped = userPaused || reducedMotion.matches;
    var label = reducedMotion.matches
      ? 'La rotación automática está desactivada por preferencia de movimiento reducido'
      : (userPaused ? 'La rotación automática de reseñas está detenida' : 'Detener la rotación automática de reseñas');
    stopButton.setAttribute('aria-label', label);
    stopButton.setAttribute('title', label);
    stopButton.setAttribute('aria-disabled', stopped ? 'true' : 'false');
  }

  function isVisible() {
    var bounds = section.getBoundingClientRect();
    return bounds.bottom > 0 && bounds.top < window.innerHeight;
  }

  function visibleSlides() {
    if (window.innerWidth >= 1024) return 3;
    if (window.innerWidth >= 768) return 2;
    return 1;
  }

  function slideOffset(slide) {
    return slide.getBoundingClientRect().left - carousel.getBoundingClientRect().left + carousel.scrollLeft;
  }

  function nearestSlideIndex() {
    var nearest = 0;
    var distance = Infinity;
    slides.forEach(function (slide, index) {
      var candidateDistance = Math.abs(slideOffset(slide) - carousel.scrollLeft);
      if (candidateDistance < distance) {
        nearest = index;
        distance = candidateDistance;
      }
    });
    return nearest;
  }

  function stopForVisitor() {
    if (userPaused) return;
    userPaused = true;
    stopTimer();
    syncStopControl();
    if (status) status.textContent = 'La rotación automática de reseñas se detuvo y no se reanudará durante esta visita.';
  }

  function pauseForKeyboardScroll(event) {
    if (['ArrowLeft', 'ArrowRight', 'Home', 'End', 'PageUp', 'PageDown', ' ', 'Spacebar'].indexOf(event.key) !== -1) {
      stopForVisitor();
    }
  }

  function advance() {
    if (userPaused || focusPaused || hoverPaused || document.hidden || reducedMotion.matches || !isVisible()) return;

    slideIndex = nearestSlideIndex();
    var lastStart = Math.max(0, slides.length - visibleSlides());
    slideIndex = slideIndex >= lastStart ? 0 : slideIndex + 1;
    carousel.scrollTo({
      left: slideOffset(slides[slideIndex]),
      behavior: 'smooth'
    });
  }

  function stopTimer() {
    if (timer !== null) {
      window.clearInterval(timer);
      timer = null;
    }
  }

  function startTimer() {
    stopTimer();
    if (!userPaused && !reducedMotion.matches) timer = window.setInterval(advance, delay);
  }

  stopButton.addEventListener('click', function () {
    if (userPaused || reducedMotion.matches) return;
    stopForVisitor();
  });

  carousel.addEventListener('pointerdown', stopForVisitor);
  carousel.addEventListener('touchstart', stopForVisitor, { passive: true });
  carousel.addEventListener('wheel', stopForVisitor, { passive: true });
  carousel.addEventListener('keydown', pauseForKeyboardScroll);
  carousel.addEventListener('pointerenter', function () {
    hoverPaused = true;
  });
  carousel.addEventListener('pointerleave', function () {
    hoverPaused = false;
  });
  section.addEventListener('focusin', function () {
    focusPaused = true;
  });
  section.addEventListener('focusout', function () {
    window.setTimeout(function () {
      focusPaused = section.contains(document.activeElement);
    }, 0);
  });

  function applyMotionPreference() {
    if (reducedMotion.matches) {
      stopTimer();
      syncStopControl();
      return;
    }
    syncStopControl();
    if (userPaused) stopTimer();
    else startTimer();
  }

  if (typeof reducedMotion.addEventListener === 'function') {
    reducedMotion.addEventListener('change', applyMotionPreference);
  } else if (typeof reducedMotion.addListener === 'function') {
    reducedMotion.addListener(applyMotionPreference);
  }
  applyMotionPreference();
}());
