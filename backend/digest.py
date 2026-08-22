"""Weekly digest email content generation."""
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.database import Article


def get_digest_articles(
    db: Session,
    categories: Optional[List[str]] = None,
    days: int = 7,
    per_category: int = 5,
) -> dict:
    """Fetch the top articles per category from the last `days` days.

    Returns:
        Dict mapping category -> list of Article objects.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    query = db.query(Article).filter(Article.published_date >= cutoff)
    if categories:
        query = query.filter(Article.category.in_(categories))

    articles = query.order_by(Article.category, desc(Article.published_date)).all()

    grouped: dict = {}
    for article in articles:
        bucket = grouped.setdefault(article.category, [])
        if len(bucket) < per_category:
            bucket.append(article)

    return grouped


def render_digest_html(grouped_articles: dict) -> str:
    """Render the digest content as a simple HTML email body."""
    if not grouped_articles:
        return "<p>No articles found for this digest period.</p>"

    sections = []
    for category, articles in grouped_articles.items():
        label = category.replace("_", " ").title()
        items = "".join(
            f'<li style="margin-bottom: 10px;">'
            f'<a href="{a.link}" style="color: #2563eb; text-decoration: none; font-weight: 600;">{a.title}</a>'
            f'<br><span style="color: #64748b; font-size: 0.85em;">{a.summary[:150] if a.summary else ""}</span>'
            f"</li>"
            for a in articles
        )
        sections.append(
            f'<h3 style="color: #1e293b; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">{label}</h3>'
            f'<ul style="list-style: none; padding: 0;">{items}</ul>'
        )

    body = "".join(sections)
    return (
        '<div style="font-family: -apple-system, Arial, sans-serif; max-width: 640px; margin: 0 auto;">'
        '<h2 style="color: #1e293b;">📰 Your Weekly News Digest</h2>'
        f"{body}"
        "</div>"
    )


def render_digest_text(grouped_articles: dict) -> str:
    """Render the digest content as plain text (email fallback)."""
    if not grouped_articles:
        return "No articles found for this digest period."

    lines = ["Your Weekly News Digest", ""]
    for category, articles in grouped_articles.items():
        label = category.replace("_", " ").title()
        lines.append(f"== {label} ==")
        for a in articles:
            lines.append(f"- {a.title}\n  {a.link}")
        lines.append("")

    return "\n".join(lines)
