require_relative 'Plugin'
require 'nokogiri'

# Fetch the most recent commit info for one or more GitHub repos.
#
#   plugins:
#     - GithubLastCommitPlugin:
#         - ZhgChgLi/linkyee
#
# Output (Hash<String, Hash>):
#   {
#     "ZhgChgLi/linkyee" => {
#       "sha" => "7d7392d2",
#       "date" => "2026-05-07",
#       "message" => "Add AI Style Designer skill, ..."
#     }
#   }
#
# Use in Liquid:
#   Last commit: {{ vars.GithubLastCommitPlugin['ZhgChgLi/linkyee'].date }}
class GithubLastCommitPlugin < Plugin
  def execute
    args.each_with_object({}) do |repo, out|
      out[repo] = cache("gh-last-commit:#{repo}") { load_last_commit(repo) } ||
                  { 'sha' => '', 'date' => '', 'message' => '' }
    end
  end

  private

  def load_last_commit(repo)
    # Use the public commits feed (Atom) — no auth, no rate limit.
    res = http_get("https://github.com/#{repo}/commits.atom")
    return nil unless res.is_a?(Net::HTTPSuccess)

    doc = Nokogiri::XML(res.body)
    entry = doc.at_xpath('//xmlns:entry')
    return nil unless entry

    sha = entry.at_xpath('xmlns:id')&.text.to_s.split('/').last.to_s[0, 7]
    date = entry.at_xpath('xmlns:updated')&.text.to_s[0, 10]
    title = entry.at_xpath('xmlns:title')&.text.to_s.strip
    { 'sha' => sha, 'date' => date, 'message' => title }
  end
end
