"""
WatchNext ML module — contract adapter for the integration kit.

Implements the shared integration contract (see README.md):
    from model.recommender import load_model, search_movies, recommend_movies
    load_model()                                              # call once at startup
    search_movies(query, limit=10) -> list[dict]
    recommend_movies(movie_title, genre=None, year=None, top_n=5) -> list[dict]
Every result dict contains exactly these shared keys:
    movie_id, title, genres (list[str]), overview, poster_path,
    similarity_score (number|None), reason (str)
The recommendation algorithm itself is NOT implemented here. It lives in
model/engine.py (a verbatim copy of the original, behaviour-unchanged
recommender; only its docstring was corrected). This adapter renames the
engine key "recommendation_reason" -> "reason", maps contract parameters,
validates inputs with distinguishable typed errors, normalises search
output to the seven shared keys, and exposes idempotent load_model() which
loads artifacts into memory once.
Configuration (environment variables, all optional)
    WATCHNEXT_ARTIFACT_DIR   folder holding movies.json / features.npz /
                             config.json (default: model/artifacts next to
                             engine.py; overridden by this variable)
Errors the backend should map to HTTP responses
    EmptyQueryError      -> 400 EMPTY_QUERY      empty/missing title or query
    InvalidYearError     -> 400 INVALID_YEAR     year is not an integer
    InvalidTopNError     -> 400 INVALID_TOP_N    top_n/limit not in 1..50
    InvalidGenreError    -> 400 INVALID_FILTER   unknown genre(s)
    MovieNotFoundError   -> 404 MOVIE_NOT_FOUND  unknown title (.suggestions)
    any load failure     -> 503 MODEL_NOT_READY  artifacts missing/unreadable
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from model.engine import (  # noqa: E402  (algorithm module, behaviour unchanged)
    EmptyQueryError,
    InvalidFilterError,
    MovieNotFoundError,
    WatchNextRecommender,
)

log = logging.getLogger("watchnext")

SHARED_KEYS = (
    "movie_id", "title", "genres", "overview", "poster_path",
    "similarity_score", "reason",
)
MAX_TOP_N = 50
DEFAULT_TOP_N = 5
DEFAULT_LIMIT = 10


class InvalidYearError(InvalidFilterError):
    """The ``year`` filter value is not a valid integer."""


class InvalidTopNError(InvalidFilterError):
    """``top_n``/``limit`` is not an integer in 1..50."""


class InvalidGenreError(InvalidFilterError):
    """The ``genre`` value names a genre not in the catalog.

    Reported with code INVALID_FILTER (400) by the backend; see HANDOFF_README.md.
    """


__all__ = [
    "load_model", "search_movies", "recommend_movies", "is_model_ready",
    "get_recommender",
    "EmptyQueryError", "InvalidFilterError", "InvalidYearError",
    "InvalidTopNError", "InvalidGenreError", "MovieNotFoundError",
]

_INSTANCE: Optional[WatchNextRecommender] = None
_MODEL_READY = False
_LOCK = threading.Lock()


def load_model() -> None:
    """Load the recommendation artifacts into memory.

    Idempotent and safe to call once at backend startup (and safe to call
    repeatedly): artifacts are loaded only on the first call. Reads
    ``WATCHNEXT_ARTIFACT_DIR`` if set, otherwise defaults to
    ``model/artifacts`` next to model/engine.py. Raises FileNotFoundError
    (or any other load failure) if the artifacts are missing or unreadable;
    the backend must map that to MODEL_NOT_READY (503).
    """
    global _INSTANCE, _MODEL_READY
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = WatchNextRecommender()
            _MODEL_READY = True
            log.info("WatchNext model loaded via load_model()")


def is_model_ready() -> bool:
    """True once load_model() has completed successfully."""
    return _MODEL_READY


def get_recommender() -> WatchNextRecommender:
    """Return the loaded recommender, loading artifacts lazily on first use."""
    global _INSTANCE, _MODEL_READY
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = WatchNextRecommender()
            _MODEL_READY = True
    return _INSTANCE


def _check_top_n(value: Any, name: str) -> int:
    if value is None:
        return DEFAULT_TOP_N
    if isinstance(value, bool):
        raise InvalidTopNError(f"{name} must be an integer between 1 and {MAX_TOP_N}.")
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise InvalidTopNError(f"{name} must be an integer between 1 and {MAX_TOP_N}.") from None
    if f != int(f) or not 1 <= int(f) <= MAX_TOP_N:
        raise InvalidTopNError(f"{name} must be an integer between 1 and {MAX_TOP_N}.")
    return int(f)


def _check_year(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise InvalidYearError("year must be an integer (release year).")
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise InvalidYearError("year must be an integer (release year).") from None
    if f != int(f):
        raise InvalidYearError("year must be an integer (release year).")
    return int(f)


def _require_nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EmptyQueryError(f"{name} is required and must not be empty.")
    return value.strip()


def _score(value: Any):
    if value is None:
        return None
    try:
        s = float(value)
    except (TypeError, ValueError):
        return None
    if s != s:  # NaN
        return None
    return s


def _engine_row_to_contract(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "movie_id": row["movie_id"],
        "title": row["title"],
        "genres": [str(g) for g in (row.get("genres") or [])],
        "overview": row.get("overview") or "",
        "poster_path": row.get("poster_path"),
        "similarity_score": _score(row.get("similarity_score")),
        "reason": row.get("reason") or row.get("recommendation_reason") or "",
    }


def _search_row_to_contract(row: Dict[str, Any]) -> Dict[str, Any]:
    """Search results carry the seven shared keys; similarity/reason are null."""
    return {
        "movie_id": row["movie_id"],
        "title": row["title"],
        "genres": [str(g) for g in (row.get("genres") or [])],
        "overview": row.get("overview") or "",
        "poster_path": None,
        "similarity_score": None,
        "reason": None,
    }


def recommend_movies(
    movie_title: str,
    genre: Optional[str] = None,
    year: Optional[int] = None,
    top_n: int = DEFAULT_TOP_N,
) -> List[Dict[str, Any]]:
    """Return up to ``top_n`` similar movies (shared contract schema)."""
    title = _require_nonempty_string(movie_title, "movie_title")
    n = _check_top_n(top_n, "top_n")
    yr = _check_year(year)
    rec = get_recommender()
    try:
        rows = rec.recommend(title=title, n=n, genre=genre, year=yr)
    except InvalidFilterError as exc:
        msg = str(exc)
        if "Unknown genre" in msg:
            raise InvalidGenreError(msg) from exc
        raise InvalidTopNError(msg) from exc
    return [_engine_row_to_contract(r) for r in rows]


def search_movies(query: str, limit: int = DEFAULT_LIMIT) -> List[Dict[str, Any]]:
    """Case-insensitive title search returning the seven shared keys."""
    q = _require_nonempty_string(query, "query")
    lim = _check_top_n(limit, "limit")
    rec = get_recommender()
    rows = rec.search(q, limit=lim)
    return [_search_row_to_contract(r) for r in rows]
