# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

The CADSEMI company website: three hand-written files (`index.html`, `styles.css`, `script.js`), no build step, no dependencies, no tests. One of several unrelated projects in the `gitwork` repo.

## Viewing a change

The browser tools reject `file://` URLs, so serve it:

```
python3 -m http.server 8765   # run from cadsemi/
```

From WSL, hand the URL to the Windows browser with `explorer.exe 'http://localhost:8765/'` — it exits 1 even on success, so ignore the status. If no window appears, Windows→WSL localhost forwarding is down; serve the WSL IP instead (`ip -4 addr show eth0`). Suggest the user run it themselves as `! explorer.exe http://localhost:8765/` when the launch will not reach Windows.

**Chrome caches `styles.css` hard.** A cache-busting query on `index.html` does *not* bust the stylesheet — the page will render new markup with old CSS and look broken in ways that aren't real. Force it from the page:

```js
document.querySelector('link[href*="styles.css"]').href = 'styles.css?v=' + Date.now();
```

Prefer measuring over eyeballing: `getComputedStyle`, `getBoundingClientRect().height`, and computing line counts as `height / lineHeight` catch alignment breaks a screenshot hides.

## Service card invariants

The four service cards must stay interchangeable, because their alignment is the whole visual argument:

- Description is **4 lines** at the 564px card width (~230–280 characters).
- **Exactly one** `.meta-row`, and its value must fit on one line. Wrapped values are what make a row of cards look ragged.
- All four cards measure the **same height** (401px at desktop). Verify after any copy edit.

Height needs the browser, but the structural half is checkable without one — run this after any card edit and expect `rows=1` on all four, descriptions inside the character band, and no dangling anchors:

```bash
python3 - <<'PY'
import re
h = open('index.html', encoding='utf-8').read()
for cid, b in re.findall(r'<article class="service-card" id="([^"]+)">(.*?)</article>', h, re.S):
    desc = re.search(r'service-desc">(.*?)</p>', b, re.S).group(1)
    print(f"{cid:18} rows={len(re.findall(r'<dt>', b))} desc={len(desc)}ch")
dead = set(re.findall(r'href="#([^"]+)"', h)) - set(re.findall(r'id="([^"]+)"', h))
print("dangling anchors:", dead or "none")
PY
```

The Contact section is a two-card grid (`.contact-layout`, 5fr/7fr): a Direct Email card and the inquiry form. The Direct Email card is currently commented out until the support mailbox exists — see *Pending: support mailbox* below. While the form is alone, `.contact-card:only-child` caps it at 564px — one service-card column, `(1152 - 24) / 2` — so it lines up with the cards above; restoring the email card brings the split back with no CSS change.

The form posts via AJAX to FormSubmit using the hashed endpoint, never the plain address, so no personal mailbox appears in the source. FormSubmit activates per origin: a new domain sends one confirmation mail to the owner before submissions are delivered.

## Design system

Colors come from the `:root` tokens in `styles.css`; never hardcode a hex. Body text holds **4.5:1** contrast — the tokens are annotated with their measured ratios, so keep the annotations honest when adding one.

Two spots in `index.html` mirror `--bg` as a literal and can't use the token — the `<meta name="theme-color">` pair (one per `prefers-color-scheme`) and the inline SVG favicon's `fill` plus its embedded dark-scheme `<style>`. Change `--bg` in either scheme and the matching literals have to move with it.

Cards are near-white on the warm canvas, so what separates them is `--surface-border`, not their fill. Keep that token dark enough to read against `--bg-alt` (it sits at 1.20:1); lighten it and the four service cards lose their edges against the services band.

The footer is inverted in light mode, and neither `--text-muted` nor `--accent` survives there (the copper only reaches 3.36:1 on `--text`); it has its own `--footer-bg`, `--footer-text`, `--footer-muted` and `--footer-accent`. Anything placed in the footer must use those — inheriting `color: var(--text)` or `var(--bg)` breaks in one of the two schemes.

### Dark mode

The site follows the OS/browser setting through `@media (prefers-color-scheme: dark)` at the end of the token section — no toggle, no JavaScript. It only redefines tokens, which is why no component may hardcode a colour. The dark set is annotated with measured ratios like the light one; the copper is lifted to `#d68b61` there because `#a0522d` drops to 3.2:1 on the dark canvas. The footer can't invert in dark mode, so it sits one shade below `--bg` with a `--footer-edge` hairline on top. Check both schemes after any colour change (DevTools → Rendering → Emulate CSS `prefers-color-scheme`).

Headings and UI are the display sans (Poppins), body copy is the serif (Lora). The wordmark is `CADSEMI`, caps with positive tracking; the `<title>` keeps title case (`Home \ Cadsemi`).

## Pending: support mailbox

`support@cadsemi.com` is not set up yet, so every place that shows it is hidden, not deleted. **Whenever the user works on this site, remind them that these are still hidden** until they say the mailbox works. Every spot carries the marker `EMAIL-PENDING`:

```
grep -n EMAIL-PENDING index.html script.js   # expect 3 hits while pending
```

When the mailbox is ready, restore all three together:

1. `index.html` — Direct Email card in Contact: delete its `BEGIN-HIDE` / `END-HIDE` lines.
2. `index.html` — footer "Get in touch" column: delete its `BEGIN-HIDE` / `END-HIDE` lines.
3. `script.js` — form failure message: uncomment the `support@cadsemi.com` line and delete the temporary one.

Then delete the `EMAIL-PENDING` note comments, bump the `?v=` on `styles.css` / `script.js`, send a real mail to `support@cadsemi.com` to confirm it arrives, and remove this section. `hr@cadsemi.com` (footer Careers link) was left visible — confirm with the user whether that mailbox works too.

## Editorial rules

- **One destination per link.** The header lost its Contact link because the Contact us button already went to `#contact`; the footer lost `hr@cadsemi.com` because Careers already linked there. Check for an existing route before adding one.
- **No résumé content.** Track record, Capabilities and year-count stats were removed on purpose — this is a services page, not a CV.
- Service copy is derived from real customer/job specs the user supplies. Don't invent capabilities, tools or nodes.
- The header is flat at every width — there is no menu to open. If you add anything to it, check that logo + nav + CTA still fits a 375px viewport (it currently needs ~355px).

Renaming a service touches five places: the card `id`, the card `<h3>`, the footer service list `href` + text, the hero subheading, and the `<meta name="description">`.

## Committing

Whether a commit is already pushed depends on the clone: some carry a `.git/hooks/post-commit` that pushes to `origin/<branch>` automatically, others don't. Hooks aren't cloned, so this differs per machine — check the result rather than assuming either way, or work lands locally while looking done:

```
git log origin/main..HEAD --oneline   # empty means the remote has it
```

`gitwork` holds several unrelated projects, so stage `cadsemi/` explicitly instead of `git add -A`.
