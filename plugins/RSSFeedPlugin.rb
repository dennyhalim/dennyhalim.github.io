require_relative 'Plugin'
require 'nokogiri'
require 'time'

# Fetch the latest items from one or more RSS / Atom feeds.
# Works with Medium, blogs, podcasts, YouTube channels, etc.
#
# List style (each entry is a feed URL, default limit = 5):
#   plugins:
#     - RSSFeedPlugin:
#         - https://blog.zhgchg.li/feed
#         - https://medium.com/feed/ztravel
#
# Output (Hash<String, Array<Hash>>):
#   {
#     "https://blog.zhgchg.li/feed" => [
#       { "title" => "...", "url" => "...", "date" => "2026-05-01" },
#       ...
#     ]
#   }
#
# Use in Liquid:
#   {% for item in vars.RSSFeedPlugin['https://blog.zhgchg.li/feed'] %}
#     {{ item.title }} — {{ item.date }}
#   {% endfor %}
class RSSFeedPlugin < Plugin
  DEFAULT_LIMIT = 5

  def execute
    args.each_with_object({}) do |url, out|
      out[url] = cache("rss:#{url}") { load_feed(url, DEFAULT_LIMIT) } || []
    end
  end

  private

  def load_feed(url, limit)
    res = http_get(url)
    return nil unless res.is_a?(Net::HTTPSuccess)

    doc = Nokogiri::XML(res.body)

    # RSS 2.0: //item   /   Atom: //entry
    items = doc.xpath('//item')
    items = doc.xpath('//xmlns:entry') if items.empty?

    items.first(limit).map { |node| parse_item(node) }
  rescue StandardError => e
    log("parse failed for #{url}: #{e.message}")
    nil
  end

  def parse_item(node)
    title = (node.at_xpath('title') || node.at_xpath('xmlns:title'))&.text.to_s.strip

    # RSS uses <link>text</link>; Atom uses <link href="..."/>.
    link_node = node.at_xpath('link') || node.at_xpath('xmlns:link')
    link = link_node&.[]('href') || link_node&.text.to_s.strip

    raw_date = (
      node.at_xpath('pubDate') ||
      node.at_xpath('xmlns:updated') ||
      node.at_xpath('xmlns:published')
    )&.text.to_s.strip

    {
      'title' => title,
      'url' => link,
      'date' => normalize_date(raw_date)
    }
  end

  def normalize_date(raw)
    return '' if raw.empty?
    Time.parse(raw).strftime('%Y-%m-%d')
  rescue ArgumentError
    raw[0, 10]
  end
end
