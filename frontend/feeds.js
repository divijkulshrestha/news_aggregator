const API_BASE = window.location.origin;

document.addEventListener('DOMContentLoaded', () => {
    loadThemePreference();
    loadFeeds();
    document.getElementById('add-feed-form').addEventListener('submit', handleAddFeed);
});

function loadThemePreference() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.body.setAttribute('data-theme', savedTheme);
}

async function loadFeeds() {
    const container = document.getElementById('feeds-table-container');
    try {
        const response = await fetch(`${API_BASE}/api/feeds`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const feeds = await response.json();
        renderFeeds(feeds);
    } catch (error) {
        container.innerHTML = `<div class="error">Failed to load feeds: ${error.message}</div>`;
    }
}

function renderFeeds(feeds) {
    const container = document.getElementById('feeds-table-container');

    if (feeds.length === 0) {
        container.innerHTML = '<div class="no-articles">No feeds configured yet.</div>';
        return;
    }

    const rows = feeds.map(feed => `
        <tr class="${feed.enabled ? '' : 'feed-disabled'}">
            <td>${escapeHtml(feed.category)}</td>
            <td class="feed-url" title="${escapeHtml(feed.url)}">${escapeHtml(feed.url)}</td>
            <td>
                <input type="checkbox" class="feed-toggle" ${feed.enabled ? 'checked' : ''}
                       onchange="toggleFeedEnabled(${feed.id}, this.checked)">
            </td>
            <td>
                <button class="feed-delete-btn" onclick="deleteFeed(${feed.id})">Delete</button>
            </td>
        </tr>
    `).join('');

    container.innerHTML = `
        <div class="feeds-table-scroll">
            <table class="feeds-table">
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>URL</th>
                        <th>Enabled</th>
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
        loadFeeds();
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
        loadFeeds();
    } catch (error) {
        console.error('Error toggling feed:', error);
        loadFeeds();
    }
}

async function deleteFeed(feedId) {
    if (!confirm('Delete this feed?')) return;
    try {
        const response = await fetch(`${API_BASE}/api/feeds/${feedId}`, { method: 'DELETE' });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        loadFeeds();
    } catch (error) {
        console.error('Error deleting feed:', error);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
