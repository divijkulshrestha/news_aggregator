import pandas as pd
from pathlib import Path

from ingest_and_process import _clean_html, clean_dataframe, save_to_csv


def test_clean_html():
    raw = "<p>Hello &amp; <b>World</b>!</p>"
    assert _clean_html(raw) == "Hello & World !" or _clean_html(raw).startswith("Hello & World")


def test_clean_dataframe_and_save(tmp_path: Path):
    entries = [
        {
            "source_url": "https://example.com/feed",
            "title": "  Test Article  ",
            "link": "https://example.com/a",
            "published_raw": "2026-02-12T12:00:00Z",
            "summary": "<p>Summary</p>",
        },
        # duplicate link should be dropped
        {
            "source_url": "https://example.com/feed",
            "title": "Test Article",
            "link": "https://example.com/a",
            "published_raw": "2026-02-12T12:00:00Z",
            "summary": "Summary",
        },
        # missing link should be removed
        {
            "source_url": "https://example.com/feed",
            "title": "No Link",
            "link": "",
            "published_raw": "",
            "summary": "",
        },
    ]

    df = pd.DataFrame(entries)
    cleaned = clean_dataframe(df)
    # Expect only one unique article retained
    assert len(cleaned) == 1

    out_dir = save_to_csv(cleaned, output_base=tmp_path)
    assert (out_dir / "part-00000.csv").exists()
    assert (out_dir / "_SUCCESS").exists()
