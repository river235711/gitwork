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
      "nav.node": "制程涵盖",
      "nav.about": "关于我们",
      "nav.contact": "联络我们",
      "hero1.eyebrow": "半导体设计自动化顾问服务",
      "hero1.title": "从 PDK 到全晶片验证<br>您值得信赖的硅智财伙伴",
      "hero1.sub": "PDK 开发移植、电路验证、客制化布局与自动化脚本开发，一站式技术顾问服务。",
      "hero1.cta": "查看服务项目",
      "hero2.title": "横跨 3nm 至 250nm<br>全制程节点实战经验",
      "hero2.sub": "从先进制程到成熟制程，协助客户完成设计转移与跨节点验证。",
      "hero2.cta": "了解制程涵盖",
      "hero3.title": "整合业界标准工具链<br>加速您的设计流程",
      "hero3.sub": "Calibre・Virtuoso・StarRC・Voltus 与自动化脚本开发，提升团队交付效率。",
      "hero3.cta": "立即咨询",
      "explore.title": "探索服务项目",
      "explore.pdk": "PDK 开发与移植",
      "explore.verification": "验证服务",
      "explore.layout": "设计与布局",
      "explore.scripting": "自动化脚本开发",
      "explore.node": "全制程节点涵盖",
      "services.title": "服务项目",
      "services.titleEn": "Services",
      "services.sub": "涵盖 IC 设计流程中每一个关键环节，从前段开发到后段验证，提供一站式技术顾问服务。",
      "pdk.title": "PDK 开发与移植",
      "pdk.en": "PDK Development &amp; Porting",
      "pdk.desc": "提供 CDF 建置、制程移植（Porting）、SKILL 语言开发与 PCELL 客制化，加速 PDK 导入与跨制程移转。",
      "verification.title": "验证服务",
      "verification.en": "Verification",
      "verification.desc": "提供 DRC、LVS、RC 萃取与 EMIR 分析等全方位验证服务，确保设计符合制程规范与电源完整性要求。",
      "verification.tools": "工具：Calibre・PVS・StarRC・QRC・Voltus",
      "layout.title": "设计与布局",
      "layout.en": "Design &amp; Layout",
      "layout.desc": "支援电路设计、客制化布局与版图检查流程整合，涵盖业界主流 EDA 平台。",
      "scripting.title": "自动化脚本开发",
      "scripting.en": "Automation &amp; Scripting",
      "scripting.desc": "建立自动化流程与版本控管机制，提升团队开发效率并降低重复性作业成本。",
      "node.title": "全制程节点涵盖",
      "node.sub": "具备从先进制程到成熟制程的专案经验，协助新旧制程节点间的设计转移与验证。",
      "node.cta": "讨论您的制程需求",
      "node.row1": "Calibre 验证整合",
      "node.row2": "Virtuoso 设计平台",
      "node.row3": "StarRC / QRC 萃取",
      "node.row4": "Voltus 电源完整性",
      "about.title": "关于我们",
      "about.titleEn": "About",
      "about.p1": "CADSEMI 是一家专注于半导体设计自动化（EDA）与客制化 IC 设计服务的技术顾问公司。我们的团队具备横跨先进制程与成熟制程节点的实战经验，服务范围涵盖 PDK 开发、电路验证、版图设计，以及流程自动化，协助客户加速产品开发时程，并确保每一项交付都符合最高的设计品质与制程规范。",
      "about.p2": "我们相信专业的顾问服务来自对工具链与制程细节的深刻理解——这正是 CADSEMI 存在的价值。",
      "about.cardTitle": "核心优势",
      "about.li1": "横跨 3nm 至 250nm 制程节点的实务经验",
      "about.li2": "熟悉业界主流 EDA 工具链与验证流程",
      "about.li3": "具备 SKILL / PCELL 客制化开发能力",
      "about.li4": "提供自动化脚本与流程整合，提升交付效率",
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
      "nav.node": "Process Nodes",
      "nav.about": "About",
      "nav.contact": "Contact",
      "hero1.eyebrow": "Semiconductor Design Automation Consulting",
      "hero1.title": "From PDK to Full-Chip Signoff<br>Your Trusted Silicon IP Partner",
      "hero1.sub": "PDK development &amp; porting, circuit verification, custom layout, and automation scripting — one-stop technical consulting.",
      "hero1.cta": "View Services",
      "hero2.title": "From 3nm to 250nm<br>Proven Across Every Process Node",
      "hero2.sub": "From advanced to mature nodes, we help clients with design migration and cross-node verification.",
      "hero2.cta": "Explore Node Coverage",
      "hero3.title": "Integrated Industry-Standard Toolchains<br>Accelerating Your Design Flow",
      "hero3.sub": "Calibre, Virtuoso, StarRC, Voltus and automation scripting to boost your team's delivery.",
      "hero3.cta": "Get in Touch",
      "explore.title": "Explore Our Services",
      "explore.pdk": "PDK Development & Porting",
      "explore.verification": "Verification",
      "explore.layout": "Design & Layout",
      "explore.scripting": "Automation & Scripting",
      "explore.node": "Full Node Coverage",
      "services.title": "Services",
      "services.titleEn": "",
      "services.sub": "Covering every critical step of the IC design flow — from front-end development to back-end signoff — as a one-stop consulting partner.",
      "pdk.title": "PDK Development & Porting",
      "pdk.en": "",
      "pdk.desc": "We provide CDF setup, process porting, SKILL development, and PCELL customization to accelerate PDK bring-up and cross-node migration.",
      "verification.title": "Verification",
      "verification.en": "",
      "verification.desc": "Full-spectrum verification including DRC, LVS, RC extraction, and EMIR analysis to ensure design-rule compliance and power integrity.",
      "verification.tools": "Tools: Calibre, PVS, StarRC, QRC, Voltus",
      "layout.title": "Design & Layout",
      "layout.en": "",
      "layout.desc": "Support for circuit design, custom layout, and layout-verification flow integration across mainstream EDA platforms.",
      "scripting.title": "Automation & Scripting",
      "scripting.en": "",
      "scripting.desc": "Building automation flows and version-control practices to improve team efficiency and reduce repetitive work.",
      "node.title": "Full Process-Node Coverage",
      "node.sub": "With project experience spanning advanced to mature nodes, we support design migration and verification across old and new process nodes.",
      "node.cta": "Discuss Your Node Requirements",
      "node.row1": "Calibre Verification Integration",
      "node.row2": "Virtuoso Design Platform",
      "node.row3": "StarRC / QRC Extraction",
      "node.row4": "Voltus Power Integrity",
      "about.title": "About",
      "about.titleEn": "",
      "about.p1": "CADSEMI is a technical consultancy focused on electronic design automation (EDA) and custom IC design services. Our team brings hands-on experience across advanced and mature process nodes — spanning PDK development, circuit verification, layout design, and flow automation — helping clients accelerate time-to-market while ensuring every deliverable meets the highest standards of design quality and process compliance.",
      "about.p2": "We believe great consulting comes from a deep understanding of the toolchain and process details — and that is exactly the value CADSEMI delivers.",
      "about.cardTitle": "Core Strengths",
      "about.li1": "Practical experience across 3nm to 250nm process nodes",
      "about.li2": "Fluent in mainstream EDA toolchains and verification flows",
      "about.li3": "Skilled in SKILL / PCELL custom development",
      "about.li4": "Automation scripting and flow integration to boost delivery efficiency",
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
