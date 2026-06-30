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
- Functional in both light and dark mode (either via `@media (prefers-color-scheme: dark)` overrides, or a single palette that works in both)
- Responsive down to 320px width with no horizontal scroll
- Keyboard-accessible: visible `:focus-visible` styles on every link and button
- Respects `@media (prefers-reduced-motion: reduce)` if you use any motion (disable transitions/animations in that block)

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
