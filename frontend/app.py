"""
WatchNext frontend (Streamlit).
Poster-first result cards powered by the backend API over HTTP only.
Never imports model/ and never invents posters, years, ratings or scores.
Run: streamlit run frontend/app.py
"""
from __future__ import annotations

import html
import os
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w342"
TMDB_IMAGE_BASE_2X = "https://image.tmdb.org/t/p/w500"

st.set_page_config(page_title="WatchNext", page_icon="🎬", layout="wide")

if "results" not in st.session_state:
    st.session_state.results = []
if "recommendations" not in st.session_state:
    st.session_state.recommendations = []
if "selected_movie" not in st.session_state:
    st.session_state.selected_movie = None
if "error" not in st.session_state:
    st.session_state.error = None
if "query" not in st.session_state:
    st.session_state.query = ""


def esc(value: Any) -> str:
    """Escape an API string for safe insertion into HTML attributes/text."""
    return html.escape("" if value is None else str(value), quote=True)


def poster_url(poster_path: Any) -> str | None:
    """Return the TMDB CDN URL for a poster path, or None when unavailable."""
    if not isinstance(poster_path, str):
        return None
    p = poster_path.strip()
    if not p.startswith("/"):
        return None
    return TMDB_IMAGE_BASE + p


def poster_srcset(poster_path: Any) -> str | None:
    """Return the 2x srcset for a poster path, or None."""
    if not isinstance(poster_path, str):
        return None
    p = poster_path.strip()
    if not p.startswith("/"):
        return None
    return TMDB_IMAGE_BASE_2X + p + " 2x"


def build_card(rank: int, movie: dict[str, Any]) -> str:
    """Build one poster-first result card as an HTML string."""
    title = esc(movie.get("title") or "Untitled")
    genres = movie.get("genres") or []
    overview = esc(movie.get("overview") or "")
    reason = esc(movie.get("reason") or "")
    score = movie.get("similarity_score")
    score_txt = f"{score:.2f}" if isinstance(score, (int, float)) else "n/a"
    poster_path = movie.get("poster_path")
    src = poster_url(poster_path) or ""
    srcset = poster_srcset(poster_path)

    pills = []
    for g in genres[:3]:
        pills.append(f'<span class="pill">{esc(g)}</span>')
    extra = len(genres) - 3
    if extra > 0:
        pills.append(f'<span class="pill">+{extra}</span>')
    genre_html = " ".join(pills)

    overview_full = esc(movie.get("overview") or "")
    overview_display = (overview_full[:160] + "…") if len(overview_full) > 160 else overview_full

    img_tag = ""
    if src:
        srcset_attr = f' srcset="{esc(srcset)}"' if srcset else ""
        img_tag = (
            f'<img src="{esc(src)}"{srcset_attr} alt="" '
            f'class="poster-img" loading="lazy">'
        )

    return f"""
    <div class="card">
      <div class="poster-box">
        <div class="placeholder">
          <span class="clapper">🎬</span>
          <div class="placereal">{title}</div>
        </div>
        {img_tag}
      </div>
      <div class="card-body">
        <div class="rank-title"><span class="rank">#{rank}</span> {title}</div>
        <div class="genres">{genre_html}</div>
        <div class="overview" title="{overview_full}">{overview_display}</div>
        <div class="reason"><span class="reason-label">Why this match:</span> {reason}</div>
        <div class="score">Similarity {score_txt}</div>
      </div>
    </div>
    """


