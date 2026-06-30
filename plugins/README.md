# linkyee Plugins — Developer Wiki

Plugins are small Ruby classes that run **at build time** to inject dynamic
values into your linkyee site (GitHub stars, latest blog posts, last commit
date, anything you can fetch from a URL). The build runs once on push and
once a day via GitHub Actions, so plugins do not run in the user's browser
— they just bake values into the generated HTML.

This wiki is the canonical reference for writing your own plugin. It is
also the source of truth that the [`linkyee-plugin-builder`](../.claude/skills/linkyee-plugin-builder/)
Claude skill reads when an AI generates a plugin for you.

- [How it works](#how-it-works)
- [Plugin contract](#plugin-contract)
- [Quick start: your first plugin in 30 seconds](#quick-start)
- [Built-in plugins](#built-in-plugins)
- [Helpers provided by the base class](#helpers-provided-by-the-base-class)
- [Common patterns (HTTP, JSON, scraping, caching)](#common-patterns)
- [Rendering output in Liquid](#rendering-output-in-liquid)
- [Debugging](#debugging)
- [Letting AI write your plugin](#letting-ai-write-your-plugin)

---

## How it works

```
config.yml ──► scaffold.rb ──► instantiate plugin ──► execute() ──► vars.<PluginName>
                                                                           │
                                                                           ▼
                                                          rendered into Liquid templates
```

1. You enable a plugin in `config.yml` under `plugins:`.
2. `scaffold.rb` requires `./plugins/<PluginName>.rb`, instantiates the
   class with the YAML values, and calls `execute()`.
3. The return value is stored in `settings["vars"][<PluginName>]`.
4. Every string in `config.yml` (links, socials, title, footer…) and the
   theme's `index.html` is rendered through Liquid, so you can reference
   `{{ vars.<PluginName> }}` anywhere.
5. If a plugin raises, `scaffold.rb` logs the error and sets the value to
   `nil` — the build still succeeds.

---

## Plugin contract

A plugin is a Ruby class that:

| Rule | Detail |
|---|---|
| Inherits from `Plugin` | `class MyPlugin < Plugin` |
| Lives at `./plugins/MyPlugin.rb` | Filename **must** match the class name |
| Implements `execute` | Returns a Liquid-renderable value (String, Number, Hash with String keys, Array, or nested combos) |
| Is defensive | Returns a safe default on network/parse failure — never `raise` |
| Has no side effects | Don't write files; just return data |

That's it. No registration, no manifest.

---

## Quick start

Add this to `plugins/HelloPlugin.rb`:

```ruby
require_relative 'Plugin'

class HelloPlugin < Plugin
  def execute
    "Hello, #{params['name'] || 'world'}!"
  end
end
```

Enable it in `config.yml`:

```yaml
plugins:
  - HelloPlugin:
      name: linkyee

footer: "{{ vars.HelloPlugin }}"
```

Run `ruby scaffold.rb` and open `_output/index.html` — the footer reads
`Hello, linkyee!`.

---

## Built-in plugins

| Plugin | Purpose | Argument style |
|---|---|---|
| [`GithubRepoStarsCountPlugin`](./GithubRepoStarsCountPlugin.rb) | Star counts for one or more repos | List of `owner/repo` |
| [`GithubLastCommitPlugin`](./GithubLastCommitPlugin.rb) | Latest commit sha / date / message | List of `owner/repo` |
| [`GithubProfilePlugin`](./GithubProfilePlugin.rb) | Followers and public-repo count | List of GitHub usernames |
| [`RSSFeedPlugin`](./RSSFeedPlugin.rb) | Latest items from an RSS / Atom feed (Medium, blogs, YouTube, podcasts) | List of feed URLs |
| [`CountdownPlugin`](./CountdownPlugin.rb) | Days until / since target dates | Hash of `label: YYYY-MM-DD` |
| [`YouTubeChannelLatestVideoPlugin`](./YouTubeChannelLatestVideoPlugin.rb) | Latest video for one or more YouTube channels | List of channel ID / `@handle` / channel URL |

Each file is short — read them as templates when writing your own.

---

## Helpers provided by the base class

Defined in [`Plugin.rb`](./Plugin.rb).

### Argument accessors

```ruby
args     # => first argument list, e.g. ["repo1", "repo2"]
params   # => first argument when it is a Hash, e.g. {"url" => "...", "limit" => 5}
data     # => the raw arguments array (escape hatch)
```

YAML list-style → use `args`:

```yaml
- MyPlugin:
    - first
    - second
```

YAML hash-style → use `params`:

```yaml
- MyPlugin:
    url: https://example.com
    limit: 5
```

### `http_get(url, headers: {}, redirect_limit: 5, timeout: 15)`

GET an HTTP(S) URL with redirect following and a sensible User-Agent.
Returns a `Net::HTTPResponse` or `nil`. **Never raises.**

```ruby
res = http_get("https://example.com/data")
return [] unless res.is_a?(Net::HTTPSuccess)
process(res.body)
```

### `http_get_json(url, headers: {}, default: nil, ...)`

Same as `http_get` but parses the body as JSON. Returns `default` on any
failure (network, non-2xx, malformed JSON).

```ruby
data = http_get_json("https://api.github.com/repos/#{repo}", default: {})
data["stargazers_count"] || 0
```

### `cache(key) { ... }`

Memoize across plugin instances within a single build. Useful when several
plugins share data (e.g. multiple GitHub plugins hitting the same repo).

```ruby
cache("repo:#{repo}") { http_get_json("https://api.github.com/repos/#{repo}") }
```

### `log(msg)`

Prints to stderr with the plugin class as prefix. Visible in GitHub
Actions logs.

```ruby
log("falling back to cached value")
```

---

## Common patterns

### 1. JSON API

```ruby
class WeatherPlugin < Plugin
  def execute
    args.each_with_object({}) do |city, out|
      json = http_get_json("https://wttr.in/#{city}?format=j1", default: {})
      out[city] = json.dig("current_condition", 0, "temp_C") || "?"
    end
  end
end
```

### 2. HTML scraping (when no API is available)

```ruby
require 'nokogiri'

class HNFrontPagePlugin < Plugin
  def execute
    res = http_get("https://news.ycombinator.com/")
    return [] unless res.is_a?(Net::HTTPSuccess)

    Nokogiri::HTML(res.body).css(".titleline > a").first(5).map do |a|
      { "title" => a.text, "url" => a["href"] }
    end
  end
end
```

### 3. Safe defaults

Always return the same shape on success and failure — Liquid templates
break ugly when a Hash becomes a String:

```ruby
empty = { "count" => 0, "label" => "" }
return empty unless res.is_a?(Net::HTTPSuccess)
```

### 4. Reading a secret / token (the only safe way)

> ⚠️ **Never put credentials in `config.yml` or in a plugin's `.rb`
> source.** `config.yml` is committed to git and rendered into the
> public gh-pages site; once a token lands in commit history, treat it
> as compromised.

The only acceptable storage for an API key, PAT, OAuth token, or
similar is a **GitHub Actions repository secret**, exposed to the build
via env-var, read from `ENV` inside the plugin.

**Three-step setup:**

1. **Add the repo secret** — GitHub → your repo → *Settings → Secrets
   and variables → Actions → New repository secret*. Name it
   (e.g. `MEDIUM_TOKEN`), paste the value.
2. **Pass it through the workflow** — edit `.github/workflows/build.yml`
   and add an `env:` block to the `Deploy` step:
   ```yaml
   - name: Deploy
     env:
       MEDIUM_TOKEN: ${{ secrets.MEDIUM_TOKEN }}
     run: bash deploy.sh
   ```
3. **Read it in the plugin** — and bail gracefully if missing:
   ```ruby
   token = ENV["MEDIUM_TOKEN"]
   return [] if token.nil? || token.empty?
   http_get_json(url, headers: { "Authorization" => "Bearer #{token}" })
   ```

For local development, export the same env var in your shell before
running `bundle exec ruby ./scaffold.rb`. Do **not** check it into
`.envrc` / `.env` files that might be committed; if you use `direnv`,
add `.envrc` to `.gitignore`.

Document the secret name in the plugin file's header comment so the
next maintainer knows what to provision.

---

## Rendering output in Liquid

Anything `execute` returns lands at `vars.<PluginName>`. Examples:

```yaml
# Scalar
title: "{{ vars.HelloPlugin }}"

# Hash lookup by key
text: "{{ vars.GithubRepoStarsCountPlugin['ZhgChgLi/linkyee'] }} Stars"

# Nested hash
text: "Last update: {{ vars.GithubLastCommitPlugin['ZhgChgLi/linkyee'].date }}"

# Iteration (works in theme index.html, not in config.yml string fields)
{% for post in vars.RSSFeedPlugin['https://blog.zhgchg.li/feed'] %}
  <a href="{{ post.url }}">{{ post.title }}</a>
{% endfor %}
```

Important:

- Use **String keys** in returned hashes (`"name"`, not `:name`). Liquid
  cannot look up symbol keys.
- `config.yml` only renders inline `{{ ... }}`, not `{% for %}` blocks.
  For loops/conditionals, edit the theme's `index.html`.

---

## Debugging

Run the build locally and watch stderr:

```bash
ruby scaffold.rb
# look for: [MyPlugin] http_get(...) failed: ...
# or:       [scaffold] Plugin 'MyPlugin' failed: ...
```

Inspect the rendered output:

```bash
open _output/index.html
```

If a `{{ vars.X }}` reference renders as empty, the plugin probably
returned `nil` — check the build log for the failure reason.

You can also `puts` arbitrary debug data from inside `execute`; it goes
to the build log without affecting the page.

---

## Letting AI write your plugin

Open this repo with [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
and just describe what you want, e.g.:

> *"Add a plugin that shows the current weather in Taipei in the footer."*
>
> *"Add a plugin that fetches the latest 3 posts from my Medium feed and lists them as additional links."*

The bundled [`linkyee-plugin-builder`](../.claude/skills/linkyee-plugin-builder/SKILL.md)
skill knows this contract and will: read your `config.yml` → confirm the
data source and shape → generate `plugins/<YourPlugin>.rb` → wire it up
in `config.yml` → run `ruby scaffold.rb` to verify.
