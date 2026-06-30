#!/usr/bin/env ruby
# seed-cache.rb — Prefill ./.linkyee-cache/ with sample plugin data.
#
# Run this once after cloning so the very first `bundle exec ruby ./scaffold.rb`
# produces a useful page even if you have no GitHub token, no network, or
# the GitHub unauth API rate limit (60/hour) is exhausted from frequent
# `preview.sh` rebuilds.
#
# The cache files use the same SHA1-of-key naming scheme that
# Plugin::cache(key, ttl:) uses, so the next successful network fetch
# transparently overwrites them with fresh data.
#
# Edit the `seeds` hash below to match the plugins enabled in your config.yml.

require 'json'
require 'fileutils'
require_relative 'plugins/Plugin'  # for Plugin.disk_cache_path

dir = Plugin.disk_cache_dir
FileUtils.mkdir_p(dir)

seeds = {
  # ── GithubRepoStarsCountPlugin ────────────────────────────────────────
  'gh-stars:ZhgChgLi/ZMarkupParser'    => '363',
  'gh-stars:ZhgChgLi/ZReviewTender'    => '60',
  'gh-stars:ZhgChgLi/ZMediumToMarkdown' => '50',
  'gh-stars:ZhgChgLi/linkyee'          => '12',

  # ── GithubLastCommitPlugin ────────────────────────────────────────────
  'gh-last-commit:ZhgChgLi/linkyee' => {
    'sha'     => '2fa00cc',
    'date'    => '2026-01-21',
    'message' => 'Update README.md'
  },

  # ── GithubProfilePlugin ───────────────────────────────────────────────
  'gh-profile:v2:ZhgChgLi' => {
    'followers' => 33,
    'following' => 0,
    'repos'     => 29
  },

  # ── RSSFeedPlugin ─────────────────────────────────────────────────────
  'rss:https://en.zhgchg.li/feed.xml' => [
    {
      'title' => 'AI Agent for Google Apps Script: Streamline Your Coding and Integration Effortlessly',
      'url'   => 'https://en.zhgchg.li/posts/zrealm-dev/ai-agent-for-google-apps-script-streamline-your-coding-and-integration-effortlessly-35cc65327d28/',
      'date'  => '2026-05-03'
    },
    {
      'title' => 'A Weekend Afternoon + Claude Design + Claude Code = Build Your Own Blog',
      'url'   => 'https://en.zhgchg.li/posts/zrealm-dev/a-weekend-afternoon-claude-design-claude-code-build-your-own-blog-6bf79c5b4dab/',
      'date'  => '2026-04-27'
    }
  ],

  # ── YouTubeChannelLatestVideoPlugin (latest video + handle resolver) ──
  'yt-latest:@zhgchgli' => {
    'title'     => 'AI 變廢為寶 - 用 Claude Design & Claude Code 打造屬於你的個人桌面 Dashboard',
    'url'       => 'https://www.youtube.com/watch?v=Zu0rbnu_iy8',
    'video_id'  => 'Zu0rbnu_iy8',
    'thumbnail' => 'https://i.ytimg.com/vi/Zu0rbnu_iy8/hqdefault.jpg',
    'published' => '2026-05-03',
    'channel'   => 'Harry Li'
  },
  'yt:resolve:@zhgchgli' => 'UCrO-ZvJhs5XOio0m-Hjb0aQ'
}

seeds.each do |key, value|
  path = Plugin.disk_cache_path(key)
  File.write(path, JSON.generate(value))
  puts "  #{key.ljust(48)} -> #{File.basename(path)}"
end
puts "\nWrote #{seeds.size} cache entries to #{dir}/"
