// API base URL - will work both locally and when deployed
const API_BASE = window.location.origin;

let currentCategory = 'all';
let currentTimeRange = '1d';

// Initialize the page
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadArticles();
});

function setupEventListeners() {
    // Category filters
    document.querySelectorAll('.filter-btn[data-category]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Update active state
            document.querySelectorAll('.filter-btn[data-category]').forEach(b => 
                b.classList.remove('active'));
            e.target.classList.add('active');
            
            currentCategory = e.target.dataset.category;
            loadArticles();
        });
    });

    // Time range filters
    document.querySelectorAll('.time-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Update active state
            document.querySelectorAll('.time-btn').forEach(b => 
                b.classList.remove('active'));
            e.target.classList.add('active');
            
            currentTimeRange = e.target.dataset.time;
            loadArticles();
        });
    });
}

async function loadArticles() {
    const container = document.getElementById('articles-container');
    container.innerHTML = '<div class="loading">Loading articles...</div>';

    try {
        // Build query parameters
        const params = new URLSearchParams({
            time_range: currentTimeRange,
            limit: 100
        });

        if (currentCategory !== 'all') {
            params.append('category', currentCategory);
        }

        const response = await fetch(`${API_BASE}/api/articles?${params}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const articles = await response.json();
        displayArticles(articles);
        
        // Update stats
        updateStats(articles.length);
        
    } catch (error) {
        console.error('Error loading articles:', error);
        container.innerHTML = `
            <div class="error">
                Failed to load articles. Please check if the backend is running.
                <br><small>${error.message}</small>
            </div>
        `;
    }
}

function displayArticles(articles) {
    const container = document.getElementById('articles-container');
    
    if (articles.length === 0) {
        container.innerHTML = `
            <div class="no-articles">
                No articles found for the selected filters.
                <br>Try adjusting your time range or category.
            </div>
        `;
        return;
    }

    container.innerHTML = articles.map(article => createArticleCard(article)).join('');
}

function createArticleCard(article) {
    const publishedDate = article.published_date 
        ? new Date(article.published_date).toLocaleString()
        : 'Date unknown';
    
    const categoryLabel = article.category.replace('_', ' ');
    const summary = article.summary 
        ? truncateText(article.summary, 200)
        : 'No summary available';
    
    const sourceHost = extractHostname(article.source_url);

    return `
        <div class="article-card" data-category="${article.category}">
            <span class="article-category">${categoryLabel}</span>
            <h2 class="article-title">
                <a href="${article.link}" target="_blank" rel="noopener noreferrer">
                    ${article.title}
                </a>
            </h2>
            <p class="article-summary">${summary}</p>
            <div class="article-meta">
                <span class="article-source">📡 ${sourceHost}</span>
                <span class="article-date">🕒 ${publishedDate}</span>
            </div>
        </div>
    `;
}

function updateStats(count) {
    const countEl = document.getElementById('article-count');
    const updateEl = document.getElementById('last-update');
    
    countEl.textContent = `${count} article${count !== 1 ? 's' : ''} found`;
    updateEl.textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
}

function refreshArticles() {
    loadArticles();
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