def build_grid(recommendations: list[dict[str, Any]]) -> str:
    """Build the complete poster-first grid as ONE HTML string."""
    cards = "\n".join(build_card(i + 1, m) for i, m in enumerate(recommendations))
    return f"""
    <div class="movies-wrap">
      <style>
        .movies-wrap {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
        .movies-grid {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
          gap: 1.2rem;
          align-items: stretch;
        }}
        .card {{
          display: flex;
          flex-direction: column;
          height: 100%;
          border: 1px solid #e2e8f0;
          border-radius: 16px;
          background: #ffffff;
          overflow: hidden;
        }}
        .poster-box {{
          aspect-ratio: 2 / 3;
          overflow: hidden;
          position: relative;
          background: linear-gradient(135deg, #4b1d6e 0%, #6d28d9 100%);
          box-shadow: 0 4px 12px rgba(75, 29, 110, 0.18);
        }}
        .placeholder {{
          position: absolute;
          inset: 0;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          color: #ffffff;
          text-align: center;
          padding: 0.5rem;
          font-size: 0.75rem;
        }}
        .clapper {{ font-size: 2.2rem; margin-bottom: 0.35rem; }}
        .placereal {{ font-weight: 600; line-height: 1.2; }}
        .poster-img {{
          position: absolute;
          inset: 0;
          width: 100%;
          height: 100%;
          object-fit: cover;
          display: block;
        }}
        .card-body {{
          flex: 1;
          display: flex;
          flex-direction: column;
          padding: 0.9rem 0.85rem;
          gap: 0.5rem;
        }}
        .rank-title {{
          font-weight: 700;
          font-size: 0.95rem;
          line-height: 1.25;
          margin: 0;
          color: #0f172a;
        }}
        .rank {{ color: #6d28d9; font-weight: 800; }}
        .genres {{ display: flex; gap: 0.35rem; flex-wrap: wrap; }}
        .pill {{
          display: inline-block;
          font-size: 0.68rem;
          font-weight: 600;
          padding: 0.12rem 0.5rem;
          border-radius: 999px;
          background: #f1e7ff;
          color: #6d28d9;
          border: 1px solid #e9d7ff;
        }}
        .overview {{
          font-size: 0.78rem;
          line-height: 1.35;
          color: #334155;
          overflow: hidden;
          display: -webkit-box;
          -webkit-line-clamp: 3;
          -webkit-box-orient: vertical;
        }}
        .reason {{
          font-size: 0.78rem;
          color: #475569;
          margin-top: auto;
        }}
        .reason-label {{ font-weight: 700; color: #6d28d9; }}
        .score {{
          font-size: 0.78rem;
          font-weight: 700;
          color: #6d28d9;
          margin-top: auto;
          padding-top: 0.4rem;
          border-top: 1px solid #f1f5f9;
        }}
      </style>
      <div class="movies-grid">
        {cards}
      </div>
    </div>
    """



# --------------------------------------------------------------------------- #
# Brand: fixed, opaque-blur nav bar
# --------------------------------------------------------------------------- #
# NOTE: the CSS MUST be wrapped in a <style> element. Streamlit's markdown
# renders bare CSS as plain text instead of applying it, which silently
# disables the whole fixed-nav layout.
NAV_CSS = """
<style>
html { scroll-behavior: smooth; }
body { overflow-x: hidden; }
/* Fixed opaque-blur nav bar (never overlaps content) */
header.nav {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 64px;
  z-index: 900;
  background: rgba(9, 7, 17, 0.82);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(205, 173, 255, 0.14);
}
header.nav .nav-inner {
  max-width: 1420px;
  margin: 0 auto;
  height: 100%;
  padding: 0 1rem;
  display: flex;
  align-items: center;
  gap: 1rem;
}
/* Brand: single "WatchNext" word (Watch white, Next light purple) */
.brand {
  display: flex;
  align-items: center;
  gap: 0;
  text-decoration: none;
  color: #ffffff;
}
.brand-word {
  font-weight: 700;
  font-size: 1.12rem;
  letter-spacing: 0.5px;
}
.brand-next {
  /* #c084fc keeps >= 4.5:1 contrast on the dark translucent bar (WCAG AA) */
  color: #c084fc;
  font-weight: 800;
  font-size: 1.12rem;
  text-shadow: 0 0 18px rgba(168, 85, 247, 0.55);
}
.brand-sub {
  font-size: 0.52rem;
  color: #94a3b8;
  margin-left: 6px;
  letter-spacing: 2px;
  text-transform: uppercase;
}
.tag-pill {
  background: #7c3aed;
  color: #ffffff;
  font-size: 0.62rem;
  font-weight: 600;
  padding: 0.2rem 0.7rem;
  border-radius: 999px;
  white-space: nowrap;
}
.nav-links {
  display: flex;
  gap: 1rem;
  list-style: none;
  margin-left: auto;
}
.nav-links a {
  color: #dddddd;
  text-decoration: none;
  font-size: 0.82rem;
  padding-bottom: 0.15rem;
  border-bottom: 2px solid transparent;
  transition: color .15s ease, border-color .15s ease;
}
.nav-links a:hover {
  color: #f0e6ff;
  border-bottom-color: #a78bfa;
}
.nav-links a:focus-visible {
  outline: 2px solid #a78bfa;
  outline-offset: 2px;
}
/* Hero title block (fully visible below the fixed nav) */
.hero { padding: 0.75rem 0 1.25rem; }
.hero h1 {
  color: #0f172a;
  font-size: 2rem;
  margin: 0 0 0.35rem;
}
.hero .subtitle { color: #475569; font-size: 1.02rem; }
/* Page spacing: first section below the nav */
.block-container { padding-top: 88px !important; }
/* Anchor targets scroll clear of the fixed nav bar */
html { scroll-padding-top: 80px; }
#search, #results, #about {
  scroll-margin-top: 80px;
}
/* Mobile: shorter bar, tighter spacing, links stay reachable (no clipping) */
@media (max-width: 700px) {
  header.nav { height: 56px; }
  .nav-inner { gap: 0.6rem; padding: 0 0.75rem; }
  .brand-sub, .tag-pill { display: none; }
  .nav-links {
    gap: 0.65rem;
    overflow-x: auto;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
  }
  .nav-links::-webkit-scrollbar { display: none; }
  .nav-links a { font-size: 0.76rem; white-space: nowrap; }
}
/* Hide Streamlit's own header/toolbar/decoration/status so nothing overlaps
   the fixed nav bar. */
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 0; min-height: 0;
  visibility: hidden;
  overflow: hidden;
  z-index: 899;
}
</style>
"""


