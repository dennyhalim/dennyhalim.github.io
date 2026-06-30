require_relative 'Plugin'
require 'nokogiri'

# Fetch public profile stats for GitHub users / orgs (followers, following,
# repos count) by scraping the public profile page.
#
#   plugins:
#     - GithubProfilePlugin:
#         - ZhgChgLi
#
# Output (Hash<String, Hash>):
#   {
#     "ZhgChgLi" => { "followers" => 33, "following" => 0, "repos" => 29 }
#   }
#
# Use in Liquid:
#   {{ vars.GithubProfilePlugin['ZhgChgLi'].followers }} followers
#
# Why scrape instead of using the REST API: the unauthenticated REST API
# is capped at 60 requests/hour per IP. Frequent rebuilds during local
# development blow through that budget in minutes and start returning
# zeroes. The public profile HTML has no such limit.
#
# Result is disk-cached so a network blip / rate-limit during a build
# falls back to the last successful value (see Plugin#cache).
class GithubProfilePlugin < Plugin
  def execute
    args.each_with_object({}) do |user, out|
      out[user] = cache("gh-profile:v2:#{user}") { load_profile(user) } || empty
    end
  end

  private

  def empty
    { 'followers' => 0, 'following' => 0, 'repos' => 0 }
  end

  def load_profile(user)
    res = http_get("https://github.com/#{user}", headers: { 'User-Agent' => 'Mozilla/5.0' })
    return nil unless res.is_a?(Net::HTTPSuccess)

    doc = Nokogiri::HTML(res.body)

    {
      'followers' => count_for(doc, 'followers'),
      'following' => count_for(doc, 'following'),
      'repos' => repos_count(user)
    }
  end

  # Followers / following appear on the profile sidebar like:
  #   <a href="/<user>/followers"><span class="text-bold">33</span>followers</a>
  # Both /users/ and /orgs/ URL prefixes are accepted.
  def count_for(doc, kind)
    link = doc.css('a').find { |a| a['href'].to_s =~ %r{/#{kind}\z} }
    return 0 unless link
    span = link.at_css('span.text-bold') || link.at_css('span')
    parse_compact_int(span&.text)
  end

  # Scrape the public repo count from the user's profile page. The most
  # reliable signal across both /users/ and /orgs/ layouts is the `<meta
  # name="description">` line which always contains a phrase like
  #   "ZRealm has 29 repositories available."
  # Tab counters and side filters move/rename across GitHub redesigns;
  # the meta string has been stable for years.
  def repos_count(user)
    res = http_get("https://github.com/#{user}",
                   headers: { 'User-Agent' => 'Mozilla/5.0' })
    return 0 unless res.is_a?(Net::HTTPSuccess)

    doc = Nokogiri::HTML(res.body)
    desc = doc.at_xpath('//meta[@name="description"]')&.[]('content').to_s
    if (m = desc.match(/has\s+([\d,]+)\s+repositor/i))
      return parse_compact_int(m[1])
    end

    # Fallbacks if GitHub ever drops the meta string.
    counter = doc.at_css('a[data-tab-item="repositories"] span.Counter') ||
              doc.at_css('a[href$="?tab=repositories"] span.Counter')
    parse_compact_int(counter&.text)
  end

  def parse_compact_int(s)
    return 0 if s.nil?
    t = s.to_s.strip.delete(',')
    case t
    when /\A([\d.]+)k\z/i then ($1.to_f * 1_000).to_i
    when /\A([\d.]+)m\z/i then ($1.to_f * 1_000_000).to_i
    when /\A\d+\z/        then t.to_i
    else 0
    end
  end
end
