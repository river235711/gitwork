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
});
