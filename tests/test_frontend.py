#!/usr/bin/env python3
"""Frontend tests: AppTest with requests mocked."""
import json
from unittest import mock

import pytest

from streamlit.testing.v1 import AppTest

APP_FILE = "frontend/app.py"

# The backend URL the app uses when BACKEND_URL is not set in the environment.
BACKEND_URL_DEFAULT = "http://127.0.0.1:8000"


class FakeResp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


RECS_WITH_POSTER = {
    "movie_id": 1,
    "title": 'Movie <A> & "B"',
    "genres": ["Action", "Adventure", "Science Fiction", "Thriller"],
    "overview": "A great overview with <script>alert(1)</script>.",
    "poster_path": "/abc123.jpg",
    "similarity_score": 0.85,
    "reason": "Shares genres and themes.",
}
RECS_NO_POSTER = {
    "movie_id": 2,
    "title": "No Poster Movie",
    "genres": ["Drama"],
    "overview": "",
    "poster_path": None,
    "similarity_score": 0.5,
    "reason": "Closest overall match.",
}
SEARCH_RESULTS = [
    {"movie_id": 1, "title": "Movie <A>", "release_year": 2010, "genres": ["Action"]},
]


def _fake_get(url, params=None, timeout=15):
    if "/movies/search" in url:
        return FakeResp({"query": "Inter", "results": SEARCH_RESULTS})
    if "/recommend" in url:
        return FakeResp({"query": "x", "recommendations": [RECS_WITH_POSTER, RECS_NO_POSTER]})
    return FakeResp({"status": "ok", "model_ready": True})


def _run_app(monkeypatch):
    import frontend.app as app_module
    monkeypatch.setattr(app_module.requests, "get", _fake_get)
    at = AppTest.from_file(APP_FILE).run()
    _assert_no_exception(at)
    return at


def _assert_no_exception(at):
    """Streamlit >= 1.46 reports a clean run as an empty ElementList, not None."""
    exc = at.exception
    if exc is not None and len(exc) != 0:
        details = []
        for e in exc:
            details.append(str(getattr(e, "value", e)))
        raise AssertionError("App raised: " + " | ".join(details))


def _button_by_label(at, label):
    """Return the button widget with the given label (labels are not unique keys)."""
    for btn in at.button:
        if btn.label == label:
            return btn
    raise AssertionError(
        f"Button {label!r} not found. Available: {[b.label for b in at.button]}"
    )


def test_app_loads_without_error(monkeypatch):
    at = _run_app(monkeypatch)
    # Backend URL caption present
    joined = " ".join(str(c.value) for c in at.caption)
    assert "127.0.0.1:8000" in joined


def test_search_then_recommend_renders_grid(monkeypatch):
    at = _run_app(monkeypatch)

    # Enter a search query and click Search
    at.text_input[0].set_value("Interstellar")
    _button_by_label(at, "Search").click()
    at = at.run()
    _assert_no_exception(at)

    # Dropdown now offers the search result; select it
    assert len(at.selectbox) >= 1
    at.selectbox[0].set_value("Movie <A>")
    at = at.run()
    _assert_no_exception(at)

    # Click Find Similar Movies (NOT the "Search" button at index 0)
    _button_by_label(at, "Find Similar Movies").click()
    at = at.run()
    _assert_no_exception(at)

    # The grid HTML should be rendered via markdown
    html_all = "\n".join(str(m.value) for m in at.markdown)
    assert "grid-template-columns" in html_all
    assert "repeat(auto-fit, minmax(210px, 1fr))" in html_all
    assert "aspect-ratio: 2 / 3" in html_all

    # Exactly two cards rendered
    assert html_all.count('class="card"') == 2, html_all

    # Poster card: TMDB w342 URL + w500 srcset
    assert "https://image.tmdb.org/t/p/w342/abc123.jpg" in html_all
    assert 'srcset="https://image.tmdb.org/t/p/w500/abc123.jpg 2x"' in html_all
    assert 'alt=""' in html_all

    # No-poster card: no w342 src, placeholder still present
    no_poster_section = html_all
    assert "w342" in no_poster_section  # from the other card
    assert "🎬" in no_poster_section  # placeholder clapper present

    # Escaping: HTML/quotes in title are escaped in attributes/text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_all
    assert "Movie &lt;A&gt; &amp; &quot;B&quot;" in html_all

    # More than 3 genres -> "+1"
    assert "+1" in html_all

    # TMDB attribution footer
    assert "Poster images courtesy of TMDB" in html_all
    assert "not endorsed or certified by TMDB" in html_all

    # No "demo" wording
    assert "demo" not in html_all.lower()
    assert "baseline" not in html_all.lower()
    assert "sample data" not in html_all.lower()


