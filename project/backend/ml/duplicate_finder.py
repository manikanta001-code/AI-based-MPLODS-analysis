"""
ml/duplicate_finder.py
────────────────────────
Duplicate/near-duplicate work detection — Section C, items 7 & 8.

APPROACH
  1. TF-IDF vectorize `work_description`, MODEL-BASED similarity via
     cosine distance (this is the primary, learned-similarity detector —
     not string-matching).
  2. thefuzz.token_set_ratio as a CONFIRMATION layer only, applied to the
     top cosine-similarity candidate, to filter out cases where TF-IDF
     found "similar bag-of-words" but the descriptions aren't actually
     near-duplicates (token_set_ratio is robust to word reordering/extra
     words, which is exactly the kind of near-duplicate MPLADS work
     descriptions often are, e.g. two "PCC road from X to Y" entries).

BLOCKING FOR TRACTABILITY
  49,000 descriptions -> a full 49,000 x 49,000 similarity matrix is
  infeasible. Duplicate MPLADS works are also, in practice, only
  meaningful WITHIN the same state and work category (a road in Kerala
  is never a "duplicate" of a school-room in Punjab) — so we block by
  (state, work_category) and use scikit-learn's NearestNeighbors with
  cosine metric (sparse, top-k only) inside each block instead of a
  dense pairwise matrix. This is exact (not approximate) similarity
  search, just scoped sensibly.

SAVED ARTIFACT
  We persist the fitted vectorizer + description-vector matrix PER BLOCK
  so that scorer.py can embed a newly uploaded description with
  `.transform()` (no refit) and compare it against the full historical
  corpus for its block instantly — this is what makes the upload/scoring
  endpoint fast ("train once, score new data instantly").
"""

import pickle

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors
from thefuzz import fuzz

from config import TFIDF_PATH, DUPLICATE_FUZZY_THRESHOLD

MIN_BLOCK_SIZE = 2          # need at least 2 works to compare
COSINE_SIM_CANDIDATE_THRESHOLD = 0.6   # only bother running thefuzz above this


def build_duplicate_index(df: pd.DataFrame, description_col="work_description",
                           block_cols=("state", "work_category")):
    """
    Fits one TfidfVectorizer + NearestNeighbors index per (state, category) block.
    Returns: {block_key: {"vectorizer", "nn", "matrix", "work_ids", "descriptions"}}
    """
    index = {}
    df = df.copy()
    df[description_col] = df[description_col].fillna("")

    for block_key, group in df.groupby(list(block_cols)):
        if len(group) < MIN_BLOCK_SIZE:
            continue
        texts = group[description_col].tolist()
        vectorizer = TfidfVectorizer(stop_words="english", max_features=3000, ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(texts)

        n_neighbors = min(6, len(group))
        nn = NearestNeighbors(n_neighbors=n_neighbors, metric="cosine", algorithm="brute", n_jobs=-1)
        nn.fit(matrix)

        index[block_key] = {
            "vectorizer": vectorizer,
            "nn": nn,
            "matrix": matrix,
            "work_ids": group["work_id"].tolist(),
            "descriptions": texts,
        }
    return index


def score_duplicates(df: pd.DataFrame, index: dict, description_col="work_description",
                      block_cols=("state", "work_category"), exclude_self=True):
    """
    For every row in df, finds the most similar OTHER description within its
    (state, category) block. Returns a DataFrame aligned to df's index with:
      duplicate_score (0-100, cosine-similarity based — used in risk fusion)
      duplicate_match_work_id (nearest neighbour's work_id, or None)
      duplicate_confirmed (bool — thefuzz token_set_ratio > threshold on the top candidate)
    """
    df = df.copy()
    df[description_col] = df[description_col].fillna("")

    n = len(df)
    duplicate_score = np.zeros(n)
    match_id = np.full(n, None, dtype=object)
    confirmed = np.zeros(n, dtype=bool)

    for block_key, group in df.groupby(list(block_cols)):
        entry = index.get(block_key)
        if entry is None:
            continue  # block too small at train time, or unseen block for new data

        texts = group[description_col].tolist()
        query_vecs = entry["vectorizer"].transform(texts)
        k = entry["nn"].n_neighbors
        distances, neighbor_idx = entry["nn"].kneighbors(query_vecs, n_neighbors=k)

        for local_i, (row_idx, dist_row, nbr_row) in enumerate(zip(group.index, distances, neighbor_idx)):
            this_work_id = group.loc[row_idx, "work_id"]
            best_sim, best_match_id, best_desc = 0.0, None, None
            for dist, nbr in zip(dist_row, nbr_row):
                candidate_id = entry["work_ids"][nbr]
                if exclude_self and candidate_id == this_work_id:
                    continue
                sim = 1 - dist
                if sim > best_sim:
                    best_sim = sim
                    best_match_id = candidate_id
                    best_desc = entry["descriptions"][nbr]
                break  # kneighbors returns sorted by distance; first non-self is the best

            duplicate_score[df.index.get_loc(row_idx)] = best_sim * 100
            match_id[df.index.get_loc(row_idx)] = best_match_id

            if best_sim >= COSINE_SIM_CANDIDATE_THRESHOLD and best_desc is not None:
                this_desc = group.loc[row_idx, description_col]
                fuzzy_score = fuzz.token_set_ratio(this_desc, best_desc)
                confirmed[df.index.get_loc(row_idx)] = fuzzy_score > DUPLICATE_FUZZY_THRESHOLD

    return pd.DataFrame({
        "duplicate_score": duplicate_score,
        "duplicate_match_work_id": match_id,
        "duplicate_confirmed": confirmed,
    }, index=df.index)


def save_index(index: dict):
    with open(TFIDF_PATH, "wb") as f:
        pickle.dump(index, f)


def load_index():
    with open(TFIDF_PATH, "rb") as f:
        return pickle.load(f)
