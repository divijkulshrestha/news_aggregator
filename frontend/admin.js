const API_BASE = window.location.origin;

const CATEGORY_COLORS = {
    top_stories: '#dc2626',
    india: '#f97316',
    world: '#2563eb',
    business_finance: '#16a34a',
    science_history: '#8b5cf6',
    technology: '#7c3aed',
    company_blogs: '#0891b2',
    cricket: '#059669',
};
const FALLBACK_COLORS = ['#e11d48', '#0284c7', '#65a30d', '#d97706', '#9333ea', '#0d9488'];
const PAPER_GRAYS = ['#1a1a1a', '#4a4a4a', '#7a7a7a', '#2e2e2e', '#5e5e5e', '#8e8e8e', '#3a3a3a', '#6a6a6a'];

let feedsCache = [];
let healthCache = [];
let trendsDays = 30;

document.addEventListener('DOMContentLoaded', () => {
    loadThemePreference();
    loadOverview();
    loadFeedsAndHealth();
    loadTrends();
    document.getElementById('add-feed-form').addEventListener('submit', handleAddFeed);
    document.querySelectorAll('.trends-range-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.trends-range-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            trendsDays = parseInt(btn.dataset.days, 10);
            loadTrends();
        });
    });
});

function loadThemePreference() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.body.setAttribute('data-theme', savedTheme);
}