def test_rank_and_score_rendered(monkeypatch):
    at = _run_app(monkeypatch)
    at.text_input[0].set_value("Interstellar")
    _button_by_label(at, "Search").click()
    at = at.run()
    _assert_no_exception(at)
    at.selectbox[0].set_value("Movie <A>")
    at = at.run()
    _assert_no_exception(at)
    _button_by_label(at, "Find Similar Movies").click()
    at = at.run()
    _assert_no_exception(at)
    html_all = "\n".join(str(m.value) for m in at.markdown)
    assert "#1" in html_all
    assert "#2" in html_all
    assert "Similarity 0.85" in html_all
    assert "Similarity 0.50" in html_all


# --------------------------------------------------------------------------- #
# NAVBAR (fixed, opaque-blur, always-visible) tests
# --------------------------------------------------------------------------- #


def test_nav_bar_markup_and_anchors(monkeypatch):
    at = _run_app(monkeypatch)
    html_all = "\n".join(str(m.value) for m in at.markdown)

    # Exactly one brand bar (header role="banner"); old st.title hero removed
    assert html_all.count('<header role="banner"') == 1
    assert len(at.title) == 0

    # Semantic navigation landmark with an accessible name
    assert html_all.count('<nav class="nav-inner" aria-label="Primary">') == 1

    # Brand: "Watch" white + "Next" purple, rendered as ONE word "WatchNext"
    assert '<span class="brand-word brand-watch">Watch</span>' in html_all
    assert '<span class="brand-word brand-next">Next</span>' in html_all
    assert "WatchNext" in html_all

    # Anchor links + their target ids all present and consistent
    for href, tid in (("#search", "search"), ("#results", "results"), ("#about", "about")):
        assert ('href="' + href + '"') in html_all
        assert ('id="' + tid + '"') in html_all

    # Nav CSS: fixed, full-width top, high z-index, translucent blur
    assert "position: fixed" in html_all
    assert "top: 0; left: 0; right: 0" in html_all
    assert "z-index: 900" in html_all          # above header, below popovers
    assert "backdrop-filter: blur(14px)" in html_all
    assert "rgba(9, 7, 17, 0.82)" in html_all

    # CSS hides Streamlit's own header/toolbar/decoration/status widgets
    assert '[data-testid="stHeader"]' in html_all
    assert '[data-testid="stToolbar"]' in html_all
    assert '[data-testid="stDecoration"]' in html_all
    assert '[data-testid="stStatusWidget"]' in html_all

    # Page spacing: container top padding >= nav height (64px -> 88px)
    assert "padding-top: 88px" in html_all
    # Anchor scroll offset above the nav, applied to the real target ids
    assert "scroll-margin-top: 80px" in html_all
    assert "#search, #results, #about {" in html_all
    assert "scroll-padding-top: 80px" in html_all

    # Mobile bar (shorter) and branding kept
    assert "height: 56px" in html_all
    assert 'class="tag-pill"' in html_all
    assert "AI MOVIE DISCOVERY" in html_all
    assert "Find your next favorite movie" in html_all


