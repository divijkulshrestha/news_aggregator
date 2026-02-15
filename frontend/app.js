// API base URL - will work both locally and when deployed
const API_BASE = window.location.origin;

let currentCategory = 'top_stories';
let currentTimeRange = '1d';
let currentSearchQuery = '';
let allArticles = [];

// Initialize the page
document.addEventListener('DOMContentLoaded', () => {
    loadThemePreference();
    setupEventListeners();
    loadArticles();
});

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
    document.querySelectorAll('.category-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Update active state
            document.querySelectorAll('.category-btn').forEach(b => 
                b.classList.remove('active'));
            e.target.closest('.category-btn').classList.add('active');
            
            currentCategory = e.target.closest('.category-btn').dataset.category;
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

        // Always filter by current category (no 'all' option anymore)
        params.append('category', currentCategory);

        const response = await fetch(`${API_BASE}/api/articles?${params}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        allArticles = await response.json();
        filterAndDisplayArticles();
        
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
    
    // Convert category name: split by underscore, capitalize each word, join with space
    const categoryLabel = article.category
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
    
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
