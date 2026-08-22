// API base URL - will work both locally and when deployed
const API_BASE = window.location.origin;

let currentCategory = 'top_stories';
let currentTimeRange = '1d';
let currentSearchQuery = '';
let allArticles = [];
let viewingBookmarks = false;
let viewingHistory = false;
let latestIngestion = null;

// Initialize the page
document.addEventListener('DOMContentLoaded', () => {
    loadThemePreference();
    setupEventListeners();
    loadArticles();
    loadCategoryCounts();
    loadLatestIngestion();
});

async function loadLatestIngestion() {
    try {
        const response = await fetch(`${API_BASE}/api/stats`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const stats = await response.json();
        latestIngestion = stats.latest_ingestion;
    } catch (error) {
        console.error('Error loading latest ingestion time:', error);
        latestIngestion = null;
    }
    renderLastUpdated();
}

function renderLastUpdated() {
    const updateEl = document.getElementById('last-update');
    updateEl.textContent = latestIngestion
        ? `Data as of ${new Date(latestIngestion).toLocaleString()}`
        : 'Data freshness unknown';
}

async function loadCategoryCounts() {
    try {
        const response = await fetch(`${API_BASE}/api/categories?time_range=${currentTimeRange}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const categories = await response.json();

        const countsByCategory = Object.fromEntries(categories.map(c => [c.category, c.count]));
        document.querySelectorAll('.category-count').forEach(el => {
            el.textContent = countsByCategory[el.dataset.countFor] || 0;
        });
    } catch (error) {
        console.error('Error loading category counts:', error);
    }
}

function loadThemePreference() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
}

function setTheme(theme) {
    document.body.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    
    // Update active state on theme buttons
    document.querySelectorAll('.theme-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.theme === theme);
    });
}

function setupEventListeners() {
    // Category filters
    document.querySelectorAll('.category-btn[data-category]').forEach(btn => {
        btn.addEventListener('click', () => selectCategory(btn.dataset.category));
    });

    // Bookmarks view
    document.getElementById('bookmarks-btn').addEventListener('click', selectBookmarksView);

    // History view
    document.getElementById('history-btn').addEventListener('click', selectHistoryView);

    // Time range filters
    document.querySelectorAll('.time-btn').forEach(btn => {
        btn.addEventListener('click', () => selectTimeRange(btn.dataset.time));
    });

    // Theme switcher
    document.querySelectorAll('.theme-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const theme = e.target.closest('.theme-btn').dataset.theme;
            setTheme(theme);
        });
    });

    // Search functionality
    const searchInput = document.getElementById('search-input');
    let searchTimeout;
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            currentSearchQuery = e.target.value.toLowerCase().trim();
            filterAndDisplayArticles();
        }, 300); // Debounce for 300ms
    });
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            searchInput.value = '';
            currentSearchQuery = '';
            filterAndDisplayArticles();
            searchInput.blur();
        }
    });

    document.getElementById('shortcuts-help').addEventListener('click', (e) => {
        if (e.target.id === 'shortcuts-help') closeShortcutsHelp();
    });

    // Mobile sidebar drawer
    document.getElementById('sidebar-toggle').addEventListener('click', openSidebar);
    document.getElementById('sidebar-close').addEventListener('click', closeSidebar);
    document.getElementById('sidebar-backdrop').addEventListener('click', closeSidebar);
    document.querySelectorAll('.category-btn, #bookmarks-btn, #history-btn').forEach(btn => {
        btn.addEventListener('click', closeSidebar);
    });

    setupKeyboardShortcuts();
}

function openSidebar() {
    document.getElementById('sidebar').classList.add('open');
    document.getElementById('sidebar-backdrop').classList.add('open');
}

function closeSidebar() {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('sidebar-backdrop').classList.remove('open');
}

function selectCategory(category) {
    document.querySelectorAll('.category-btn').forEach(b => b.classList.remove('active'));
    const btn = document.querySelector(`.category-btn[data-category="${category}"]`);
    if (btn) btn.classList.add('active');

    viewingBookmarks = false;
    viewingHistory = false;
    currentCategory = category;
    updateViewToggles();
    loadArticles();
}

function selectBookmarksView() {
    document.querySelectorAll('.category-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('bookmarks-btn').classList.add('active');

    viewingBookmarks = true;
    viewingHistory = false;
    updateViewToggles();
    loadArticles();
}

function selectHistoryView() {
    document.querySelectorAll('.category-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('history-btn').classList.add('active');

    viewingBookmarks = false;
    viewingHistory = true;
    updateViewToggles();
    loadArticles();
}

function updateViewToggles() {
    document.getElementById('clear-history-btn').style.display = viewingHistory ? 'inline-block' : 'none';
}

async function clearHistory() {
    if (!confirm('Clear all read history?')) return;
    try {
        const response = await fetch(`${API_BASE}/api/history`, { method: 'DELETE' });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        loadArticles();
    } catch (error) {
        console.error('Error clearing history:', error);
    }
}

async function logHistory(articleId) {
    try {
        await fetch(`${API_BASE}/api/history/${articleId}`, { method: 'POST' });
    } catch (error) {
        console.error('Error logging history:', error);
    }
}

function selectTimeRange(time) {
    document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
    const btn = document.querySelector(`.time-btn[data-time="${time}"]`);
    if (btn) btn.classList.add('active');

    currentTimeRange = time;
    loadArticles();
    loadCategoryCounts();
}

const TIME_RANGE_KEYS = { h: '1h', d: '1d', w: '7d' };

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        const searchInput = document.getElementById('search-input');
        const isTyping = document.activeElement === searchInput;

        // '/' focuses search regardless of current focus (unless already typing)
        if (e.key === '/' && !isTyping) {
            e.preventDefault();
            searchInput.focus();
            return;
        }

        if (e.key === '?' && !isTyping) {
            e.preventDefault();
            toggleShortcutsHelp();
            return;
        }

        if (e.key === 'Escape') {
            closeShortcutsHelp();
            closeSidebar();
            if (isTyping) searchInput.blur();
            return;
        }

        if (isTyping) return; // don't hijack other keys while typing

        if (e.key === 'r') {
            e.preventDefault();
            refreshArticles();
        } else if (e.key in TIME_RANGE_KEYS) {
            e.preventDefault();
            selectTimeRange(TIME_RANGE_KEYS[e.key]);
        } else if (e.key >= '1' && e.key <= '8') {
            e.preventDefault();
            const categoryBtns = document.querySelectorAll('.category-btn[data-category]');
            const btn = categoryBtns[parseInt(e.key, 10) - 1];
            if (btn) selectCategory(btn.dataset.category);
        }
    });
}

function toggleShortcutsHelp() {
    document.getElementById('shortcuts-help').classList.toggle('open');
}

function closeShortcutsHelp() {
    document.getElementById('shortcuts-help').classList.remove('open');
}

async function loadArticles() {
    const container = document.getElementById('articles-container');
    container.innerHTML = '<div class="loading">Loading articles...</div>';

    try {
        let url;
        if (viewingHistory) {
            url = `${API_BASE}/api/history`;
        } else if (viewingBookmarks) {
            url = `${API_BASE}/api/bookmarks`;
        } else {
            const params = new URLSearchParams({
                time_range: currentTimeRange,
                limit: 100
            });
            params.append('category', currentCategory);
            url = `${API_BASE}/api/articles?${params}`;
        }

        const response = await fetch(url);

        if (!response.ok) {
            const err = new Error(`HTTP ${response.status}`);
            err.status = response.status;
            throw err;
        }

        allArticles = await response.json();
        filterAndDisplayArticles();

    } catch (error) {
        console.error('Error loading articles:', error);
        container.innerHTML = `<div class="error">${describeLoadError(error)}</div>`;
    }
}

function describeLoadError(error) {
    const subject = viewingHistory ? 'your history' : viewingBookmarks ? 'your bookmarks' : 'articles';

    if (error instanceof TypeError) {
        // fetch() throws TypeError for network-level failures (server down, no connection, CORS)
        return `Can't reach the server. Is the backend running?<br><small>Tried to load ${subject} from ${API_BASE}</small>`;
    }

    if (error.status >= 500) {
        return `The server ran into a problem loading ${subject} (HTTP ${error.status}).<br><small>Try refreshing in a moment.</small>`;
    }

    if (error.status === 404) {
        return `Couldn't find ${subject} (HTTP 404).<br><small>This may be a temporary issue — try refreshing.</small>`;
    }

    return `Failed to load ${subject} (HTTP ${error.status || 'unknown'}).<br><small>${error.message}</small>`;
}

function filterAndDisplayArticles() {
    let filtered = allArticles;

    // Filter by search query if present
    if (currentSearchQuery) {
        filtered = allArticles.filter(article => 
            article.title.toLowerCase().includes(currentSearchQuery)
        );
    }

    displayArticles(filtered);
    updateStats(filtered.length);
}

function displayArticles(articles) {
    const container = document.getElementById('articles-container');

    if (articles.length === 0) {
        container.innerHTML = `<div class="no-articles">${describeEmptyState()}</div>`;
        return;
    }

    container.innerHTML = articles.map(article => createArticleCard(article)).join('');
}

function describeEmptyState() {
    if (viewingHistory) {
        if (currentSearchQuery) {
            return `No history matches "${escapeHtml(currentSearchQuery)}".<br>Try a different search term.`;
        }
        return `🕘 No reading history yet.<br>Articles you click through to read will show up here.`;
    }

    if (viewingBookmarks) {
        if (currentSearchQuery) {
            return `No bookmarks match "${escapeHtml(currentSearchQuery)}".<br>Try a different search term.`;
        }
        return `⭐ No bookmarks yet.<br>Click the star on any article to save it here.`;
    }

    if (currentSearchQuery) {
        return `No headlines match "${escapeHtml(currentSearchQuery)}".<br>Try a different search term or time range.`;
    }

    return `No articles found for this category and time range.<br>Try "Last Week" or a different category.`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function starIconSvg(filled) {
    return `<svg class="bookmark-icon" viewBox="0 0 24 24" fill="${filled ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.5 15 9l7 1-5 5 1.5 7-6.5-3.5L5 22l1.5-7-5-5 7-1 3.5-6.5z"/></svg>`;
}

function createArticleCard(article) {
    const publishedDate = article.published_date
        ? new Date(article.published_date).toLocaleString()
        : 'Date unknown';

    // Convert category name: split by underscore, capitalize each word, join with space
    const categoryLabel = article.category
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');

    const safeCategory = escapeHtml(article.category);
    const safeCategoryLabel = escapeHtml(categoryLabel);
    const safeTitle = escapeHtml(article.title);
    const safeLink = /^https?:\/\//i.test(article.link || '') ? escapeHtml(article.link) : '#';

    const summary = article.summary
        ? truncateText(article.summary, 200)
        : 'No summary available';
    const safeSummary = escapeHtml(summary);

    const sourceHost = extractHostname(article.source_url);
    const starred = article.is_bookmarked;

    const visitedMeta = article.visited_at
        ? `<span class="article-date">🕘 Read ${new Date(article.visited_at).toLocaleString()}</span>`
        : '';

    return `
        <div class="article-card" data-category="${safeCategory}">
            <div class="article-card-header">
                <span class="article-category">${safeCategoryLabel}</span>
                <button class="bookmark-btn ${starred ? 'bookmarked' : ''}"
                        onclick="toggleBookmark(${article.id}, this)"
                        title="${starred ? 'Remove bookmark' : 'Bookmark this article'}">
                    ${starIconSvg(starred)}
                </button>
            </div>
            <h2 class="article-title">
                <a href="${safeLink}" target="_blank" rel="noopener noreferrer" onclick="logHistory(${article.id})">
                    ${safeTitle}
                </a>
            </h2>
            <p class="article-summary">${safeSummary}</p>
            <div class="article-meta">
                <span class="article-source">📡 ${sourceHost}</span>
                <span class="article-date">🕒 ${publishedDate}</span>
                ${visitedMeta}
            </div>
        </div>
    `;
}

async function toggleBookmark(articleId, buttonEl) {
    const isBookmarked = buttonEl.classList.contains('bookmarked');
    try {
        const response = await fetch(`${API_BASE}/api/bookmarks/${articleId}`, {
            method: isBookmarked ? 'DELETE' : 'POST'
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        if (viewingBookmarks && isBookmarked) {
            // Removing from the bookmarks view - drop the card entirely
            allArticles = allArticles.filter(a => a.id !== articleId);
            filterAndDisplayArticles();
            return;
        }

        buttonEl.classList.toggle('bookmarked');
        buttonEl.innerHTML = starIconSvg(!isBookmarked);
        buttonEl.title = isBookmarked ? 'Bookmark this article' : 'Remove bookmark';

        const article = allArticles.find(a => a.id === articleId);
        if (article) article.is_bookmarked = !isBookmarked;
    } catch (error) {
        console.error('Error toggling bookmark:', error);
    }
}

function updateStats(count) {
    const countEl = document.getElementById('article-count');
    countEl.textContent = `${count} article${count !== 1 ? 's' : ''} found`;
    renderLastUpdated();
}

function refreshArticles() {
    loadArticles();
    loadCategoryCounts();
    loadLatestIngestion();
}

function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substr(0, maxLength) + '...';
}

function extractHostname(url) {
    try {
        const hostname = new URL(url).hostname;
        return hostname.replace('www.', '');
    } catch {
        return 'Unknown source';
    }
}

// Auto-refresh every 5 minutes
setInterval(() => {
    loadArticles();
}, 5 * 60 * 1000);
