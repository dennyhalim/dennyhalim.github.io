import urllib.request
import xml.etree.ElementTree as ET
import feedparser
from datetime import datetime
import html
import json
import trafilatura

# Replace this with your actual raw OPML URL (e.g., GitHub Raw, Gist, or public server)
OPML_URL = "https://sabas.pages.dev/all.opml"

def parse_opml_remote(opml_url):
    try:
        req = urllib.request.Request(opml_url, headers={'User-Agent': 'Mozilla/5.0 rss-reader'})
        with urllib.request.urlopen(req) as response:
            opml_content = response.read()
            
        root = ET.fromstring(opml_content)
        categories = {}
        body = root.find('body')
        if body is not None:
            for cat_outline in body.findall('outline'):
                cat_name = cat_outline.attrib.get('text', 'Uncategorized')
                categories[cat_name] = []
                for feed_outline in cat_outline.findall('outline'):
                    feed_title = feed_outline.attrib.get('text', 'Unknown Source')
                    feed_url = feed_outline.attrib.get('xmlUrl')
                    if feed_url:
                        categories[cat_name].append({'title': feed_title, 'url': feed_url})
        return categories
    except Exception as e:
        print(f"Error fetching remote OPML: {e}")
        return {}

def get_full_content(entry, link):
    if hasattr(entry, 'content') and entry.content:
        return entry.content[0].get('value', '')
    downloaded = trafilatura.fetch_url(link)
    if downloaded:
        extracted = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        if extracted:
            paragraphs = extracted.split('\n\n')
            return "".join([f"<p>{html.escape(p)}</p>" for p in paragraphs if p.strip()])
    return entry.get('summary', 'Full content unavailable.')

def fetch_all_articles(categories):
    all_articles = []
    feed_registry = {}
    for cat_name, feeds in categories.items():
        feed_registry[cat_name] = []
        for feed in feeds:
            feed_title = feed['title']
            feed_registry[cat_name].append(feed_title)
            parsed_feed = feedparser.parse(feed['url'])
            for entry in parsed_feed.entries[:5]:
                published = entry.get('published_parsed') or entry.get('updated_parsed')
                pub_date = datetime(*published[:6]) if published else datetime.now()
                link = entry.get('link', '#')
                full_body = get_full_content(entry, link)
                all_articles.append({
                    'category': cat_name,
                    'source': feed_title,
                    'title': entry.get('title', 'No Title'),
                    'link': link,
                    'content': full_body,
                    'dateStr': pub_date.strftime('%b %d, %Y - %H:%M'),
                    'timestamp': pub_date.timestamp()
                })
    all_articles.sort(key=lambda x: x['timestamp'], reverse=True)
    return all_articles, feed_registry

def export_json_and_html(articles, feed_registry):
    data = {
        'registry': feed_registry,
        'articles': articles,
        'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M UTC')
    }
    with open("articles.json", "w", encoding="utf-8") as f:
        json.dump(data, f)

    html_content = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SMB Cyber Security - Full Text Reader</title>
    <!-- Pico CSS v2 -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <style>
        body { display: grid; grid-template-columns: 280px 1fr; min-height: 100vh; margin: 0; }
        aside { background: var(--card-background-color); border-right: var(--pico-border-width) solid var(--pico-muted-border-color); padding: 1.5rem; overflow-y: auto; height: 100vh; position: sticky; top: 0; }
        main { padding: 2rem; overflow-y: auto; }
        .nav-btn { width: 100%; text-align: left; margin-bottom: 0.35rem; font-size: 0.9rem; padding: 0.5rem 0.75rem; background: transparent; border: none; color: var(--pico-color); cursor: pointer; border-radius: var(--pico-border-radius); }
        .nav-btn:hover, .nav-btn.active { background: var(--pico-primary-background); color: var(--pico-primary-inverse); }
        .cat-header { font-size: 0.75rem; font-weight: bold; text-transform: uppercase; color: var(--pico-muted-color); margin: 1.25rem 0 0.5rem 0.5rem; letter-spacing: 0.05em; }
        .feed-btn { padding-left: 1.25rem; font-size: 0.85rem; opacity: 0.85; }
        .article-card { margin-bottom: 2rem; }
        .source-badge { font-size: 0.75rem; text-transform: uppercase; font-weight: bold; padding: 0.2rem 0.5rem; border-radius: 4px; background: var(--pico-secondary-background); color: var(--pico-secondary-inverse); }
        @media (max-width: 900px) {
            body { display: block; }
            aside { height: auto; position: static; border-right: none; border-bottom: var(--pico-border-width) solid var(--pico-muted-border-color); }
        }
    </style>
