"""
WatchNext - movie recommender (inference module)
================================================
Loads the artifacts produced by the training notebook and exposes a small,
dependency-light API (numpy / scipy only; pandas is NOT imported) for the backend:

    from recommender import recommend_movies, search_movies, list_genres

    recommend_movies("Avatar", n=5, genre="Action", year_min=2000)
    search_movies("batm")
    list_genres()

Configuration (environment variables, all optional)
    WATCHNEXT_ARTIFACT_DIR   folder that holds movies.json / features.npz / config.json
                             (default: ./artifacts next to this file)

Errors the backend should map to HTTP responses
    EmptyQueryError      (ValueError)   -> 400 / 422  empty or missing title
    InvalidFilterError   (ValueError)   -> 422        bad genre / year / n
    MovieNotFoundError   (LookupError)  -> 404        unknown title (has .suggestions)
"""
from __future__ import annotations

import difflib
import json
import logging
import os
import re
import threading
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import scipy.sparse as sp

__all__ = [
    "recommend_movies", "search_movies", "list_genres", "get_recommender",
    "reload_artifacts", "WatchNextRecommender",
    "EmptyQueryError", "InvalidFilterError", "MovieNotFoundError",
]

log = logging.getLogger("watchnext")

MAX_N = 50
RECOMMENDATION_FIELDS = (
    "movie_id", "title", "genres", "overview",
    "poster_path", "similarity_score", "recommendation_reason",
)


def _default_artifact_dir() -> Path:
    env = os.environ.get("WATCHNEXT_ARTIFACT_DIR")
    if env:
        return Path(env)
    try:
        return Path(__file__).resolve().parent / "artifacts"
    except NameError:  # pragma: no cover - interactive use
        return Path("artifacts")


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class EmptyQueryError(ValueError):
    """The title / query was missing or blank."""


class InvalidFilterError(ValueError):
    """A filter or parameter (genre, year, n, movie_id) was invalid."""


class MovieNotFoundError(LookupError):
    """The requested movie is not in the catalog."""

    def __init__(self, query: str, suggestions: Optional[List[str]] = None):
        self.query = query
        self.suggestions = suggestions or []
        msg = f"Movie not found: {query!r}."
        if self.suggestions:
            msg += " Did you mean: " + ", ".join(self.suggestions[:5]) + "?"
        super().__init__(msg)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _norm(text: Any) -> str:
    """Accent/punctuation/case-insensitive key: 'Spider-Man 3' == 'spiderman 3'."""
    if text is None:
        return ""
    s = str(text)
    ascii_s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    key = re.sub(r"[^a-z0-9]+", "", ascii_s.lower())
    return key or s.strip().lower()


def _to_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise InvalidFilterError(f"{name} must be an integer.")
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise InvalidFilterError(f"{name} must be an integer.") from None
    if f != int(f):
        raise InvalidFilterError(f"{name} must be an integer.")
    return int(f)


def _join(items: Sequence[str]) -> str:
    return ", ".join(items)


