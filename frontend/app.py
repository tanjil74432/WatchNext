import random
import re
from difflib import get_close_matches

import streamlit as st

st.set_page_config(
    page_title="WatchNext | AI Movie Discovery",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------
# Demo catalog. Replace this list with cleaned TMDB CSV data / your API.
# Poster URLs are optional; cards gracefully show a placeholder on error.
# ---------------------------------------------------------------------
MOVIES = [
    {
        "title": "Interstellar", "year": 2014, "rating": 8.7,
        "genres": ["Sci-Fi", "Drama", "Adventure"],
        "overview": "A team of explorers travels beyond this galaxy to discover whether mankind has a future among the stars.",
        "keywords": ["space", "time", "survival", "family", "wormhole", "science"],
        "poster": "https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6Mxe7GJ2w.jpg",
    },
    {
        "title": "The Martian", "year": 2015, "rating": 8.0,
        "genres": ["Sci-Fi", "Adventure"],
        "overview": "Stranded on Mars, an astronaut uses science and ingenuity to survive while Earth races to bring him home.",
        "keywords": ["space", "mars", "survival", "science", "astronaut"],
        "poster": "https://image.tmdb.org/t/p/w500/5aGhaIH3OnhX4CfewX6b9YQnLY7.jpg",
    },
    {
        "title": "Inception", "year": 2010, "rating": 8.8,
        "genres": ["Sci-Fi", "Thriller", "Action"],
        "overview": "A skilled thief enters dreams to steal secrets, then faces an impossible task: planting an idea.",
        "keywords": ["dreams", "mind", "time", "heist", "reality", "science"],
        "poster": "https://image.tmdb.org/t/p/w500/oYuLEt3zVCKq57qu2F8dT7NIa6f.jpg",
    },
    {
        "title": "Arrival", "year": 2016, "rating": 7.9,
        "genres": ["Sci-Fi", "Drama", "Mystery"],
        "overview": "A linguist works with the military to communicate with mysterious spacecraft that have arrived on Earth.",
        "keywords": ["aliens", "language", "space", "time", "humanity", "science"],
        "poster": "https://image.tmdb.org/t/p/w500/x2FJsf1ElAgr63Y3PNPtJrcmpoe.jpg",
    },
    {
        "title": "Blade Runner 2049", "year": 2017, "rating": 8.0,
        "genres": ["Sci-Fi", "Thriller", "Drama"],
        "overview": "A young blade runner uncovers a secret that could reshape what remains of society.",
        "keywords": ["future", "android", "identity", "humanity", "dystopia", "technology"],
        "poster": "https://image.tmdb.org/t/p/w500/gajva2L0rPYkEWjzgFlBXCAVBE5.jpg",
    },
    {
        "title": "Dune: Part Two", "year": 2024, "rating": 8.5,
        "genres": ["Sci-Fi", "Adventure", "Drama"],
        "overview": "Paul Atreides unites with Chani and the Fremen while seeking justice against those who destroyed his family.",
        "keywords": ["desert", "destiny", "politics", "war", "epic", "future"],
        "poster": "https://image.tmdb.org/t/p/w500/1pdfLvkbY9ohJlCjQH2CZjjYVvJ.jpg",
    },
    {
        "title": "The Dark Knight", "year": 2008, "rating": 9.0,
        "genres": ["Action", "Crime", "Drama"],
        "overview": "Batman faces the Joker, a criminal mastermind who plunges Gotham into chaos.",
        "keywords": ["hero", "crime", "justice", "chaos", "city", "villain"],
        "poster": "https://image.tmdb.org/t/p/w500/qJ2tW6WMUDux911r6m7haRef0WH.jpg",
    },
    {
        "title": "Oppenheimer", "year": 2023, "rating": 8.3,
        "genres": ["Drama", "History", "Thriller"],
        "overview": "The story of J. Robert Oppenheimer and his role in the development of the atomic bomb.",
        "keywords": ["science", "history", "war", "scientist", "politics", "biography"],
        "poster": "https://image.tmdb.org/t/p/w500/ptpr0kGAckfQkJeJIt8st5dglvd.jpg",
    },
    {
        "title": "Everything Everywhere All at Once", "year": 2022, "rating": 7.8,
        "genres": ["Sci-Fi", "Comedy", "Action"],
        "overview": "An exhausted laundromat owner becomes the unlikely hero of a wild multiverse-spanning adventure.",
        "keywords": ["multiverse", "family", "identity", "parallel worlds", "comedy", "action"],
        "poster": "https://image.tmdb.org/t/p/w500/w3LxiVYdWWRvEVdn5RYq6jIqkb1.jpg",
    },
    {
        "title": "The Shawshank Redemption", "year": 1994, "rating": 9.3,
        "genres": ["Drama", "Crime"],
        "overview": "Two imprisoned men build a lasting friendship and find hope through years of hardship.",
        "keywords": ["friendship", "hope", "prison", "freedom", "justice"],
        "poster": "https://image.tmdb.org/t/p/w500/9cqNxx0GxF0bflZmeSMuL5tnGzr.jpg",
    },
    {
        "title": "Spider-Man: Across the Spider-Verse", "year": 2023, "rating": 8.6,
        "genres": ["Animation", "Action", "Adventure"],
        "overview": "Miles Morales travels across the multiverse and meets a team of Spider-People protecting its existence.",
        "keywords": ["multiverse", "hero", "parallel worlds", "family", "action"],
        "poster": "https://image.tmdb.org/t/p/w500/8Vt6mWEReuy4Of61Lnj5Xj704m8.jpg",
    },
    {
        "title": "The Grand Budapest Hotel", "year": 2014, "rating": 8.1,
        "genres": ["Comedy", "Drama", "Adventure"],
        "overview": "A legendary concierge and his young protégé become tangled in a theft and a family inheritance battle.",
        "keywords": ["friendship", "mystery", "hotel", "comedy", "adventure"],
        "poster": "https://image.tmdb.org/t/p/w500/eWdyYQreja6JGCzqHWXpWHDrrPo.jpg",
    },
    {
        "title": "The Conjuring", "year": 2013, "rating": 7.5,
        "genres": ["Horror", "Mystery", "Thriller"],
        "overview": "Paranormal investigators help a family terrorized by a dark presence in their farmhouse.",
        "keywords": ["haunted", "ghost", "family", "mystery", "supernatural"],
        "poster": "https://image.tmdb.org/t/p/w500/wVYREutTvI2tmxr6ujrHT704wGF.jpg",
    },
    {
        "title": "La La Land", "year": 2016, "rating": 8.0,
        "genres": ["Romance", "Drama", "Music"],
        "overview": "A jazz musician and an aspiring actress fall in love while pursuing their dreams in Los Angeles.",
        "keywords": ["love", "dreams", "music", "ambition", "romance"],
        "poster": "https://image.tmdb.org/t/p/w500/uDO8zWDhfWwoFdKS4fzkUJt0Rf0.jpg",
    },
    {
        "title": "Mad Max: Fury Road", "year": 2015, "rating": 8.1,
        "genres": ["Action", "Adventure", "Sci-Fi"],
        "overview": "In a brutal wasteland, a drifter joins a rebel warrior in a high-speed escape from a tyrant.",
        "keywords": ["survival", "future", "chase", "desert", "action", "dystopia"],
        "poster": "https://image.tmdb.org/t/p/w500/8tZYtuWezp8JbcsvHYO0O46tFbo.jpg",
    },
    {
        "title": "Coco", "year": 2017, "rating": 8.4,
        "genres": ["Animation", "Family", "Fantasy"],
        "overview": "A young musician journeys to the Land of the Dead to uncover his family's history.",
        "keywords": ["family", "music", "memory", "adventure", "fantasy"],
        "poster": "https://image.tmdb.org/t/p/w500/gGEsBPAijhVUFoiNpgZXqRVWJt2.jpg",
    },
]

GENRES = sorted({g for movie in MOVIES for g in movie["genres"]})
YEARS = sorted({movie["year"] for movie in MOVIES}, reverse=True)

# Custom CSS: responsive cards, purple neon highlights, cinematic background.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
:root { --bg:#090711; --panel:#131020; --purple:#a855f7; --lav:#d5a8ff; --muted:#aaa0bc; }
html, body, [data-testid="stAppViewContainer"] { background:var(--bg); color:#f8f5ff; font-family:'DM Sans',sans-serif; }
[data-testid="stHeader"] { background:rgba(9,7,17,.88); }
[data-testid="stAppViewContainer"] > .main { background:radial-gradient(ellipse at 80% 0%,rgba(113,48,173,.15),transparent 35%),var(--bg); }
.block-container { max-width:1420px; padding-top:1.1rem; padding-bottom:3rem; }
h1,h2,h3 { font-family:'Space Grotesk',sans-serif !important; letter-spacing:-.04em; color:#fff; }
a { color:#d5a8ff !important; }
.brandbar { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.35rem 0 1rem; border-bottom:1px solid rgba(205,173,255,.14); margin-bottom:1.3rem; }
.brand { display:flex; align-items:baseline; flex-wrap:wrap; gap:.55rem; min-width:0; font-family:'Space Grotesk',sans-serif; font-size:1.55rem; font-weight:700; letter-spacing:-.06em; line-height:1.4; }
.brand-name-accent { color:#c084fc; text-shadow:0 0 20px rgba(168,85,247,.5); }
.brand-subtitle { display:inline-block; color:#a99eb8; font-family:'DM Sans',sans-serif; font-size:.65rem; font-weight:500; letter-spacing:0; white-space:normal; }
.brand-tag { display:inline-flex; align-items:center; justify-content:center; flex-shrink:0; max-width:100%; box-sizing:border-box; font-size:.72rem; line-height:1.45; color:#e3d6f3; border:1px solid rgba(192,132,252,.3); background:rgba(168,85,247,.08); padding:.55rem .85rem; border-radius:99px; white-space:normal; text-align:center; }
.hero { position:relative; overflow:hidden; border:1px solid rgba(196,148,255,.22); border-radius:22px; padding:clamp(1.4rem,4vw,3.4rem); margin-bottom:1.7rem;
background:linear-gradient(100deg,rgba(12,9,22,.98) 0%,rgba(17,10,30,.93) 53%,rgba(39,16,62,.67) 100%),radial-gradient(circle at 83% 35%,rgba(168,85,247,.5),transparent 36%); box-shadow:0 18px 70px rgba(0,0,0,.18); }
.hero:after { content:"✦"; position:absolute; right:8%; top:3%; font-size:clamp(7rem,20vw,16rem); line-height:1; color:rgba(196,132,252,.08); pointer-events:none; }
.eyebrow { color:#c084fc; text-transform:uppercase; letter-spacing:.18em; font-size:.68rem; font-weight:700; }
.hero h1 { font-size:clamp(2.3rem,5vw,4.4rem); line-height:1.02; margin:.7rem 0 1rem; max-width:800px; }
.hero h1 span { color:#c084fc; }
.hero p { color:#c6bdd5; max-width:610px; font-size:1rem; line-height:1.75; }
.stat-row { display:flex; gap:2rem; flex-wrap:wrap; margin-top:1.5rem; }
.stat { border-left:2px solid #a855f7; padding-left:.75rem; }
.stat strong { display:block; font-size:1.15rem; color:#fff; }
.stat small { color:#a99eb8; font-size:.72rem; }
.panel { background:linear-gradient(145deg,rgba(25,19,40,.94),rgba(14,11,24,.96)); border:1px solid rgba(201,163,255,.16); border-radius:16px; padding:1rem; height:100%; }
.panel-title { font-family:'Space Grotesk',sans-serif; font-size:1.1rem; font-weight:700; margin-bottom:.25rem; }
.panel-subtitle { color:#a99eb8; font-size:.8rem; margin-bottom:1rem; }
.section-head { display:flex; align-items:end; justify-content:space-between; gap:1rem; margin:1.8rem 0 1rem; }
.section-head h2 { margin:0; font-size:1.55rem; }
.section-head p { margin:.3rem 0 0; color:#a99eb8; font-size:.82rem; }
div[data-testid="stTextInput"] input, div[data-testid="stSelectbox"] div[data-baseweb="select"] > div, div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div { background:#0d0a17 !important; color:#f8f5ff !important; border-color:rgba(197,156,255,.28) !important; border-radius:10px !important; }
div[data-testid="stTextInput"] input:focus { box-shadow:0 0 0 1px #a855f7 !important; }
.stButton > button { border-radius:10px; border:1px solid rgba(192,132,252,.35); background:linear-gradient(110deg,#963ee5,#7131c9); color:white; font-weight:700; min-height:2.65rem; transition:all .15s ease; }
.stButton > button:hover { border-color:#d4a4ff; box-shadow:0 0 22px rgba(168,85,247,.25); color:#fff; transform:translateY(-1px); }
.stButton > button[kind="secondary"] { background:rgba(255,255,255,.035); border-color:rgba(201,163,255,.2); color:#e9ddf7; }
.movie-card { overflow:hidden; height:100%; border:1px solid rgba(200,165,255,.16); border-radius:14px; background:#131020; box-shadow:0 10px 25px rgba(0,0,0,.12); }
.movie-poster { width:100%; aspect-ratio:2/2.8; object-fit:cover; display:block; background:linear-gradient(145deg,#291743,#100c1c); }
.poster-placeholder { width:100%; aspect-ratio:2/2.8; display:flex; flex-direction:column; justify-content:center; align-items:center; gap:.7rem; padding:1rem; text-align:center; color:#c9a5ef; background:radial-gradient(circle at 50% 25%,#42205e,#171022 70%); }
.poster-placeholder span { font-size:.8rem; font-weight:700; }
.movie-info { padding:.85rem; }
.movie-title { font-family:'Space Grotesk',sans-serif; color:#fff; font-size:1rem; font-weight:700; line-height:1.3; margin-bottom:.45rem; }
.movie-meta { display:flex; flex-wrap:wrap; gap:.4rem; color:#b2a6c2; font-size:.72rem; margin-bottom:.7rem; }
.pill { display:inline-block; border:1px solid rgba(192,132,252,.25); background:rgba(168,85,247,.1); color:#d8b8ff; padding:.2rem .48rem; border-radius:99px; font-size:.66rem; margin:0 .22rem .25rem 0; }
.movie-overview { color:#bdb3cc; font-size:.78rem; line-height:1.6; min-height:5rem; }
.why-box { border-top:1px solid rgba(201,163,255,.13); margin-top:.7rem; padding-top:.65rem; color:#d9c7ef; font-size:.74rem; line-height:1.5; }
.why-label { color:#c084fc; font-size:.64rem; letter-spacing:.1em; text-transform:uppercase; font-weight:700; margin-bottom:.25rem; }
.match { display:inline-block; color:#b7f4d2; background:rgba(52,211,153,.09); border:1px solid rgba(52,211,153,.2); border-radius:6px; padding:.2rem .4rem; font-size:.68rem; }
.helper { color:#a99eb8; font-size:.76rem; }
div[data-testid="stAlert"] { border-radius:10px; }
hr { border-color:rgba(201,163,255,.12) !important; }
footer { visibility:hidden; }
@media(max-width:700px) {
 .block-container { padding-left:1rem; padding-right:1rem; }
 .brandbar { align-items:flex-start; flex-direction:column; gap:.45rem; }
 .hero { border-radius:16px; padding:1.3rem; }
 .hero h1 { font-size:2.35rem; }
 .stat-row { gap:1rem; }
 .section-head { align-items:flex-start; flex-direction:column; }
 .movie-overview { min-height:0; }
}
</style>
""", unsafe_allow_html=True)


def normalize(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def recommendation_score(source, candidate):
    source_genres = set(source["genres"])
    candidate_genres = set(candidate["genres"])
    genre_overlap = len(source_genres & candidate_genres)
    source_keywords = set(source["keywords"])
    candidate_keywords = set(candidate["keywords"])
    keyword_overlap = len(source_keywords & candidate_keywords)
    # Lightweight baseline heuristic for the demo; replace with TF-IDF cosine similarity.
    return genre_overlap * 3 + keyword_overlap * 1.2 + candidate["rating"] * 0.12


def explain_recommendation(source, candidate):
    shared_genres = [g for g in source["genres"] if g in candidate["genres"]]
    shared_keywords = [k for k in source["keywords"] if k in candidate["keywords"]]
    reasons = []
    if shared_genres:
        reasons.append("shared genres: " + ", ".join(shared_genres[:3]))
    if shared_keywords:
        reasons.append("similar themes: " + ", ".join(shared_keywords[:3]))
    if not reasons:
        reasons.append("similar audience rating and broad storytelling profile")
    return "Recommended because it shares " + " and ".join(reasons) + " with " + source["title"] + "."


def find_movie(title):
    cleaned = normalize(title)
    if not cleaned:
        return None, "Please enter or select a movie first."
    for movie in MOVIES:
        if normalize(movie["title"]) == cleaned:
            return movie, None
    titles = {normalize(m["title"]): m for m in MOVIES}
    close = get_close_matches(cleaned, titles.keys(), n=1, cutoff=0.66)
    if close:
        return None, f"We couldn't find “{title}”. Did you mean **{titles[close[0]]['title']}**?"
    return None, f"“{title}” isn't in this demo catalog. Try a title such as Interstellar, Inception, Dune: Part Two, or The Martian."


def get_recommendations(source, genre_filter, year_range):
    ranked = []
    for candidate in MOVIES:
        if candidate["title"] == source["title"]:
            continue
        if genre_filter != "All genres" and genre_filter not in candidate["genres"]:
            continue
        if not (year_range[0] <= candidate["year"] <= year_range[1]):
            continue
        score = recommendation_score(source, candidate)
        ranked.append((score, candidate))
    ranked.sort(key=lambda item: (item[0], item[1]["rating"]), reverse=True)
    results = []
    for score, movie in ranked:
        item = dict(movie)
        item["why"] = explain_recommendation(source, movie)
        item["match"] = min(99, max(65, round(65 + score * 2.2)))
        results.append(item)
    return results[:5]


def render_movie_card(movie, index):
    st.markdown('<div class="movie-card">', unsafe_allow_html=True)
    try:
        st.image(movie["poster"], use_container_width=True)
    except Exception:
        st.markdown(
            f'<div class="poster-placeholder"><span>🎬</span><span>{movie["title"]}</span><small>Poster unavailable</small></div>',
            unsafe_allow_html=True,
        )
    st.markdown('<div class="movie-info">', unsafe_allow_html=True)
    st.markdown(f'<div class="movie-title">{movie["title"]}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="movie-meta"><span>{movie["year"]}</span><span>★ {movie["rating"]:.1f}</span><span>#{index}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown("".join(f'<span class="pill">{g}</span>' for g in movie["genres"]), unsafe_allow_html=True)
    st.markdown(f'<div class="movie-overview">{movie["overview"]}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="why-box"><div class="why-label">✦ Why this match</div>{movie["why"]}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div style="margin-top:.7rem"><span class="match">{movie["match"]}% similarity (demo)</span></div>', unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)


# Header
st.markdown("""
<div class="brandbar">
  <div class="brand"><span style="color:#f8f5ff;text-shadow:none">Watch</span><span class="brand-name-accent">Next</span><span class="brand-subtitle">AI MOVIE DISCOVERY</span></div>
  <div class="brand-tag">✦ Find your next favorite movie</div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<section class="hero">
  <div class="eyebrow">YOUR PERSONAL CINEMA · AI / ML HACKATHON</div>
  <h1>Less scrolling.<br><span>More great stories.</span></h1>
  <p>Tell WatchNext one movie you love. We'll find five movies with similar genres, themes, and storytelling — and explain why each one made the list.</p>
  <div class="stat-row">
    <div class="stat"><strong>5 picks</strong><small>Focused recommendations</small></div>
    <div class="stat"><strong>Explainable</strong><small>See why each movie fits</small></div>
    <div class="stat"><strong>Free demo</strong><small>No paid API required</small></div>
  </div>
</section>
""", unsafe_allow_html=True)

# Search and filter controls
st.markdown('<div class="section-head"><div><div class="eyebrow">START WITH A FAVORITE</div><h2>What did you enjoy watching?</h2><p>Search the demo catalog or choose a title from the list.</p></div></div>', unsafe_allow_html=True)

catalog_titles = [m["title"] for m in MOVIES]
c1, c2 = st.columns([2.3, 1], gap="large")
with c1:
    typed_title = st.text_input(
        "Movie title",
        placeholder="e.g. Interstellar",
        key="movie_search",
        help="Enter a movie title available in the demo catalog.",
    )
    selected_title = st.selectbox("Or choose a movie", ["— Choose a movie —"] + catalog_titles, index=0)
with c2:
    st.markdown('<div class="panel"><div class="panel-title">Fine-tune your picks</div><div class="panel-subtitle">Optional filters apply to the recommended results.</div>', unsafe_allow_html=True)
    genre_filter = st.selectbox("Genre", ["All genres"] + GENRES, index=0)
    min_year, max_year = min(YEARS), max(YEARS)
    year_range = st.slider("Release year", min_value=min_year, max_value=max_year, value=(min_year, max_year))
    st.markdown('</div>', unsafe_allow_html=True)

b1, b2, spacer = st.columns([1.6, 1, 4])
with b1:
    find_clicked = st.button("✦  Find Similar Movies", type="primary", use_container_width=True)
with b2:
    surprise_clicked = st.button("🎲  Surprise Me", type="secondary", use_container_width=True)

if "results" not in st.session_state:
    st.session_state.results = None
if "source_title" not in st.session_state:
    st.session_state.source_title = None

if find_clicked or surprise_clicked:
    with st.spinner("Finding movies with similar genres and themes..."):
        if surprise_clicked:
            source = random.choice(MOVIES)
            error = None
        else:
            title_to_find = typed_title.strip() if typed_title.strip() else (selected_title if selected_title != "— Choose a movie —" else "")
            source, error = find_movie(title_to_find)

        if error:
            st.session_state.results = None
            st.session_state.source_title = None
            st.warning(error)
        else:
            results = get_recommendations(source, genre_filter, year_range)
            st.session_state.source_title = source
            st.session_state.results = results
            if len(results) < 5:
                st.info(f"Only {len(results)} recommendations match these filters. Widen the genre or year range to see five results.")
            elif len(results) == 0:
                st.warning("No recommendations match the current filters. Try a wider filter range.")

if st.session_state.results is not None and st.session_state.source_title:
    source = st.session_state.source_title
    results = st.session_state.results
    st.markdown("---")
    st.markdown(
        f'<div class="section-head"><div><div class="eyebrow">PERSONALIZED RESULTS</div><h2>Because you liked <span style="color:#c084fc">{source["title"]}</span></h2><p>Ranked using shared genres, keywords, and rating as a demo baseline.</p></div><div class="match">✓ Recommendation run complete</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="panel" style="margin-bottom:1rem"><div class="panel-title">Why these recommendations?</div><div class="panel-subtitle" style="margin:0">We compare genre overlap and shared themes, then generate a short human-readable reason for each suggestion. Replace this baseline with TF-IDF + cosine similarity for the final AI/ML submission.</div></div>',
        unsafe_allow_html=True,
    )
    if results:
        cols = st.columns(5 if len(results) == 5 else min(5, len(results)), gap="medium")
        for i, movie in enumerate(results):
            with cols[i % len(cols)]:
                render_movie_card(movie, i + 1)
    else:
        st.warning("No recommendations are available with the selected filters. Widen the filter range and try again.")

st.markdown("---")
st.markdown("""
<div style="display:flex;justify-content:space-between;gap:1rem;align-items:center;flex-wrap:wrap;color:#82778f;font-size:.72rem">
  <span><strong style="color:#c9b6df">WatchNext</strong> · AI movie recommendation prototype</span>
  <span>Demo catalog · Poster images need an internet connection · Replace sample data before final submission</span>
</div>
""", unsafe_allow_html=True)