</head>
<body>
    <aside>
        <h4 style="margin-bottom: 1rem;">🔒 Security Feeds</h4>
        <button class="nav-btn active" onclick="filterView('all', null)">🌟 All Feeds Stream</button>
        <div id="nav-categories">Loading categories...</div>
    </aside>

    <main>
        <header style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
            <div>
                <h2 id="view-title" style="margin-bottom: 0.2rem;">All Feeds Stream</h2>
                <small id="view-subtitle" style="color: var(--pico-muted-color);">Showing latest updates across all security sources</small>
            </div>
            <div style="display: flex; align-items: center; gap: 1rem;">
                <small id="last-updated" style="color: var(--pico-muted-color);"></small>
                <button class="outline secondary" style="padding: 0.4rem 0.8rem; font-size: 0.8rem;" onclick="toggleTheme()">🌓 Theme</button>
            </div>
        </header>

        <section style="margin-bottom: 2rem;">
            <input type="search" id="search-input" placeholder="🔍 Search articles by keyword (e.g. ransomware, phishing, CISA)..." oninput="applyFilters()" />
        </section>

        <div id="articles-container"><article><p aria-busy="true">Loading articles...</p></article></div>
    </main>

    <script>
        let globalArticles = [];
        let globalRegistry = {};
        let currentFilterType = 'all';
        let currentFilterTarget = null;

        fetch('articles.json')
            .then(res => res.json())
            .then(data => {
                globalArticles = data.articles;
                globalRegistry = data.registry;
                document.getElementById('last-updated').innerText = 'Updated: ' + data.updatedAt;
                buildSidebar();
                applyFilters();
            })
            .catch(() => {
                document.getElementById('articles-container').innerHTML = '<article><p>Failed to load articles.json. Ensure GitHub Actions has run at least once.</p></article>';
            });

        function toggleTheme() {
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');
            html.setAttribute('data-theme', currentTheme === 'dark' ? 'light' : 'dark');
        }

        function buildSidebar() {
            const container = document.getElementById('nav-categories');
            let htmlContent = '';
            for (const [cat, feeds] of Object.entries(globalRegistry)) {
                htmlContent += `<div class="cat-header">${cat}</div>`;
                htmlContent += `<button class="nav-btn" onclick="filterView('category', '${cat}')">📁 All ${cat}</button>`;
                feeds.forEach(feed => {
                    htmlContent += `<button class="nav-btn feed-btn" onclick="filterView('feed', '${feed}')">▪ ${feed}</button>`;
                });
            }
            container.innerHTML = htmlContent;
        }

        function filterView(type, target) {
            currentFilterType = type;
            currentFilterTarget = target;
            document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            let title = "All Feeds Stream";
            let subtitle = "Showing latest updates across all security sources";

            if (type === 'category') {
                title = `Category: ${target}`;
                subtitle = `Showing updates from all sources in ${target}`;
            } else if (type === 'feed') {
                title = `Source: ${target}`;
                subtitle = `Showing full articles from ${target}`;
            }

            document.getElementById('view-title').innerText = title;
            document.getElementById('view-subtitle').innerText = subtitle;
            applyFilters();
        }

        function applyFilters() {
            const query = document.getElementById('search-input').value.toLowerCase().trim();
            let filtered = globalArticles;

            if (currentFilterType === 'category') {
                filtered = filtered.filter(a => a.category === currentFilterTarget);
            } else if (currentFilterType === 'feed') {
                filtered = filtered.filter(a => a.source === currentFilterTarget);
            }

            if (query) {
                filtered = filtered.filter(a => 
                    a.title.toLowerCase().includes(query) || 
                    a.content.toLowerCase().includes(query) ||
                    a.source.toLowerCase().includes(query) ||
                    a.category.toLowerCase().includes(query)
                );
            }

            renderArticles(filtered);
        }

        function renderArticles(list) {
            const container = document.getElementById('articles-container');
            if (list.length === 0) {
                container.innerHTML = '<article><p>No matching articles found.</p></article>';
                return;
            }
            let htmlContent = '';
            list.forEach(art => {
                htmlContent += `
                    <article class="article-card">
                        <header style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                            <span class="source-badge">${art.source}</span>
                            <small>${art.dateStr}</small>
                        </header>
                        <h3 style="margin-bottom: 0.5rem;"><a href="${art.link}" target="_blank" style="color: inherit; text-decoration: none;">${art.title}</a></h3>
                        <small style="color: var(--pico-muted-color); display: block; margin-bottom: 1rem;">Category: <b>${art.category}</b></small>
                        <div>${art.content}</div>
                        <footer>
                            <a href="${art.link}" target="_blank" class="secondary" style="font-size: 0.9rem;">View original source &rarr;</a>
                        </footer>
                    </article>
                `;
            });
            container.innerHTML = htmlContent;
        }
    </script>
</body>
</html>
    """
    with open("news.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    categories = parse_opml_remote(OPML_URL)
    articles, registry = fetch_all_articles(categories)
    export_json_and_html(articles, registry)