def build_nav() -> str:
    """One fixed, opaque-blur navigation bar (CSS + markup) rendered in a single
    st.markdown call so the bar and its styles are always served together."""
    # NB: join the three link strings as a LIST, not as adjacent f-strings,
    # otherwise " ".join() would iterate over the characters of one string.
    links = " ".join(
        [
            '<li><a href="#search">Search</a></li>',
            '<li><a href="#results">Results</a></li>',
            '<li><a href="#about">About</a></li>',
        ]
    )
    return NAV_CSS + f"""
<header role="banner" class="nav">
  <nav class="nav-inner" aria-label="Primary">
    <a class="brand" href="#search" aria-label="WatchNext home">
      <span class="brand-word brand-watch">Watch</span>
      <span class="brand-word brand-next">Next</span>
      <span class="brand-sub">AI MOVIE DISCOVERY</span>
    </a>
    <ul class="nav-links">
      {links}
    </ul>
    <div class="tag-pill">Find your next favorite movie</div>
  </nav>
</header>
"""


def build_hero() -> str:
    """One-screen hero + title block, below the fixed nav bar.

    The tagline + backend URL are rendered by the original Streamlit caption,
    so this block must not repeat them.
    """
    return """
<section class="hero">
  <div class="hero-inner">
    <h1 class="eyebrow">Less scrolling. More great stories.</h1>
    <p class="subtitle">Search a movie you already love and get similar picks, each with the reason it matched.</p>
  </div>
</section>
"""


def api_get(path: str, params: dict[str, Any] | None = None) -> tuple[int, dict | None, str | None]:
    """Call the backend API. Returns (status_code, json_body_or_None, error_message)."""
    try:
        resp = requests.get(f"{BACKEND_URL}{path}", params=params, timeout=15)
    except requests.RequestException as exc:
        return 0, None, f"Could not reach the backend at {BACKEND_URL}. Is it running? ({exc})"
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", {})
            return resp.status_code, None, detail.get("message", "Request failed.")
        except Exception:
            return resp.status_code, None, f"Request failed (HTTP {resp.status_code})."
    try:
        return resp.status_code, resp.json(), None
    except Exception:
        return resp.status_code, None, "Invalid response from backend."


def search_movies(query: str) -> tuple[list[dict], str | None]:
    status, body, err = api_get("/movies/search", {"q": query, "limit": 10})
    if err:
        return [], err
    return (body or {}).get("results", []), None


def recommend_movies(title: str, genre: str | None, year: int | None, top_n: int) -> tuple[list[dict], str | None]:
    params: dict[str, Any] = {"title": title, "top_n": top_n}
    if genre:
        params["genre"] = genre
    if year:
        params["year"] = year
    status, body, err = api_get("/recommend", params)
    if err:
        return [], err
    return (body or {}).get("recommendations", []), None


# --------------------------------------------------------------------------- #
# UI
# --------------------------------------------------------------------------- #
# Brand: fixed, opaque-blur nav bar (never overlaps content)
st.markdown(build_nav(), unsafe_allow_html=True)

