---
name: linkyee-style-designer
description: Use when the user wants to design, customize, or generate a custom visual theme for their linkyee site (a Hexo-like LinkTree-style static site). Triggers on phrases like "design my linkyee page", "make a custom theme", "change the style", "I want my links to look like X", "create a new theme inspired by Y". Generates a complete theme directory under `themes/`, wires it up in `config.yml`, and verifies the build.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# linkyee Style Designer

You help users design custom visual themes for **linkyee** — a Ruby/Liquid static site generator that builds a single-page LinkTree-style site. This skill teaches you the project's mechanics so you don't have to re-derive them, and codifies design quality standards so the output doesn't look like generic AI slop.

## How linkyee builds a site

- Build command: `bundle exec ruby ./scaffold.rb`
- Output: `_output/` (committed to `gh-pages` branch by `deploy.sh` in CI)
- Theme switch: edit the `theme:` field at the top of `config.yml` to a directory name under `themes/`
- The build copies `themes/<theme>/` verbatim into `_output/`, then renders `_output/index.html` through Liquid using `config.yml` as variable scope

## Theme directory contract

A theme dir **must** contain:
- `index.html` — Liquid template (see required hooks below)
- `styles.css` — the look
- `scripts.js` — can be empty, but the file must exist (default theme references it)

A theme dir **should** contain:
- `images/profile.jpeg` — sample avatar (so the theme works before the user replaces it)
- `images/favicons/favicon.ico` — at minimum a single favicon

For new themes, copy these two image assets from `themes/default/images/` rather than generating new ones.

## Required Liquid variables and HTML hooks

