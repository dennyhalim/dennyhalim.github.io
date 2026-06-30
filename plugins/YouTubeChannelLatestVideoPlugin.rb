require_relative 'Plugin'
require 'nokogiri'
require 'time'

# Fetch the latest video for one or more YouTube channels.
# Uses YouTube's public Atom feed — no API key required.
#
# Each list item can be:
#   - A channel ID:   "UC_x5XG1OV2P6uZZ5FSM9Ttw"
#   - A handle:       "@GoogleDevelopers"
#   - A channel URL:  "https://www.youtube.com/@GoogleDevelopers"
#                     "https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw"
#
#   plugins:
#     - YouTubeChannelLatestVideoPlugin:
#         - "@GoogleDevelopers"
#         - "UC_x5XG1OV2P6uZZ5FSM9Ttw"
#
# Output (Hash<input, Hash>):
#   {
#     "@GoogleDevelopers" => {
#       "title"       => "...",
#       "url"         => "https://www.youtube.com/watch?v=...",
#       "video_id"    => "dQw4w9WgXcQ",
#       "thumbnail"   => "https://i.ytimg.com/vi/.../hqdefault.jpg",
#       "published"   => "2026-05-01",
#       "channel"     => "Google Developers"
#     }
#   }
#
# Use in Liquid:
#   <a href="{{ vars.YouTubeChannelLatestVideoPlugin['@GoogleDevelopers'].url }}">
#     {{ vars.YouTubeChannelLatestVideoPlugin['@GoogleDevelopers'].title }}
#   </a>
class YouTubeChannelLatestVideoPlugin < Plugin
  EMPTY = {
    'title' => '', 'url' => '', 'video_id' => '',
    'thumbnail' => '', 'published' => '', 'channel' => ''
  }.freeze

  def execute
    args.each_with_object({}) do |input, out|
      out[input] = cache("yt-latest:#{input}") { load_latest(input) } || EMPTY.dup
    end
  end

  private

  def load_latest(input)
    channel_id = resolve_channel_id(input)
    return nil unless channel_id

    feed_url = "https://www.youtube.com/feeds/videos.xml?channel_id=#{channel_id}"
    res = http_get(feed_url)
    return nil unless res.is_a?(Net::HTTPSuccess)

    doc = Nokogiri::XML(res.body)
    channel = doc.at_xpath('//xmlns:feed/xmlns:title')&.text.to_s.strip
    entry = doc.at_xpath('//xmlns:feed/xmlns:entry')
    return EMPTY.dup.merge('channel' => channel) unless entry

    video_id = entry.at_xpath('yt:videoId', 'yt' => 'http://www.youtube.com/xml/schemas/2015')&.text.to_s
    title = entry.at_xpath('xmlns:title')&.text.to_s.strip
    link = entry.at_xpath('xmlns:link')&.[]('href').to_s
    published = entry.at_xpath('xmlns:published')&.text.to_s
    {
      'title' => title,
      'url' => link,
      'video_id' => video_id,
      'thumbnail' => video_id.empty? ? '' : "https://i.ytimg.com/vi/#{video_id}/hqdefault.jpg",
      'published' => normalize_date(published),
      'channel' => channel
    }
  end

  # Accept channel_id (UC…), handle (@name), or YouTube URL → channel_id.
  # Disk-cached so a network failure falls back to the last good UC ID;
  # on success the cache is overwritten with the freshly resolved value.
  def resolve_channel_id(input)
    cache("yt:resolve:#{input}") do
      str = input.to_s.strip
      return str if str.start_with?('UC') && str.length >= 20 && !str.include?('/')

      url = if str.start_with?('http')
              str
            elsif str.start_with?('@')
              "https://www.youtube.com/#{str}"
            else
              "https://www.youtube.com/@#{str}"
            end

      # `/channel/UC...` URLs are already a direct path.
      if (m = url.match(%r{youtube\.com/channel/(UC[^/?#]+)}))
        next m[1]
      end

      # YouTube's handle pages serve a stripped response to non-browser UAs.
      res = http_get(url, headers: { 'User-Agent' => 'Mozilla/5.0' })
      next nil unless res.is_a?(Net::HTTPSuccess)

      m = res.body.match(%r{youtube\.com/channel/(UC[A-Za-z0-9_-]{10,})}) ||
          res.body.match(/"channelId":"(UC[A-Za-z0-9_-]+)"/) ||
          res.body.match(%r{itemprop="channelId" content="(UC[A-Za-z0-9_-]+)"}) ||
          res.body.match(/(UC[A-Za-z0-9_-]{20,24})/)
      m && m[1]
    end
  end

  def normalize_date(raw)
    return '' if raw.to_s.empty?
    Time.parse(raw).strftime('%Y-%m-%d')
  rescue ArgumentError
    raw.to_s[0, 10]
  end
end
