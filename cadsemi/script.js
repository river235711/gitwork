document.addEventListener("DOMContentLoaded", () => {
  const navToggle = document.getElementById("navToggle");
  const mainNav = document.getElementById("mainNav");

  navToggle?.addEventListener("click", () => {
    const isOpen = mainNav.classList.toggle("open");
    navToggle.setAttribute("aria-expanded", String(isOpen));
  });

  mainNav?.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      mainNav.classList.remove("open");
      navToggle?.setAttribute("aria-expanded", "false");
    });
  });

  const yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  // Language switch (CN / EN)
  const langOpts = Array.from(document.querySelectorAll(".lang-opt"));
  langOpts.forEach((btn) => {
    btn.addEventListener("click", () => {
      langOpts.forEach((b) => {
        const active = b === btn;
        b.classList.toggle("is-active", active);
        b.setAttribute("aria-pressed", String(active));
      });
      document.documentElement.lang = btn.dataset.lang === "en" ? "en" : "zh-Hant";
    });
  });

  // Hero carousel
  const carousel = document.getElementById("carousel");
  const slides = carousel ? Array.from(carousel.querySelectorAll(".slide")) : [];
  const dots = Array.from(document.querySelectorAll("#carouselDots .dot"));
  const toggleBtn = document.getElementById("carouselToggle");
  const iconPause = toggleBtn?.querySelector(".icon-pause");
  const iconPlay = toggleBtn?.querySelector(".icon-play");

  let current = 0;
  let playing = true;
  let timer = null;

  function showSlide(index) {
    slides.forEach((slide, i) => slide.classList.toggle("is-active", i === index));
    dots.forEach((dot, i) => dot.classList.toggle("is-active", i === index));
    current = index;
  }

  function next() {
    showSlide((current + 1) % slides.length);
  }

  function startAutoplay() {
    stopAutoplay();
    timer = setInterval(next, 6000);
  }

  function stopAutoplay() {
    if (timer) clearInterval(timer);
    timer = null;
  }

  dots.forEach((dot, i) => {
    dot.addEventListener("click", () => {
      showSlide(i);
      if (playing) startAutoplay();
    });
  });

  toggleBtn?.addEventListener("click", () => {
    playing = !playing;
    if (playing) {
      startAutoplay();
      iconPause.hidden = false;
      iconPlay.hidden = true;
      toggleBtn.setAttribute("aria-label", "暫停輪播");
    } else {
      stopAutoplay();
      iconPause.hidden = true;
      iconPlay.hidden = false;
      toggleBtn.setAttribute("aria-label", "播放輪播");
    }
  });

  if (slides.length > 1) startAutoplay();
});
