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

  // ---- Language switch (简体中文 / English) ----
  const i18n = {
    zh: {
      "nav.services": "服务项目",
      "nav.contact": "联络我们",
      "hero.eyebrow": "半导体设计自动化顾问服务",
      "hero.title": "从 PDK 到全晶片验证<br>您值得信赖的硅智财伙伴",
      "hero.sub": "PDK 开发移植、电路验证、客制化布局与自动化脚本开发，一站式技术顾问服务。",
      "hero.cta": "查看服务项目",
      "hero.ctaContact": "联络我们",
      "hero.stat1Value": "先进与成熟",
      "hero.stat1": "制程节点涵盖",
      "hero.stat2": "核心服务领域",
      "hero.stat3": "核心 EDA 工具",
      "services.title": "服务项目",
      "services.titleEn": "Services",
      "services.sub": "涵盖 IC 设计流程中每一个关键环节，从前段开发到后段验证，提供一站式技术顾问服务。",
      "pdk.title": "PDK 开发与移植",
      "pdk.en": "PDK Development &amp; Porting",
      "pdk.desc": "提供 CDF 建置与 callback 开发、制程移植（Porting）、SKILL 语言开发与 PCELL 客制化，涵盖 TSMC・UMC・SMIC・GF・HLMC 等主流晶圆厂格式，加速 PDK 导入、QA 与跨制程移转。",
      "verification.title": "验证服务",
      "verification.en": "Verification",
      "verification.desc": "提供 DRC、LVS、RC 萃取与 EMIR 分析等全方位验证服务，并建立 PGV library flow，确保设计符合制程规范与电源完整性要求。",
      "verification.tools": "工具：Calibre・PVS・StarRC・QRC・Voltus",
      "layout.title": "设计与布局",
      "layout.en": "Design &amp; Layout",
      "layout.desc": "支援电路设计、客制化布局、Symbol 与 Analog Logic Cell 建置，涵盖业界主流 EDA 平台。",
      "model.title": "模型验证与工具认证",
      "model.en": "Model &amp; Tool Certification",
      "model.desc": "提供制程 SPICE Model 评估与认证、EDA 工具资格认证与效能基准测试，协助团队完成从模型到工具导入的完整验证链。",
      "scripting.title": "自动化脚本开发",
      "scripting.en": "Automation &amp; Scripting",
      "scripting.desc": "建立自动化流程与版本控管机制，提供 EDA 工具评估与基准测试，提升团队开发效率并降低重复性作业成本。",
      "contact.title": "联络我们",
      "contact.titleEn": "Contact",
      "contact.sub": "欢迎透过以下方式与我们联系，讨论您的专案需求或加入我们的团队。",
      "contact.card1": "客户服务与专案洽询",
      "contact.card1En": "Client Inquiries",
      "contact.card2": "人才招募",
      "contact.card2En": "Careers / HR",
      "contact.domain": "官方网域 <strong>cadsemi.com</strong> 筹备中，敬请期待正式上线。",
      "_title": "CADSEMI | 半导体设计自动化顾问服务",
    },
    en: {
      "nav.services": "Services",
      "nav.contact": "Contact",
      "hero.eyebrow": "Semiconductor Design Automation Consulting",
      "hero.title": "From PDK to Full-Chip Signoff<br>Your Trusted Silicon IP Partner",
      "hero.sub": "PDK development &amp; porting, circuit verification, custom layout, and automation scripting — one-stop technical consulting.",
      "hero.cta": "View Services",
      "hero.ctaContact": "Contact Us",
      "hero.stat1Value": "Advanced &amp; Mature",
      "hero.stat1": "Process Node Coverage",
      "hero.stat2": "Core Service Areas",
      "hero.stat3": "Core EDA Tools",
      "services.title": "Services",
      "services.titleEn": "",
      "services.sub": "Covering every critical step of the IC design flow — from front-end development to back-end signoff — as a one-stop consulting partner.",
      "pdk.title": "PDK Development & Porting",
      "pdk.en": "",
      "pdk.desc": "CDF setup and callback development, process porting, SKILL development, and PCELL customization across TSMC, UMC, SMIC, GF, and HLMC foundry formats — accelerating PDK bring-up, QA, and cross-node migration.",
      "verification.title": "Verification",
      "verification.en": "",
      "verification.desc": "Full-spectrum verification including DRC, LVS, RC extraction, and EMIR analysis, plus PGV library flow setup, to ensure design-rule compliance and power integrity.",
      "verification.tools": "Tools: Calibre, PVS, StarRC, QRC, Voltus",
      "layout.title": "Design & Layout",
      "layout.en": "",
      "layout.desc": "Support for circuit design, custom layout, and symbol / analog logic cell creation across mainstream EDA platforms.",
      "model.title": "Model & Tool Certification",
      "model.en": "",
      "model.desc": "SPICE model evaluation and certification, EDA tool qualification, and performance benchmarking — covering the full verification chain from model to tool rollout.",
      "scripting.title": "Automation & Scripting",
      "scripting.en": "",
      "scripting.desc": "Building automation flows and version-control practices, plus EDA tool evaluation and benchmarking, to improve team efficiency and reduce repetitive work.",
      "contact.title": "Contact",
      "contact.titleEn": "",
      "contact.sub": "Reach out through the channels below to discuss your project or join our team.",
      "contact.card1": "Client & Project Inquiries",
      "contact.card1En": "",
      "contact.card2": "Careers",
      "contact.card2En": "",
      "contact.domain": "Our official domain <strong>cadsemi.com</strong> is in preparation — stay tuned for launch.",
      "_title": "CADSEMI | Semiconductor Design Automation Consulting",
    },
  };

  const langNames = { zh: "简体中文", en: "English" };
  const htmlLangAttr = { zh: "zh-Hans", en: "en" };
  const i18nNodes = Array.from(document.querySelectorAll("[data-i18n]"));
  const langSwitch = document.getElementById("langSwitch");
  const langTrigger = document.getElementById("langTrigger");
  const langMenu = document.getElementById("langMenu");
  const langCurrent = document.getElementById("langCurrent");
  const langItems = Array.from(document.querySelectorAll(".lang-item"));

  function applyLang(lang) {
    const dict = i18n[lang] || i18n.zh;
    i18nNodes.forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (key in dict) el.innerHTML = dict[key];
    });
    document.documentElement.lang = htmlLangAttr[lang] || "zh-Hans";
    if (dict._title) document.title = dict._title;
    if (langCurrent) langCurrent.textContent = langNames[lang];
    langItems.forEach((it) => it.classList.toggle("is-active", it.dataset.lang === lang));
    try { localStorage.setItem("cadsemi-lang", lang); } catch (e) {}
  }

  function closeMenu() {
    langSwitch?.classList.remove("open");
    langTrigger?.setAttribute("aria-expanded", "false");
  }

  langTrigger?.addEventListener("click", (e) => {
    e.stopPropagation();
    const open = langSwitch.classList.toggle("open");
    langTrigger.setAttribute("aria-expanded", String(open));
  });

  langItems.forEach((item) => {
    item.addEventListener("click", () => {
      applyLang(item.dataset.lang);
      closeMenu();
    });
  });

  document.addEventListener("click", (e) => {
    if (langSwitch && !langSwitch.contains(e.target)) closeMenu();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeMenu();
  });

  let savedLang = "zh";
  try { savedLang = localStorage.getItem("cadsemi-lang") || "zh"; } catch (e) {}
  applyLang(savedLang);
});
