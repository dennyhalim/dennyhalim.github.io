require_relative 'Plugin'
require 'nokogiri'

# Fetch GitHub repo star counts.
#
#   plugins:
#     - GithubRepoStarsCountPlugin:
#         - ZhgChgLi/linkyee
#         - ZhgChgLi/ZMarkupParser
#
# Output (Hash<String, String|Integer>) accessible as:
#   {{ vars.GithubRepoStarsCountPlugin['ZhgChgLi/linkyee'] }}
#
# Why scrape instead of using the API: the public GitHub API rate-limits
# unauthenticated requests at 60/hour per IP, which is fragile for
# scheduled rebuilds. The repo page renders the star count directly.
class GithubRepoStarsCountPlugin < Plugin
  def execute
    args.each_with_object({}) do |repo, out|
      out[repo] = cache("gh-stars:#{repo}") { load_repo_stars(repo) } || 0
    end
  end

  private

  def load_repo_stars(repo)
    res = http_get("https://github.com/#{repo}")
    return nil unless res.is_a?(Net::HTTPSuccess)

    doc = Nokogiri::HTML(res.body)
    doc.at('span#repo-stars-counter-star')&.text
  end
end
