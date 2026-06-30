---
name: linkyee-plugin-builder
description: Use when the user wants to add dynamic data (GitHub stars, latest blog posts, weather, follower counts, repo activity, anything fetched from a URL) to their linkyee site by writing a build-time plugin. Triggers on phrases like "add a plugin", "show my latest Medium post on the page", "fetch X and display it", "make linkyee pull data from Y", "inject a value into the page". Generates `plugins/<PluginName>.rb`, wires it up in `config.yml`, references it in the right Liquid spot, and runs the build to verify.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# linkyee Plugin Builder

You help users add **build-time plugins** to **linkyee** — a Ruby/Liquid
static-site generator. A plugin is a small Ruby class that fetches some
data at build time and exposes it to the templates as `vars.<PluginName>`.

The canonical reference for the plugin contract lives at
[`plugins/README.md`](../../../plugins/README.md). Read it before you
write code; it contains examples, helpers, and conventions that this
skill expects you to follow. Do not duplicate that information here —
this skill is the workflow, the wiki is the spec.

## Mental model in one paragraph

`config.yml` lists enabled plugins. At build time `scaffold.rb`
instantiates `<PluginName>.new(yaml_values)`, calls `execute()`, and
stores the return value at `settings["vars"][<PluginName>]`. Liquid then
renders `{{ vars.<PluginName> }}` (and friends) inside `config.yml`
strings and the theme's `index.html`. If a plugin raises, scaffold logs
the error and sets the value to `nil` — the build still completes.

## Workflow

Follow these steps **in order**. Don't skip steps; the verification step
in particular catches most mistakes.

### 1. Understand the request

Before writing anything, confirm:

- **What data** does the user want? (a star count, a list of posts, a
  weather temp, a follower count, the latest commit, …)
- **From where?** (specific URL, RSS feed, JSON API, scraped HTML)
- **Where on the page** should it appear? (footer, a link's text, a new
  link, a new section in `index.html`)

If anything is ambiguous, ask **one** focused question. Don't ask three
clarifying questions at once.

### 2. Check whether a built-in plugin already covers it

Read `plugins/README.md` § "Built-in plugins". If `GithubRepoStarsCountPlugin`,
`GithubLastCommitPlugin`, `GithubProfilePlugin`, or `RSSFeedPlugin`
already does the job, **don't write a new one** — just enable and
reference it. Tell the user.

### 3. Read the existing config

Run `Read` on `config.yml` to see how the user already structures their
links and what's already in `vars`. This affects naming and where to
inject the value.

### 4. Write the plugin

Create `plugins/<PluginName>.rb`:

- Name the class to match the file. Use a descriptive `*Plugin` suffix
  (e.g. `WeatherPlugin`, `MediumLatestPostsPlugin`).
- `require_relative 'Plugin'` at the top.
- Inherit from `Plugin`.
- Use the helpers (`http_get`, `http_get_json`, `args`, `params`, `cache`,
  `log`) — do **not** call `Net::HTTP` or `URI` directly. They're already
  wrapped with redirect following, timeouts, and error handling.
- Be defensive. Return a sensible default (`0`, `""`, `{}`, `[]`) on
  failure. Plugins must not raise.
- Use **String** keys in returned hashes (Liquid can't look up symbol
  keys).
- Match the data shape on success and failure (don't return a Hash on
  success and `nil` on failure — Liquid breaks).

Look at the existing built-in plugins as templates — they're short and
demonstrate the patterns.

### 5. Wire it up in config.yml

Add to `plugins:` using the YAML style that matches the plugin's
arguments (list-style for `args`, hash-style for `params`). Then
reference `{{ vars.<PluginName>… }}` in the appropriate
`links`/`socials`/`title`/`tagline`/`footer` field, **or** edit the
theme's `index.html` if the user wants a loop / conditional.

### 6. Verify the build

Run:

```bash
bundle exec ruby ./scaffold.rb
```

Then check:

- Build exits 0
- No `[<PluginName>]` or `[scaffold] Plugin '<PluginName>' failed` lines
  in stderr
- The injected value appears in `_output/index.html` (grep for it)

If the value is missing, **read the stderr output** — the new
`scaffold.rb` swallows plugin failures but logs them clearly. Do not
guess; fix the underlying error.

### 7. Secrets — non-negotiable

If the plugin needs an API key, personal access token, OAuth token,
or any other credential:

- **Never** put the secret value in `config.yml`. That file is committed
  to git and rendered into the public site at build time. Anything in it
  is public, forever, including in old commits.
- **Never** hardcode the secret in the plugin's `.rb` file. Same problem.
- **Always** read it from `ENV`:
  ```ruby
  token = ENV["MEDIUM_TOKEN"]
  return [] if token.nil? || token.empty?
  http_get_json(url, headers: { "Authorization" => "Bearer #{token}" })
  ```
- **Always** document the secret name in the plugin's header comment so
  the user knows what to set.
- **Always** tell the user how to wire it through, in three steps:
  1. **Repo secret**: GitHub → repo → *Settings → Secrets and variables
     → Actions → New repository secret*. Name it (e.g. `MEDIUM_TOKEN`),
     paste value.
  2. **Workflow env**: edit `.github/workflows/build.yml`, add an `env:`
     block to the `Deploy` step:
     ```yaml
     - name: Deploy
       env:
         MEDIUM_TOKEN: ${{ secrets.MEDIUM_TOKEN }}
       run: bash deploy.sh
     ```
  3. **Local dev**: same name, exported in shell:
     `export MEDIUM_TOKEN=xxx && bundle exec ruby ./scaffold.rb`

If the user asks you to "just paste the token in config.yml for now",
**refuse and explain why**. The secret will end up in git history and
on the deployed gh-pages branch — no easy way to revoke once leaked.

### 8. Report back

Tell the user:

- What plugin was created
- What got added to `config.yml`
- Where in the rendered page the value now appears
- How to extend it (e.g. "add more entries to the list under
  `MyPlugin:`")

## What NOT to do

- **Don't** add new gems to the `Gemfile` unless absolutely required.
  `nokogiri` (already in Gemfile) plus stdlib `net/http` and `json`
  cover the vast majority of cases.
- **Don't** scrape sites that have an obvious public JSON/Atom endpoint.
  RSS / Atom (`/feed`, `/commits.atom`) and JSON APIs are far more
  stable than HTML scraping.
- **Don't** hardcode credentials. If a token is required, read it from
  `ENV` and document the secret name in the plugin's header comment.
- **Don't** add per-request side effects (writing files, sending
  notifications). `execute` should be a pure data fetch.
- **Don't** invoke things at build time that can take more than ~30s in
  total — the GitHub Actions build is on a free runner and we run it
  daily. Cap the work.
- **Don't** touch theme files unless the user asked for layout changes.
  Most plugin requests are satisfied by editing `config.yml` only.
- **Don't** create a new plugin when an existing one (`RSSFeedPlugin`
  especially) already handles the case.

## Anti-patterns to refuse

- *"Make it run in the visitor's browser instead."* — linkyee is a
  static site; plugins are build-time only. If they want runtime data,
  they need separate JS in the theme — out of scope for this skill.
- *"Have the plugin email me when X."* — no side effects in plugins.
  Suggest a separate GitHub Actions workflow.