# Hero title block (fully visible below the fixed nav)
st.markdown(build_hero(), unsafe_allow_html=True)

# Original Streamlit caption + backend URL (preserved existing behaviour)
st.caption("Find your next movie from a movie you already like. · Backend: " + BACKEND_URL)

st.session_state.error = None

# ---- Search ----
st.markdown('<div id="search">', unsafe_allow_html=True)
st.subheader("Search for a movie")
col_search, col_btn = st.columns([4, 1])
with col_search:
    search_query = st.text_input("Movie title", value=st.session_state.query, placeholder="e.g. Interstellar", label_visibility="collapsed")
with col_btn:
    search_clicked = st.button("Search", use_container_width=True)

if search_clicked and search_query.strip():
    st.session_state.query = search_query.strip()
    st.session_state.selected_movie = None
    st.session_state.recommendations = []
    results, err = search_movies(st.session_state.query)
    if err:
        st.session_state.error = err
    else:
        st.session_state.results = results

elif search_clicked and not search_query.strip():
    st.session_state.error = "Please enter a movie title."

# Show search results as a dropdown (dropdown priority)
if st.session_state.results:
    st.write(f"Found {len(st.session_state.results)} result(s):")
    options = ["Select a movie…"] + [f"{r.get('title')}" for r in st.session_state.results]
    pick = st.selectbox("Choose a movie", options, index=0, label_visibility="collapsed")
    if pick and pick != "Select a movie…":
        chosen = next((r for r in st.session_state.results if r.get("title") == pick), None)
        if chosen:
            st.session_state.selected_movie = chosen
st.markdown('</div>', unsafe_allow_html=True)

# ---- Errors / suggestions ----
if st.session_state.error:
    st.error(st.session_state.error)

# ---- Recommendations ----
st.markdown('<div id="results">', unsafe_allow_html=True)
if st.session_state.selected_movie:
    movie = st.session_state.selected_movie
    st.divider()
    st.subheader("Similar to “" + html.escape(movie.get("title") or "") + "”")

    col_g, col_y, col_n = st.columns([2, 1, 1])
    with col_g:
        genre_filter = st.text_input("Genre (optional)", placeholder="e.g. Action", label_visibility="collapsed")
    with col_y:
        year_filter = st.text_input("Year (optional)", placeholder="e.g. 2015", label_visibility="collapsed")
    with col_n:
        top_n_filter = st.number_input("Top N", min_value=1, max_value=20, value=5, step=1, label_visibility="collapsed")

    col_r, col_s = st.columns([2, 1])
    with col_r:
        rec_clicked = st.button("Find Similar Movies", use_container_width=True, type="primary")
    with col_s:
        surprise_clicked = st.button("Surprise Me", use_container_width=True)

    def _run_recommend(title: str, genre: str | None, year: int | None, top_n: int):
        year_int = None
        if year:
            try:
                year_int = int(year)
            except ValueError:
                st.session_state.error = "Year must be a number."
                return
        recs, err = recommend_movies(title, genre or None, year_int, int(top_n))
        if err:
            st.session_state.error = err
            st.session_state.recommendations = []
        else:
            st.session_state.recommendations = recs or []

    if rec_clicked:
        _run_recommend(movie.get("title"), genre_filter.strip() or None, year_filter.strip() or None, top_n_filter)
    if surprise_clicked:
        _run_recommend(movie.get("title"), None, None, 5)

    if st.session_state.error:
        st.error(st.session_state.error)

    if st.session_state.recommendations:
        st.markdown(build_grid(st.session_state.recommendations), unsafe_allow_html=True)
    elif st.session_state.selected_movie and not st.session_state.error:
        st.info("No recommendations found for this selection.")
st.markdown('</div>', unsafe_allow_html=True)

# ---- About / footer ----
st.markdown('<div id="about">', unsafe_allow_html=True)
st.divider()
st.markdown(
    """
    <div style="color:#64748b; font-size:0.8rem; text-align:center; padding:1rem 0;">
      Poster images courtesy of TMDB. This product uses TMDB data but is not endorsed or certified by TMDB.<br>
      Content-based TF-IDF + cosine similarity on the TMDB 5000 dataset · exact-year filter · no personalization · no API key.
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown('</div>', unsafe_allow_html=True)
