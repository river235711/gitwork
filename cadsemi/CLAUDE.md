# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

The CADSEMI company website: three hand-written files (`index.html`, `styles.css`, `script.js`), no build step, no dependencies, no tests. One of several unrelated projects in the `gitwork` repo.

## Viewing a change

The browser tools reject `file://` URLs, so serve it:

```
python3 -m http.server 8765   # run from cadsemi/
```

**Chrome caches `styles.css` hard.** A cache-busting query on `index.html` does *not* bust the stylesheet — the page will render new markup with old CSS and look broken in ways that aren't real. Force it from the page:

```js
document.querySelector('link[href*="styles.css"]').href = 'styles.css?v=' + Date.now();
```

Prefer measuring over eyeballing: `getComputedStyle`, `getBoundingClientRect().height`, and computing line counts as `height / lineHeight` catch alignment breaks a screenshot hides.

## Service card invariants

The four service cards must stay interchangeable, because their alignment is the whole visual argument:

- Description is **4 lines** at the 564px card width (~230–280 characters).
- **Exactly one** `.meta-row`, and its value must fit on one line. Wrapped values are what make a row of cards look ragged.
- All four cards measure the **same height** (399px at desktop). Verify after any copy edit.

The Contact section's single card is capped at 564px — one service-card column, `(1152 - 24) / 2` — so it lines up with the cards above.

## Design system

Colors come from the `:root` tokens in `styles.css`; never hardcode a hex. Body text holds **4.5:1** contrast — the tokens are annotated with their measured ratios, so keep the annotations honest when adding one.

The footer is inverted, and neither `--text-muted` nor `--accent` survives there (the copper only reaches 3.36:1 on `--text`); it has its own `--footer-muted` and `--footer-accent`. Anything placed in the footer that inherits `color: var(--text)` — `.logo-text` did — needs an explicit override or it goes dark on dark.

Headings and UI are the display sans (Poppins), body copy is the serif (Lora). The wordmark is `CADSEMI`, caps with positive tracking; the `<title>` keeps title case (`Home \ Cadsemi`).

## Editorial rules

- **One destination per link.** The header lost its Contact link because the Contact us button already went to `#contact`; the footer lost `hr@cadsemi.com` because Careers already linked there. Check for an existing route before adding one.
- **No résumé content.** Track record, Capabilities and year-count stats were removed on purpose — this is a services page, not a CV.
- Service copy is derived from real customer/job specs the user supplies. Don't invent capabilities, tools or nodes.
- The header is flat at every width — there is no menu to open. If you add anything to it, check that logo + nav + CTA still fits a 375px viewport (it currently needs ~355px).

Renaming a service touches five places: the card `id`, the card `<h3>`, the footer service list `href` + text, the hero subheading, and the `<meta name="description">`.

## Committing

`.git/hooks/post-commit` pushes to `origin/<branch>` automatically. Commit and you are done — no manual `git push`.
