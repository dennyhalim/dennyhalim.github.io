require 'net/http'
require 'uri'
require 'json'
require 'fileutils'

# Base class for all linkyee plugins.
#
# A plugin is a Ruby class living under `./plugins/<ClassName>.rb` that is
# enabled via `config.yml`:
#
#   plugins:
#     - MyPlugin:
#         - some
#         - args
#
# At build time scaffold.rb instantiates `MyPlugin.new(<values from yaml>)`
# and calls `execute`. Whatever `execute` returns is stored under
# `vars.MyPlugin` and is then available inside `config.yml` and theme
# templates as `{{ vars.MyPlugin }}` (Liquid).
#
# ─── Subclass contract ────────────────────────────────────────────────
#
# Subclasses MUST:
#   - Inherit from Plugin (`class MyPlugin < Plugin`)
#   - Be saved as `./plugins/MyPlugin.rb` (filename == class name)
#   - Override `execute` and return a value Liquid can render
#     (String, Numeric, Hash with String keys, Array, or nested combos).
#
# Subclasses SHOULD:
#   - Use the helpers below (`http_get`, `http_get_json`, `log`, `cache`)
#     instead of reaching for Net::HTTP directly. They are battle-tested,
#     follow redirects, set a sensible User-Agent, and never raise.
#   - Be defensive: a flaky external API should NOT break the whole build.
#     If a fetch fails, return a safe default (0, "", {}, []).
#
# ─── Accessing arguments ──────────────────────────────────────────────
#
# linkyee passes plugin args from config.yml as `data` (array of values).
# For convenience use:
#
#   `args`   – the first argument list (typical case: a YAML list)
#   `params` – first argument when it is a Hash (typical case: keyword-style)
#
# Example (list-style):
#   plugins:
#     - GithubRepoStarsCountPlugin:
#         - ZhgChgLi/linkyee
#         - ZhgChgLi/ZMarkupParser
#   # inside the plugin: args == ["ZhgChgLi/linkyee", "ZhgChgLi/ZMarkupParser"]
#
# Example (hash-style):
#   plugins:
#     - RSSFeedPlugin:
#         url: https://blog.zhgchg.li/feed
#         limit: 5
#   # inside the plugin: params == {"url" => "...", "limit" => 5}
class Plugin
  attr_reader :data

  def initialize(data)
    @data = data
  end

  # Override in subclasses.
  def execute
  end

  # First positional argument list, e.g. `["repo1", "repo2"]`.
  # Returns [] if no arguments were given.
  def args
    first = Array(@data).first
    first.is_a?(Array) ? first : (first.nil? ? [] : [first])
  end

  # First positional argument when it is a Hash (keyword-style params).
  # Returns {} otherwise.
  def params
    first = Array(@data).first
    first.is_a?(Hash) ? first : {}
  end

  # ─── Helpers ────────────────────────────────────────────────────────

  # GET an HTTP(S) URL with redirect following. Returns Net::HTTPResponse,
  # or nil on failure. Never raises.
  #
  #   resp = http_get("https://api.github.com/repos/ZhgChgLi/linkyee")
  #   return 0 unless resp&.is_a?(Net::HTTPSuccess)
  def http_get(url, headers: {}, redirect_limit: 5, timeout: 15)
    return nil if redirect_limit <= 0

    uri = URI(url)
    req = Net::HTTP::Get.new(uri)
    default_headers.merge(headers).each { |k, v| req[k] = v }

    res = Net::HTTP.start(
      uri.hostname, uri.port,
      use_ssl: uri.scheme == 'https',
      open_timeout: timeout, read_timeout: timeout
    ) { |http| http.request(req) }

    case res
    when Net::HTTPRedirection
      http_get(res['location'], headers: headers, redirect_limit: redirect_limit - 1, timeout: timeout)
    else
      res
    end
  rescue StandardError => e
    log("http_get(#{url}) failed: #{e.class}: #{e.message}")
    nil
  end

  # GET a URL and parse the body as JSON. Returns parsed value, or `default`
  # on failure (network error, non-2xx, malformed JSON).
  def http_get_json(url, headers: {}, default: nil, **opts)
    res = http_get(url, headers: { 'Accept' => 'application/json' }.merge(headers), **opts)
    return default unless res.is_a?(Net::HTTPSuccess)

    JSON.parse(res.body)
  rescue JSON::ParserError => e
    log("http_get_json(#{url}) parse failed: #{e.message}")
    default
  end

  # Cache with stale-on-failure semantics — no TTL.
  #
  #   cache("gh:#{repo}") { http_get_json(...) }
  #
  # On every build the block is run first to fetch fresh data. If it
  # returns a non-nil value, the cache file under ./.linkyee-cache/ is
  # overwritten and that value is returned. If the block returns nil
  # (network failure, rate limit, parse error), the previously cached
  # value on disk is returned instead — so the rendered page always
  # has SOMETHING usable. Only when there is no cache AND the fetch
  # fails do we return nil to the caller.
  #
  # In-memory results are also cached so multiple plugins sharing a
  # key (e.g. several GitHub plugins hitting the same repo) only do
  # one network call per build.
  def cache(key)
    return Plugin.cache_store[key] if Plugin.cache_store.key?(key)
    path = Plugin.disk_cache_path(key)

    value = yield

    if !value.nil?
      # Fresh fetch succeeded — overwrite cache.
      Plugin.cache_store[key] = value
      FileUtils.mkdir_p(File.dirname(path))
      File.write(path, JSON.generate(value))
      return value
    end

    # Fetch failed — fall back to whatever's on disk (any age).
    if File.exist?(path)
      begin
        cached = JSON.parse(File.read(path))
        Plugin.cache_store[key] = cached
        log("fetch failed for #{key}; using cached value")
        return cached
      rescue JSON::ParserError
        # Corrupt cache file — fall through to nil.
      end
    end

    nil
  end

  # Print a build-log line with the plugin's class name as prefix.
  def log(msg)
    warn "[#{self.class.name}] #{msg}"
  end

  def self.cache_store
    @cache_store ||= {}
  end

  def self.disk_cache_dir
    './.linkyee-cache'
  end

  # Filenames use a human-readable slug of the key (so `ls .linkyee-cache/`
  # tells you what each file is) instead of an opaque hash. Unsafe chars
  # collapse to `--`; the result is capped at 200 chars to stay below
  # filesystem limits.
  def self.disk_cache_path(key)
    slug = key.gsub(/[^A-Za-z0-9._@-]+/, '--')
    slug = slug[0, 200]
    File.join(disk_cache_dir, "#{slug}.json")
  end

  private

  def default_headers
    {
      'User-Agent' => 'linkyee/1.0 (+https://github.com/ZhgChgLi/linkyee)',
      'Accept' => '*/*'
    }
  end
end
