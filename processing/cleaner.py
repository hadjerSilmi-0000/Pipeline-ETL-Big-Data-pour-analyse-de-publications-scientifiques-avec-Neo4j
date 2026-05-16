import json
import os
import re
import unicodedata
from datetime import datetime
from tqdm import tqdm

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import DATA_RAW_PATH, DATA_PROCESSED_PATH
from config.logging_config import setup_logger

logger = setup_logger("cleaner")


# ─── Nettoyage texte ─────────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    """Normalise un texte : unicode, espaces, caracteres speciaux"""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


def normalize_author_name(name: str) -> str:
    """Normalise un nom d'auteur"""
    if not name:
        return ""
    name = normalize_text(name)
    # supprime les titres academiques
    name = re.sub(r"\b(Dr|Prof|Mr|Mrs|Ms)\.?\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def extract_year(date_str: str) -> int | None:
    """Extrait l'annee depuis une date string"""
    if not date_str:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", date_str)
    return int(match.group()) if match else None


def extract_keywords(text: str) -> list[str]:
    """Extrait des mots-cles simples depuis le titre et l'abstract"""
    STOPWORDS = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "is", "are", "was", "were",
        "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "will", "would", "could", "should", "may", "might", "this", "that",
        "these", "those", "we", "our", "their", "its", "it", "as", "via",
        "based", "using", "show", "paper", "propose", "approach", "method",
        "model", "result", "use", "used", "also", "two", "new", "more"
    }

    text = text.lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    words = text.split()
    keywords = [w for w in words if len(w) > 3 and w not in STOPWORDS]

    # frequence
    freq = {}
    for w in keywords:
        freq[w] = freq.get(w, 0) + 1

    top_keywords = sorted(freq, key=freq.get, reverse=True)[:15]
    return top_keywords


# ─── Nettoyage paper ─────────────────────────────────────────────────────────

def clean_paper(paper: dict) -> dict | None:
    """Nettoie et valide un paper"""

    # champs obligatoires
    arxiv_id = paper.get("arxiv_id", "").strip()
    title    = normalize_text(paper.get("title", ""))
    abstract = normalize_text(paper.get("abstract", ""))

    if not arxiv_id or not title or len(title) < 5:
        logger.debug(f"Paper ignore (champs manquants) : {arxiv_id}")
        return None

    # auteurs
    raw_authors = paper.get("authors", [])
    authors = []
    for a in raw_authors:
        name = normalize_author_name(a if isinstance(a, str) else a.get("name", ""))
        if name and len(name) > 2:
            authors.append(name)

    if not authors:
        logger.debug(f"Paper ignore (aucun auteur) : {title[:40]}")
        return None

    # date
    published = paper.get("published", "")
    year      = extract_year(published)

    # categories / topics
    categories = paper.get("categories", [])
    if isinstance(categories, str):
        categories = [categories]

    # keywords depuis titre + abstract
    keywords = extract_keywords(f"{title} {abstract}")

    # donnees S2
    s2_data = paper.get("s2_data") or {}
    s2_id                     = s2_data.get("s2_id", "")
    citation_count            = s2_data.get("citation_count", 0) or 0
    reference_count           = s2_data.get("reference_count", 0) or 0
    influential_citation_count= s2_data.get("influential_citation_count", 0) or 0
    venue                     = normalize_text(s2_data.get("venue", "") or "")

    # citations et references (liste de paper_ids)
    raw_citations  = s2_data.get("citations", [])  or []
    raw_references = s2_data.get("references", []) or []

    citations = [
        c.get("citingPaper", {}).get("paperId", "")
        for c in raw_citations
        if c.get("citingPaper", {}).get("paperId")
    ]

    references = [
        r.get("citedPaper", {}).get("paperId", "")
        for r in raw_references
        if r.get("citedPaper", {}).get("paperId")
    ]

    cleaned = {
        "arxiv_id"                   : arxiv_id,
        "s2_id"                      : s2_id,
        "title"                      : title,
        "abstract"                   : abstract,
        "authors"                    : authors,
        "year"                       : year,
        "published"                  : published,
        "categories"                 : categories,
        "keywords"                   : keywords,
        "doi"                        : paper.get("doi", "") or "",
        "pdf_url"                    : paper.get("pdf_url", "") or "",
        "venue"                      : venue,
        "citation_count"             : citation_count,
        "reference_count"            : reference_count,
        "influential_citation_count" : influential_citation_count,
        "citations"                  : citations,
        "references"                 : references,
        "query"                      : paper.get("query", ""),
        "cleaned_at"                 : datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    return cleaned


# ─── Pipeline nettoyage ──────────────────────────────────────────────────────

def run_cleaning(input_file: str = None) -> list[dict]:
    """Pipeline complet de nettoyage"""

    if input_file is None:
        # si enriched existe on le prend, sinon all_papers
        enriched_path = os.path.join(DATA_RAW_PATH, "enriched_papers.json")
        raw_path      = os.path.join(DATA_RAW_PATH, "all_papers.json")
        input_file    = enriched_path if os.path.exists(enriched_path) else raw_path

    print(f"Chargement : {input_file}")

    with open(input_file, "r", encoding="utf-8") as f:
        papers = json.load(f)

    print(f"{len(papers)} papers charges — nettoyage en cours...")

    cleaned  = []
    skipped  = 0
    seen_ids = set()

    for paper in tqdm(papers, desc="Nettoyage"):
        result = clean_paper(paper)

        if result is None:
            skipped += 1
            continue

        # deduplication finale
        if result["arxiv_id"] in seen_ids:
            skipped += 1
            continue

        seen_ids.add(result["arxiv_id"])
        cleaned.append(result)

    os.makedirs(DATA_PROCESSED_PATH, exist_ok=True)
    output_path = os.path.join(DATA_PROCESSED_PATH, "cleaned_papers.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    print(f"\nNettoyage termine :")
    print(f"  Total traite  : {len(papers)}")
    print(f"  Papers nets   : {len(cleaned)}")
    print(f"  Ignores       : {skipped}")
    print(f"  Sauvegarde    : {output_path}")

    logger.info(f"Nettoyage termine — {len(cleaned)} papers nets, {skipped} ignores")
    return cleaned


if __name__ == "__main__":
    print("Demarrage du nettoyage...")
    cleaned = run_cleaning()
    print("Termine !")