Every `index.html` you generate **must** preserve these variables (the user's `config.yml` data flows through them):

| Variable | Purpose |
|---|---|
| `{{ lang }}` | `<html lang>` |
| `{{ title }}` | `<title>`, OG/Twitter meta |
| `{{ name }}` | Display name |
| `{{ tagline }}` | Bio / description |
| `{{ avatar }}` | Avatar image src |
| `{{ links }}` | Loop: `{% for item in links %}{% assign link = item.link %}` then use `link.url`, `link.icon`, `link.text`, `link.title`, `link.alt`, `link.target` |
| `{{ socials }}` | Loop: `{% for item in socials %}{% assign social = item.social %}` then use `social.url`, `social.icon`, `social.title`, `social.alt`, `social.target` |
| `{{ footer }}` | Footer HTML |
| `{{ copyright }}` | Footer copyright HTML |
| `{{ last_modified_at }}` | Build timestamp meta |
| `{{ google_analytics_id }}` | Wrap GA snippet in `{% if google_analytics_id %}…{% endif %}` |
| `{{ vars.<PluginName> }}` | Plugin output (rare; user-controlled) |

**Required HTML structural elements** (preserve from `themes/default/index.html` so SEO/PWA features keep working):
- `<title>`, `<meta name="description">`, all `og:` and `twitter:` meta tags using the variables above
- Favicon `<link>` tags (paths point to `./images/favicons/...`)
- The GA `<script>` block wrapped in the Liquid `{% if %}` guard
- A `<script src="./scripts.js">` reference at the end of `<body>`

**Font Awesome**: link from CDN to keep theme dirs small:
```html
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css" crossorigin="anonymous" referrerpolicy="no-referrer">
```
(The original `default` theme self-hosts Font Awesome; new themes use the CDN.)

## Design principles — the "no AI slop" baseline

Distilled from [`alchaincyf/huashu-design`](https://github.com/alchaincyf/huashu-design). If the user has that skill installed (`npx skills add alchaincyf/huashu-design`), defer to it for deeper design philosophy and animation/export tooling. The rules below are the minimum bar this skill enforces.

**Avoid these AI-design clichés:**
- Purple → pink gradients
- Emoji used as functional icons (Font Awesome icons exist for a reason)
- Generic "glassy gradient blob" backgrounds with no purpose
- Center-aligned everything with no hierarchy
- Drop shadows on every element

**Prefer these moves:**
- A clear typographic hierarchy: one display face for the name/headline, one body face for tagline + links
- `text-wrap: pretty` (or `balance`) on the tagline so line breaks don't look ragged
- Real units: a single accent color, deliberate whitespace, consistent border radius across all elements (don't mix 4px buttons with 24px cards)
- One signature move per theme (e.g. brutalist border-shadow, editorial drop cap, terminal scanlines) — don't pile effects

**Quality bar every theme must meet:**
- WCAG AA contrast on body text and button text
- Keyboard-accessible: visible `:focus-visible` styles on every link and button
- Respects `@media (prefers-reduced-motion: reduce)` if you use any motion (disable transitions/animations in that block)
- **Dark mode (auto-switch): see the dedicated section below — non-negotiable.**
- **Responsive (RWD): see the dedicated section below — non-negotiable, this is the single most common failure mode.**

## Dark mode — required, auto-switch only

Every theme must work in both system appearances. The user does not click a button — the OS toggles between light and dark and the theme MUST follow. This is non-negotiable and a frequent source of regressions, so verify it explicitly.

**Hard rules:**

- Auto-switch via `@media (prefers-color-scheme: dark) { ... }` only. **No** JavaScript toggle. **No** `color-scheme: light only` (that disables auto-switching). **No** `<html data-theme="…">` workaround. The user's macOS / iOS / Windows / Android system setting is the source of truth.
- **Don't just invert.** Define a separate dark palette. Pure `#000` background causes banding on OLED panels and gives nothing for shadows or borders to push against — use elevated grays from the `#0d1117 / #14110d / #1c1814` family. White-on-black body text is harsh — prefer `#e6edf3 / #f3ecdf` etc.
- **Re-tune accents.** A red that reads on cream often goes muddy on charcoal; a soft pastel disappears. Test each accent color against the dark surface and either brighten/desaturate or pick a sibling hue. Both modes need WCAG AA (4.5:1 body, 3:1 large) — re-check on dark, don't assume.
- **Surface hierarchy still has to read.** On dark, cards / link buttons need to be one step lighter than the body (e.g. body `#0d1117`, card `#161b22`). Borders that were `rgba(0,0,0,0.12)` on light should drop in opacity, not just flip color.
- **Don't lose the signature move.** A brutalist drop-shadow in pure black disappears on a dark page — switch the shadow to a neon (cyan / yellow) on dark. A frosted glass card needs a different blur tint on a dark gradient. Keep the theme's identity in both modes; redesign the trick instead of dropping it.
- **Latest-link badge** (`.link-latest-badge`) must be re-tuned per mode. The light-mode color usually doesn't read on the dark surface — add a `@media (prefers-color-scheme: dark) { .link-latest-badge { ... } }` override.
- **Focus rings.** A `#1f6feb` ring that pops on white may need to brighten to `#58a6ff` on dark. Don't share `:focus-visible` styling blindly across modes.

**Authoring patterns:**

- Prefer **CSS-vars-driven palette swap**: define `:root { --bg: ...; --fg: ...; ... }` once, then `@media (prefers-color-scheme: dark) { :root { --bg: ...; ... } }` only changes the values. The rest of the CSS reads `var(--bg)` etc. and never needs duplicate rules. This is the cleanest pattern and the one most built-in themes use.
- Per-rule overrides are acceptable when only a few properties change (e.g. `default` theme), but the vars approach scales better.
- `terminal-retro` is the **dark-first reference**: its `:root` defaults are dark (green-on-black CRT), and the LIGHT variant is added via `@media (prefers-color-scheme: light)` (the inverse of the usual pattern) — translating the CRT identity to "deep olive on cream printer-paper". This is the right move when your theme has a dominant identity in one mode: keep that identity dominant, but still translate it into the other mode rather than skipping it. A user who pins `color_scheme: light` deserves SOMETHING that fits the theme, not the dark version unchanged.

**`color_scheme` override (required for new themes):**

Users can pin the page to a specific mode via `color_scheme: auto | light | dark` in `config.yml`. The theme must respect this — the system-default auto-switch is not enough. Wire it up like this:

1. **`index.html`** — add the scheme class on `<html>`:
   ```liquid
   <html lang="{{ lang }}"{% if color_scheme == "light" %} class="scheme-light"{% elsif color_scheme == "dark" %} class="scheme-dark"{% endif %}>
   ```
   For `auto`, no class is added; the @media query fires normally.

2. **`styles.css`** — gate the dark block on `:not(.scheme-light)` and add a `.scheme-dark` block that duplicates the dark vars. With CSS variables this is two short blocks:
   ```css
   :root { /* light vars */ }

   /* Auto + OS=dark, OR explicit "dark" */
   @media (prefers-color-scheme: dark) {
     :root:not(.scheme-light) { /* dark vars */ }
   }
   /* Forced "dark" — beats system preference */
   :root.scheme-dark { /* same dark vars */ }
   ```
   Yes, the dark vars are duplicated. There is no clean CSS-only way to avoid it short of `light-dark()` (Baseline 2024 — fine to use if you want a single source of truth and don't need IE-era support). For per-rule themes (no vars, like `default`), prefix every dark selector with `:root:not(.scheme-light)` and duplicate every rule under `:root.scheme-dark`. Mechanical but verbose.

3. **Verification** — set `color_scheme: light` in `config.yml`, rebuild, force your OS into dark mode. The page should stay light. Set `color_scheme: dark`, force OS to light. Page should stay dark. Set `color_scheme: auto`, toggle OS. Page should swap live.

**Dark-first themes (e.g. CRT, neon, vaporwave)** should still ship a light variant — but the light variant should *translate* the genre, not invert it (e.g. `terminal-retro` becomes "olive-on-cream printer paper" in light mode, not a generic light theme). Skipping a light variant is a last resort; a thoughtfully translated one is almost always more respectful of users with `color_scheme: light` set.

**Verification (do not skip):**

After your edits, before declaring the theme done:

1. Run `bundle exec ruby ./scaffold.rb` then open `_output/index.html`.
2. Toggle macOS *System Settings → Appearance* between Light and Dark (or use DevTools → Rendering → "Emulate CSS prefers-color-scheme"). The page must swap palettes without refresh.
3. In each mode, confirm: body text ≥ 4.5:1 contrast against background, latest-badge readable, focus ring visible, signature move (shadow / glass / drop cap / scanlines) still has identity.
4. If you used `./scripts/screenshot-themes.sh` or generated screenshots, capture both light and dark and compare side-by-side. Two visually-identical screenshots means the dark CSS is broken — investigate before shipping.

## Responsive design (RWD) — required

linkyee is overwhelmingly viewed on phones. A theme that looks great at 1440px but breaks at 360px is a broken theme. Treat the small-screen pass as part of "the theme is done", not a polish step.

**Layout rules:**
- **Mobile-first.** Author the base CSS for ~360px-wide phones; layer up with `min-width` media queries for tablet/desktop refinements. Don't write desktop-first then patch with `max-width` queries.
- **Container width:** use `width: 100%` with a `max-width` (e.g. 480–640px for the link column). Never set fixed pixel widths on top-level containers.
- **No horizontal scroll at any width 320–1920px.** If something would overflow (long unbroken strings like URLs, RSS post titles, repo names), use `overflow-wrap: anywhere` or `text-overflow: ellipsis` with `white-space: nowrap` — pick one per element and stick with it.
- **Test at minimum these widths:** 320, 375, 414, 768, 1024, 1440. Eyeball each. If you used `huashu-design` or any preview/screenshot capability, capture at 375 and 1280 at minimum.

**Typography:**
- Use `clamp()` for headline/name sizes so they scale fluidly without breakpoint jumps, e.g. `font-size: clamp(1.6rem, 5vw, 2.4rem)`.
- Body text floor of 16px on mobile (smaller triggers iOS auto-zoom on inputs and is below WCAG comfort threshold).
- Long Latest-link titles (RSS feed posts, YouTube video titles) can be 60+ chars — clamp them. The standard pattern: `.link-latest .link-text { display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: middle; }` Adapt the badge per theme but keep the truncation.

**Touch targets:**
- Minimum 44×44 CSS px hit area for every link, button, and social icon (Apple HIG / WCAG 2.5.5). Pad with `padding`, not just `height`, so the tappable area scales.
- Minimum 8px gap between adjacent tappable elements (no rage-tap collisions).

**Images / media:**
- `max-width: 100%; height: auto` on every `<img>`, including the avatar. The avatar should be a `clamp()`-sized circle so it doesn't dominate small viewports.
- Don't use `background-image` for content images — they don't scale predictably across DPRs.

**Density / safe areas:**
- Use `padding: env(safe-area-inset-top) ... env(safe-area-inset-bottom)` on the outermost container if you have edge-to-edge color, so notched iPhones don't crop content.
- Reduce vertical padding on small viewports — what looks airy on desktop looks wasted on a 568px-tall iPhone SE.

**Verification step (do not skip):**
After running `bundle exec ruby ./scaffold.rb`, also do one of the following before declaring the theme done:
1. `./preview.sh <new-theme>` and resize the browser through 320 → 1440 manually, OR
2. Use Playwright/headless browser at minimum 375×667 and 1280×800, OR
3. Open `_output/index.html` and toggle DevTools device mode through iPhone SE, iPhone 14, iPad, desktop.

If any of: horizontal scroll appears, text overflows the container, tap targets shrink below 44px, or the avatar covers more than ~30% of viewport height — fix before reporting back.

## When the user's brief is vague

Offer them 2–3 differentiated directions before writing code. Pick from these design schools (mirroring huashu-design's "schools" pattern, scoped to a single-page link list):

| School | Vibe | Good for |
|---|---|---|
| **Swiss minimal** | Mono/sans, hairline rules, monochrome, generous whitespace | Engineers, writers |
| **Editorial** | Serif headlines, drop caps, two-tone palette, magazine columns | Bloggers, journalists |
| **Neo-brutalism** | Thick borders, hard offset shadows, primary colors, no anti-aliasing of intent | Indie devs, artists |
| **Soft & friendly** | Pastel cards, rounded corners, hand-drawn accents, casual type | Creators, illustrators |
| **Terminal/Retro** | Monospace, CRT scanlines, blinking caret, green-on-black or amber | Hackers, infosec |

Built-in themes already exist for each: `minimal-mono`, `editorial-serif`, `neo-brutalism`, `paper-card`, `terminal-retro`, plus `glassmorphism`. Read one of them as a starting point if the user's request is close to an existing direction.

## Workflow you should follow

1. **Read context first** — `Read` `config.yml` to see the user's actual content (name, tagline, link count, link types). Don't design in the abstract.
2. **Read a reference theme** — `Read` `themes/default/index.html` (canonical structure) and one closer-aesthetic theme from `themes/`.
3. **Confirm direction** — if the brief is vague, present 2–3 options with one-line aesthetic descriptions. Wait for the user to pick.
4. **Generate the theme** — create `themes/<kebab-name>/`:
   - `index.html` — copy the structural skeleton from `themes/default/index.html`, preserve every Liquid variable and meta tag listed above, swap Font Awesome for the CDN `<link>`, redesign the body markup as needed
   - `styles.css` — the actual style work
   - `scripts.js` — empty file (or actual JS if the design needs it)
   - `images/profile.jpeg` — copy from `themes/default/images/profile.jpeg` via `cp`
   - `images/favicons/favicon.ico` — copy from `themes/default/images/favicons/favicon.ico` via `cp`
5. **Wire it up** — update `config.yml` `theme:` field via `Edit`. Match the exact existing format (`theme: default` → `theme: <new-name>`).
6. **Verify the build** — run `bundle exec ruby ./scaffold.rb`. Confirm:
   - Exit code 0 (no Liquid render errors)
   - `_output/index.html` exists
   - It contains the user's actual `name` and `tagline` text (no raw `{{` left in output)
7. **Tell the user how to preview** — `./preview.sh <theme-name>` builds + serves on `http://localhost:8080`.

## Common pitfalls to avoid

- **Don't drop the GA `{% if %}` guard.** Many users leave `google_analytics_id` blank; without the guard you'll inject a broken `gtag` config.
- **Don't change the loop variable assignment.** Liquid uses `{% assign link = item.link %}` (not `{% assign link = item %}`) — `config.yml` nests link data one level deeper than feels natural.
- **Don't remove `og:image` meta** — it uses `{{ avatar }}` and link previews on social media depend on it.
- **Don't hardcode the user's name/tagline into CSS** (e.g. as a `::before` pseudo-element). The site is rebuilt every time `config.yml` changes; the CSS must stay content-agnostic.
- **`scripts.js` must exist** even if empty — `index.html` references it.
- **Don't break `default`.** When generating a new theme, leave `themes/default/` untouched.