async function loadOverview() {
    try {
        const response = await fetch(`${API_BASE}/api/admin/stats/overview`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const stats = await response.json();
        renderOverview(stats);
    } catch (error) {
        document.getElementById('stat-total-articles').textContent = '—';
        console.error('Error loading overview stats:', error);
    }
}

function renderOverview(stats) {
    document.getElementById('stat-total-articles').textContent = stats.total_articles;
    document.getElementById('stat-articles-today').textContent = stats.articles_today;
    document.getElementById('stat-last-run').textContent = stats.last_successful_run
        ? new Date(stats.last_successful_run + 'Z').toLocaleString()
        : 'Never';
}

function categoryColor(category, index) {
    if (document.body.getAttribute('data-theme') === 'paper') {
        return PAPER_GRAYS[index % PAPER_GRAYS.length];
    }
    return CATEGORY_COLORS[category] || FALLBACK_COLORS[index % FALLBACK_COLORS.length];
}

async function loadTrends() {
    const container = document.getElementById('trends-chart-container');
    try {
        const response = await fetch(`${API_BASE}/api/admin/stats/trends?days=${trendsDays}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const trends = await response.json();
        renderTrendsChart(trends);
    } catch (error) {
        container.innerHTML = `<div class="error">Failed to load trends: ${error.message}</div>`;
    }
}

function renderTrendsChart(trends) {
    const container = document.getElementById('trends-chart-container');
    const categories = Object.keys(trends.series);

    if (categories.length === 0 || trends.dates.length === 0) {
        container.innerHTML = '<div class="no-articles">No ingestion data yet.</div>';
        return;
    }

    const width = 800;
    const height = 260;
    const paddingLeft = 40;
    const paddingBottom = 24;
    const paddingTop = 12;
    const plotWidth = width - paddingLeft - 10;
    const plotHeight = height - paddingTop - paddingBottom;

    const maxValue = Math.max(1, ...categories.map(cat => Math.max(...trends.series[cat])));
    const numPoints = trends.dates.length;

    const xForIndex = (i) => paddingLeft + (numPoints === 1 ? 0 : (i / (numPoints - 1)) * plotWidth);
    const yForValue = (v) => paddingTop + plotHeight - (v / maxValue) * plotHeight;

    const gridLines = [0, 0.25, 0.5, 0.75, 1].map(fraction => {
        const y = paddingTop + plotHeight - fraction * plotHeight;
        const label = Math.round(fraction * maxValue);
        return `
            <line x1="${paddingLeft}" y1="${y}" x2="${width - 10}" y2="${y}" class="trends-gridline" />
            <text x="${paddingLeft - 8}" y="${y + 4}" class="trends-axis-label" text-anchor="end">${label}</text>
        `;
    }).join('');

    const dateLabelStep = Math.max(1, Math.ceil(numPoints / 6));
    const dateLabels = trends.dates.map((date, i) => {
        if (i % dateLabelStep !== 0 && i !== numPoints - 1) return '';
        const short = date.slice(5); // MM-DD
        return `<text x="${xForIndex(i)}" y="${height - 4}" class="trends-axis-label" text-anchor="middle">${short}</text>`;
    }).join('');

    const lines = categories.map((category, idx) => {
        const color = categoryColor(category, idx);
        const points = trends.series[category]
            .map((value, i) => `${xForIndex(i)},${yForValue(value)}`)
            .join(' ');
        return `<polyline points="${points}" fill="none" stroke="${color}" stroke-width="2" />`;
    }).join('');

    const legend = categories.map((category, idx) => `
        <div class="trends-legend-item">
            <span class="trends-legend-swatch" style="background:${categoryColor(category, idx)}"></span>
            <span>${escapeHtml(category)}</span>
        </div>
    `).join('');

    container.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" class="trends-svg" preserveAspectRatio="xMidYMid meet">
            ${gridLines}
            ${lines}
            ${dateLabels}
        </svg>
        <div class="trends-legend">${legend}</div>
    `;
}

async function loadFeedsAndHealth() {
    const container = document.getElementById('feeds-table-container');
    try {
        const [feedsResponse, healthResponse] = await Promise.all([
            fetch(`${API_BASE}/api/feeds`),
            fetch(`${API_BASE}/api/admin/feeds/health`)
        ]);
        if (!feedsResponse.ok) throw new Error(`HTTP error! status: ${feedsResponse.status}`);
        if (!healthResponse.ok) throw new Error(`HTTP error! status: ${healthResponse.status}`);

        feedsCache = await feedsResponse.json();
        healthCache = await healthResponse.json();

        renderFeeds(feedsCache, healthCache);
        renderFeedSummary(feedsCache, healthCache);
    } catch (error) {
        container.innerHTML = `<div class="error">Failed to load feeds: ${error.message}</div>`;
    }
}

function renderFeedSummary(feeds, health) {
    const activeFeeds = feeds.filter(f => f.enabled).length;
    const failingFeeds = health.filter(h => h.enabled && h.last_run_success === false).length;

    document.getElementById('stat-active-feeds').textContent = activeFeeds;
    const failingEl = document.getElementById('stat-feeds-failing');
    failingEl.textContent = failingFeeds;
    failingEl.classList.toggle('value-warning', failingFeeds > 0);
}

function renderFeeds(feeds, health) {
    const container = document.getElementById('feeds-table-container');

    if (feeds.length === 0) {
        container.innerHTML = '<div class="no-articles">No feeds configured yet.</div>';
        return;
    }

    const healthById = new Map(health.map(h => [h.id, h]));

    const rows = feeds.map(feed => {
        const h = healthById.get(feed.id);
        const statusIcon = !h || h.last_run_success === null ? '—' : (h.last_run_success ? '✅' : '❌');
        const lastRun = h && h.last_run_at ? new Date(h.last_run_at + 'Z').toLocaleString() : 'Never';
        const failures = h ? h.consecutive_failures : 0;
        const failuresClass = failures >= 3 ? 'feed-health-failures value-warning' : 'feed-health-failures';
        const successRate = h && h.success_rate !== null && h.success_rate !== undefined
            ? `${Math.round(h.success_rate * 100)}%`
            : '—';

        return `
        <tr class="${feed.enabled ? '' : 'feed-disabled'}">
            <td>${escapeHtml(feed.category)}</td>
            <td class="feed-url" title="${escapeHtml(feed.url)}">${escapeHtml(feed.url)}</td>
            <td>
                <input type="checkbox" class="feed-toggle" ${feed.enabled ? 'checked' : ''}
                       onchange="toggleFeedEnabled(${feed.id}, this.checked)">
            </td>
            <td class="feed-health-status" title="Last run: ${lastRun}">${statusIcon}</td>
            <td class="${failuresClass}">${failures}</td>
            <td>${successRate}</td>
            <td>
                <button class="feed-delete-btn" onclick="deleteFeed(${feed.id})">Delete</button>
            </td>
        </tr>
    `;
    }).join('');

    container.innerHTML = `
        <div class="feeds-table-scroll">
            <table class="feeds-table">
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>URL</th>
                        <th>Enabled</th>
                        <th>Last Run</th>
                        <th>Consec. Failures</th>
                        <th>Success Rate</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
}

async function handleAddFeed(e) {
    e.preventDefault();
    const category = document.getElementById('new-category').value.trim();
    const url = document.getElementById('new-url').value.trim();
    const errorEl = document.getElementById('add-feed-error');
    errorEl.textContent = '';

    try {
        const response = await fetch(`${API_BASE}/api/feeds`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category, url })
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP error! status: ${response.status}`);
        }

        document.getElementById('new-category').value = '';
        document.getElementById('new-url').value = '';
        loadFeedsAndHealth();
    } catch (error) {
        errorEl.textContent = error.message;
    }
}

async function toggleFeedEnabled(feedId, enabled) {
    try {
        const response = await fetch(`${API_BASE}/api/feeds/${feedId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        loadFeedsAndHealth();
    } catch (error) {
        console.error('Error toggling feed:', error);
        loadFeedsAndHealth();
    }
}

async function deleteFeed(feedId) {
    if (!confirm('Delete this feed?')) return;
    try {
        const response = await fetch(`${API_BASE}/api/feeds/${feedId}`, { method: 'DELETE' });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        loadFeedsAndHealth();
    } catch (error) {
        console.error('Error deleting feed:', error);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
