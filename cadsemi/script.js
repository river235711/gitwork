document.addEventListener("DOMContentLoaded", () => {
  const yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  // Pre-select the matching service when clicking "Discuss this service"
  const serviceSelect = document.getElementById("service");
  document.querySelectorAll(".card-cta[data-service]").forEach((link) => {
    link.addEventListener("click", () => {
      if (serviceSelect) {
        serviceSelect.value = link.dataset.service;
        serviceSelect.classList.remove("invalid");
      }
    });
  });

  // Copy email convenience button
  const copyBtn = document.getElementById("copy-email");
  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const email = copyBtn.dataset.email || "";
      try {
        await navigator.clipboard.writeText(email);
        copyBtn.textContent = "Copied";
        setTimeout(() => {
          copyBtn.textContent = "Copy";
        }, 1800);
      } catch {
        copyBtn.textContent = email;
      }
    });
  }

  // Contact form submission via FormSubmit AJAX
  const form = document.getElementById("contact-form");
  const statusEl = document.getElementById("form-status");
  const submitBtn = document.getElementById("submit-btn");

  if (!form || !statusEl || !submitBtn) return;

  const requiredFields = Array.from(form.querySelectorAll("[required]"));
  requiredFields.forEach((el) => {
    el.addEventListener("input", () => el.classList.remove("invalid"));
    el.addEventListener("change", () => el.classList.remove("invalid"));
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    statusEl.className = "form-status";
    statusEl.textContent = "";

    let firstInvalid = null;
    requiredFields.forEach((el) => {
      const valid = el.checkValidity();
      el.classList.toggle("invalid", !valid);
      if (!valid && !firstInvalid) firstInvalid = el;
    });

    if (firstInvalid) {
      firstInvalid.focus();
      statusEl.className = "form-status is-error";
      statusEl.textContent = "Please fill in all required fields with a valid email.";
      return;
    }

    const formData = new FormData(form);
    submitBtn.disabled = true;
    statusEl.textContent = "Sending...";

    try {
      const res = await fetch(form.action, {
        method: "POST",
        headers: { Accept: "application/json" },
        body: formData,
      });
      const data = await res.json();
      if (res.ok && (data.success === "true" || data.success === true)) {
        form.reset();
        statusEl.className = "form-status is-success";
        statusEl.textContent = "Thank you — your inquiry has been sent. We will reply shortly.";
      } else {
        throw new Error(data.message || "Submission failed");
      }
    } catch {
      statusEl.className = "form-status is-error";
      statusEl.textContent = "Could not send right now. Please email support@cadsemi.com directly.";
    } finally {
      submitBtn.disabled = false;
    }
  });
});