# --------------------------------------------------------------------------- #
# Core class
# --------------------------------------------------------------------------- #
class WatchNextRecommender:
    """Content-based recommender over pre-computed TF-IDF feature blocks."""

    def __init__(self, artifact_dir: Union[str, Path, None] = None):
        d = Path(artifact_dir) if artifact_dir else _default_artifact_dir()
        needed = ["movies.json", "features.npz", "config.json"]
        missing = [f for f in needed if not (d / f).exists()]
        if missing:
            raise FileNotFoundError(
                f"Missing artifact file(s) {missing} in '{d}'. Run the notebook first "
                f"or set WATCHNEXT_ARTIFACT_DIR."
            )
        with open(d / "movies.json", encoding="utf-8") as fh:
            self._rec: List[Dict[str, Any]] = json.load(fh)
        self.X: sp.csr_matrix = sp.load_npz(d / "features.npz").tocsr()
        with open(d / "config.json", encoding="utf-8") as fh:
            self.config: Dict[str, Any] = json.load(fh)

        poster_file = d / "poster_paths.json"  # optional {movie_id: "/abc.jpg"}
        self._posters: Dict[int, str] = {}
        if poster_file.exists():
            with open(poster_file, encoding="utf-8") as fh:
                self._posters = {int(k): v for k, v in json.load(fh).items() if v}

        if self.X.shape[0] != len(self._rec):
            raise ValueError("Artifacts are inconsistent: feature rows != movie records.")
        self._build_indexes()
        log.info("WatchNext loaded: %d movies, %d features", len(self._rec), self.X.shape[1])

    # ------------------------------------------------------------------ #
    def _build_indexes(self) -> None:
        n = len(self._rec)
        self._ids = [int(r["movie_id"]) for r in self._rec]
        self._id_to_idx = {mid: i for i, mid in enumerate(self._ids)}
        self._vote_count = np.array([r.get("vote_count") or 0 for r in self._rec], dtype=np.float64)
        self._popularity = np.array([r.get("popularity") or 0.0 for r in self._rec], dtype=np.float64)
        self._years = np.array(
            [r["release_year"] if r.get("release_year") is not None else -1 for r in self._rec],
            dtype=np.int32,
        )
        self._key_to_idx: Dict[str, List[int]] = {}
        for i, r in enumerate(self._rec):
            self._key_to_idx.setdefault(_norm(r["title"]), []).append(i)
        self._keys = list(self._key_to_idx.keys())

        self._genre_display: Dict[str, str] = {}
        self._genre_masks: Dict[str, np.ndarray] = {}
        for i, r in enumerate(self._rec):
            for g in r.get("genres") or []:
                low = g.lower()
                self._genre_display.setdefault(low, g)
                self._genre_masks.setdefault(low, np.zeros(n, dtype=bool))[i] = True
        self._blocks = self.config.get("blocks", {})
        self._ov_min = float(self.config.get("overview_reason_min", 0.15))

    # ------------------------------------------------------------------ #
    # Public helpers
    # ------------------------------------------------------------------ #
    def __len__(self) -> int:
        return len(self._rec)

    def genres(self) -> List[str]:
        return sorted(self._genre_display.values())

    def suggest(self, title: str, k: int = 5) -> List[str]:
        """Closest catalog titles for a (mis)typed query."""
        key = _norm(title)
        if not key:
            return []
        picked: List[str] = []
        if len(key) >= 3:  # substring hits first, most-voted titles first
            subs = [k_ for k_ in self._keys if key in k_]
            subs.sort(key=lambda k_: -max(self._vote_count[i] for i in self._key_to_idx[k_]))
            picked += subs
        picked += difflib.get_close_matches(key, self._keys, n=k * 2, cutoff=0.72)
        out: List[str] = []
        seen = set()
        for k_ in picked:
            if k_ in seen:
                continue
            seen.add(k_)
            best = max(self._key_to_idx[k_], key=lambda i: self._vote_count[i])
            out.append(self._rec[best]["title"])
            if len(out) >= k:
                break
        return out

    def search(self, q: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Title search for autocomplete: exact > prefix > substring > fuzzy."""
        if q is None or not isinstance(q, str) or not q.strip():
            raise EmptyQueryError("Search query is empty.")
        limit = self._check_n(limit, name="limit")
        key, raw = _norm(q), q.strip().lower()
        ranked = []
        for i, r in enumerate(self._rec):
            tkey, tlow = _norm(r["title"]), r["title"].lower()
            if key == tkey:
                tier = 0
            elif tkey.startswith(key) or tlow.startswith(raw):
                tier = 1
            elif key in tkey or raw in tlow:
                tier = 2
            else:
                continue
            ranked.append((tier, -self._vote_count[i], i))
        ranked.sort()
        idxs = [i for _, _, i in ranked][:limit]
        if len(idxs) < limit:  # top up with fuzzy matches so typos still return something
            for title in self.suggest(q, k=limit):
                for i in self._key_to_idx[_norm(title)]:
                    if i not in idxs and len(idxs) < limit:
                        idxs.append(i)
        return [
            {
                "movie_id": self._ids[i],
                "title": self._rec[i]["title"],
                "release_year": self._rec[i].get("release_year"),
                "genres": list(self._rec[i].get("genres") or []),
            }
            for i in idxs
        ]

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    @staticmethod
    def _check_n(n: Any, name: str = "n") -> int:
        n = _to_int(n, name)
        if not 1 <= n <= MAX_N:
            raise InvalidFilterError(f"{name} must be between 1 and {MAX_N}.")
        return n

    def _genre_filter(self, genre: Any) -> Optional[np.ndarray]:
        if genre is None:
            return None
        items = genre.split(",") if isinstance(genre, str) else list(genre)
        wanted = [str(g).strip().lower() for g in items if str(g).strip()]
        if not wanted:
            return None
        unknown = [g for g in wanted if g not in self._genre_masks]
        if unknown:
            raise InvalidFilterError(
                f"Unknown genre(s) {unknown}. Available: {', '.join(self.genres())}."
            )
        mask = np.zeros(len(self._rec), dtype=bool)
        for g in wanted:
            mask |= self._genre_masks[g]
        return mask

    def _year_filter(self, year: Any, year_min: Any, year_max: Any) -> Optional[np.ndarray]:
        if year is not None and (year_min is not None or year_max is not None):
            raise InvalidFilterError("Use either 'year' or 'year_min'/'year_max', not both.")
        if year is not None:
            year_min = year_max = year
        if year_min is None and year_max is None:
            return None
        lo = _to_int(year_min, "year_min") if year_min is not None else 1800
        hi = _to_int(year_max, "year_max") if year_max is not None else 2100
        if lo > hi:
            raise InvalidFilterError("year_min cannot be greater than year_max.")
        return (self._years >= lo) & (self._years <= hi) & (self._years != -1)

    def _resolve(self, title: Any, movie_id: Any) -> int:
        if movie_id is not None:
            mid = _to_int(movie_id, "movie_id")
            idx = self._id_to_idx.get(mid)
            if idx is None:
                raise MovieNotFoundError(f"movie_id={mid}")
            return idx
        if title is None or (isinstance(title, str) and not title.strip()):
            raise EmptyQueryError("Please provide a movie title.")
        if not isinstance(title, str):
            raise InvalidFilterError("title must be a string.")
        cands = self._key_to_idx.get(_norm(title))
        if not cands:
            raise MovieNotFoundError(title.strip(), self.suggest(title))
        # Same title, several films (e.g. 'Batman' 1966 vs 1989): take the best known one.
        return max(cands, key=lambda i: (self._vote_count[i], self._popularity[i]))

    # ------------------------------------------------------------------ #
    # Explanation
    # ------------------------------------------------------------------ #
    def _overview_cosine(self, qi: int, ji: int) -> float:
        blk = self._blocks.get("overview")
        w = float(self.config.get("weights", {}).get("overview", 0) or 0)
        if not blk or w <= 0:
            return 0.0
        a, b = blk
        rows = self.X[[qi, ji]][:, a:b]
        return float(rows[0].multiply(rows[1]).sum()) / w

    def _reason(self, qi: int, ji: int) -> str:
        q, r = self._rec[qi], self._rec[ji]
        r_genres = {g.lower() for g in r.get("genres") or []}
        r_kw = {k.lower() for k in r.get("keywords") or []}
        r_cast = {c.lower() for c in r.get("cast") or []}
        shared = []
        g = [x for x in q.get("genres") or [] if x.lower() in r_genres]
        k = [x for x in q.get("keywords") or [] if x.lower() in r_kw][:4]
        c = [x for x in q.get("cast") or [] if x.lower() in r_cast][:3]
        if g:
            shared.append("genres: " + _join(g))
        if k:
            shared.append("keywords: " + _join(k))
        if c:
            shared.append("cast: " + _join(c))
        sentences = []
        if shared:
            sentences.append("Shares " + "; ".join(shared))
        if q.get("director") and q.get("director") == r.get("director"):
            sentences.append(f"Same director: {q['director']}")
        if self._overview_cosine(qi, ji) >= self._ov_min:
            sentences.append("Similar plot description")
        if not sentences:
            sentences.append("Closest overall match on plot and themes")
        return ". ".join(sentences) + "."

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #
    def recommend(
        self,
        title: Optional[str] = None,
        n: int = 5,
        genre: Union[str, Sequence[str], None] = None,
        year: Optional[int] = None,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
        movie_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        n = self._check_n(n)
        genre_mask = self._genre_filter(genre)
        year_mask = self._year_filter(year, year_min, year_max)
        qi = self._resolve(title, movie_id)

        sims = (self.X @ self.X[qi].T).toarray().ravel()
        mask = np.ones(len(self._rec), dtype=bool)
        mask[qi] = False  # never recommend the movie itself
        if genre_mask is not None:
            mask &= genre_mask
        if year_mask is not None:
            mask &= year_mask
        cand = np.flatnonzero(mask & (sims > 0))
        if cand.size == 0:
            return []
        order = np.lexsort((-self._popularity[cand], -sims[cand]))  # score desc, then popularity
        top = cand[order[:n]]

        results = []
        for j in top:
            r = self._rec[j]
            results.append(
                {
                    "movie_id": self._ids[j],
                    "title": r["title"],
                    "genres": list(r.get("genres") or []),
                    "overview": r.get("overview") or "",
                    "poster_path": self._posters.get(self._ids[j]),
                    "similarity_score": round(float(min(sims[j], 1.0)), 4),
                    "recommendation_reason": self._reason(qi, int(j)),
                }
            )
        return results


# --------------------------------------------------------------------------- #
# Module-level API (lazy singleton: artifacts are loaded once, thread-safe)
# --------------------------------------------------------------------------- #
_INSTANCE: Optional[WatchNextRecommender] = None
_LOCK = threading.Lock()


def get_recommender() -> WatchNextRecommender:
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = WatchNextRecommender()
    return _INSTANCE


def reload_artifacts(artifact_dir: Union[str, Path, None] = None) -> WatchNextRecommender:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = WatchNextRecommender(artifact_dir)
    return _INSTANCE


def recommend_movies(
    title: Optional[str] = None,
    n: int = 5,
    genre: Union[str, Sequence[str], None] = None,
    year: Optional[int] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    movie_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return up to ``n`` similar movies, each a dict with exactly the fields:

    movie_id, title, genres (list[str]), overview, poster_path (None when the
    dataset has no poster), similarity_score (0-1), recommendation_reason.

    Raises EmptyQueryError, InvalidFilterError, MovieNotFoundError (see module doc).
    """
    return get_recommender().recommend(title, n, genre, year, year_min, year_max, movie_id)


def search_movies(q: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Title search / autocomplete (movie_id, title, release_year, genres)."""
    return get_recommender().search(q, limit)


def list_genres() -> List[str]:
    return get_recommender().genres()


if __name__ == "__main__":  # python recommender.py "Avatar"
    import sys

    for rec in recommend_movies(" ".join(sys.argv[1:]) or "Avatar"):
        print(f"{rec['similarity_score']:.3f}  {rec['title']:<40} {rec['recommendation_reason']}")