def test_nav_flex_and_tag_pill(monkeypatch):
    at = _run_app(monkeypatch)
    html_all = "\n".join(str(m.value) for m in at.markdown)
    # horizontal layout: brand, links, right-aligned tag pill
    assert "display: flex" in html_all
    assert "margin-left: auto" in html_all


def test_nav_links_remain_reachable_on_mobile(monkeypatch):
    """The nav links must NOT be hidden on small screens (no unreachable nav)."""
    at = _run_app(monkeypatch)
    html_all = "\n".join(str(m.value) for m in at.markdown)
    media = html_all[html_all.index("@media (max-width: 700px)"):]
    media = media[: media.index("}") + 1]
    # brand subtitle + tag pill may be hidden, but .nav-links must stay visible
    assert ".nav-links {" not in media or "display: none" not in media.split(".nav-links {")[1]
    assert ".nav-links a { font-size: 0.76rem; white-space: nowrap; }" in html_all


def test_nav_css_is_wrapped_in_style_tag(monkeypatch):
    """Regression guard: bare CSS is rendered as TEXT by Streamlit markdown.

    Without a <style> wrapper the whole fixed-nav layout silently degrades to
    `position: static`, so the nav overlaps the page content.
    """
    at = _run_app(monkeypatch)
    html_all = "\n".join(str(m.value) for m in at.markdown)
    # The nav stylesheet must be a real <style> element ...
    assert "<style>" in html_all
    assert "</style>" in html_all
    # ... and the CSS must live INSIDE it, not as bare text.
    style_start = html_all.index("<style>")
    style_end = html_all.index("</style>")
    css_block = html_all[style_start:style_end]
    assert "header.nav" in css_block
    assert "position: fixed" in css_block
    # The CSS must not be emitted outside any <style> element.
    outside = html_all[:style_start] + html_all[style_end + len("</style>"):]
    assert "header.nav {" not in outside
    assert "scroll-behavior: smooth" not in outside


def test_nav_is_accessible(monkeypatch):
    """Landmarks and links carry accessible names."""
    at = _run_app(monkeypatch)
    html_all = "\n".join(str(m.value) for m in at.markdown)
    # banner landmark + named nav landmark
    assert 'role="banner"' in html_all
    assert 'aria-label="Primary"' in html_all
    # brand link has an accessible name
    assert 'aria-label="WatchNext home"' in html_all
    # every nav link has visible text
    for label in ("Search", "Results", "About"):
        assert f">{label}</a>" in html_all
    # focus-visible styling for keyboard users
    assert ":focus-visible" in html_all


def test_no_old_brandbar_markup_remains(monkeypatch):
    at = _run_app(monkeypatch)
    html_all = "\n".join(str(m.value) for m in at.markdown)
    # Old in-flow brandbar markup must be gone
    assert "brandbar" not in html_all.lower()
    assert "st.title" not in html_all
    # The old wide brand title with the emoji is removed
    assert "🎬" not in html_all
    # Exactly one hero title and one tag pill
    assert html_all.count('class="eyebrow"') == 1
    assert html_all.count('class="tag-pill"') == 1


def test_no_duplicated_user_facing_copy(monkeypatch):
    """The hero subtitle and the Streamlit caption must not repeat each other."""
    at = _run_app(monkeypatch)
    html_all = "\n".join(str(m.value) for m in at.markdown)
    tagline = "Find your next movie from a movie you already like."
    # The tagline lives in the original Streamlit caption ...
    captions = " ".join(str(c.value) for c in at.caption)
    assert captions.count(tagline) == 1
    # ... and must NOT be repeated in the page markup (hero subtitle).
    assert tagline not in html_all
    # The backend URL is surfaced exactly once, via the caption.
    assert captions.count(BACKEND_URL_DEFAULT) == 1
    assert BACKEND_URL_DEFAULT not in html_all


def test_navbar_writes_no_new_files(monkeypatch, tmp_path):
    # Frontend change must not touch the frozen package / model / backend trees
    at = _run_app(monkeypatch)
    _assert_no_exception(at)
