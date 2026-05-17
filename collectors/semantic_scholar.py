import requests
import json
import os
import time
from tqdm import tqdm

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    SEMANTIC_SCHOLAR_API_KEY,
    MAX_CITATIONS_PER_PAPER,
    DATA_RAW_PATH
)
from config.logging_config import setup_logger

logger = setup_logger("semantic_scholar")

BASE_URL = "https://api.semanticscholar.org/graph/v1"
HEADERS  = {"x-api-key": SEMANTIC_SCHOLAR_API_KEY}
DELAY    = 1.2


def clean_arxiv_id(arxiv_id: str) -> str:
    """Supprime la version de l'arxiv_id — S2 n'accepte pas 'v1', 'v2' etc."""
    import re
    return re.sub(r"v\d+$", "", arxiv_id.strip())


def get_paper_full(arxiv_id: str, retries: int = 3) -> dict | None:
    """Recupere details + citations + references en une seule requete S2"""
    clean_id = clean_arxiv_id(arxiv_id)
    url      = f"{BASE_URL}/paper/arXiv:{clean_id}"
    params   = {
        "fields": (
            "paperId,title,year,citationCount,referenceCount,"
            "influentialCitationCount,venue,"
            "citations.paperId,citations.title,citations.year,citations.externalIds,"
            "references.paperId,references.title,references.year,references.externalIds"
        )
    }

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=20)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.debug(f"Paper non trouve sur S2 : {clean_id}")
                return None
            elif response.status_code == 429:
                wait = 20 + attempt * 10
                logger.warning(f"Rate limit — pause {wait}s")
                time.sleep(wait)
                continue
            elif response.status_code == 403:
                logger.error("API key invalide")
                return None
            else:
                logger.warning(f"Status {response.status_code} pour {clean_id}")
                return None

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout attempt {attempt+1} pour {clean_id}")
            time.sleep(5)
            continue
        except requests.exceptions.ConnectionError:
            wait = 30 + attempt * 15
            logger.warning(f"Connexion perdue — pause {wait}s (attempt {attempt+1})")
            time.sleep(wait)
            continue
        except Exception as e:
            logger.error(f"Erreur {clean_id} : {e}")
            return None

    return None


def extract_arxiv_id_from_external(external_ids: dict) -> str:
    if not external_ids:
        return ""
    return external_ids.get("ArXiv", "")


def enrich_papers(papers: list[dict], max_papers: int = 500,
                  checkpoint_file: str = None) -> list[dict]:
    """
    Enrichit les papers arXiv avec S2.
    Sauvegarde un checkpoint toutes les 50 papers pour reprendre en cas d'interruption.
    """
    sample    = papers[:max_papers]
    enriched  = []
    found     = 0
    not_found = 0

    # charger checkpoint si existe
    start_idx = 0
    if checkpoint_file and os.path.exists(checkpoint_file):
        with open(checkpoint_file, "r", encoding="utf-8") as f:
            enriched = json.load(f)
        start_idx = len(enriched)
        print(f"Reprise depuis le checkpoint — {start_idx} papers deja traites")

    for i, paper in enumerate(tqdm(sample[start_idx:], desc="Enrichissement S2",
                                   initial=start_idx, total=max_papers)):
        arxiv_id = paper.get("arxiv_id", "")
        if not arxiv_id:
            enriched.append({**paper, "s2_data": None})
            continue

        data = get_paper_full(arxiv_id)
        time.sleep(DELAY)

        if data is None:
            not_found += 1
            enriched.append({**paper, "s2_data": None})
        else:
            found += 1
            raw_citations  = data.get("citations", [])  or []
            raw_references = data.get("references", []) or []

            citations = []
            for c in raw_citations[:MAX_CITATIONS_PER_PAPER]:
                citing = c.get("citingPaper") or c
                citations.append({
                    "paperId"  : citing.get("paperId", ""),
                    "title"    : citing.get("title", ""),
                    "year"     : citing.get("year"),
                    "arxiv_id" : extract_arxiv_id_from_external(
                                     citing.get("externalIds", {}))
                })

            references = []
            for r in raw_references[:MAX_CITATIONS_PER_PAPER]:
                cited = r.get("citedPaper") or r
                references.append({
                    "paperId"  : cited.get("paperId", ""),
                    "title"    : cited.get("title", ""),
                    "year"     : cited.get("year"),
                    "arxiv_id" : extract_arxiv_id_from_external(
                                     cited.get("externalIds", {}))
                })

            enriched.append({
                **paper,
                "s2_data": {
                    "s2_id"                      : data.get("paperId", ""),
                    "citation_count"             : data.get("citationCount", 0) or 0,
                    "reference_count"            : data.get("referenceCount", 0) or 0,
                    "influential_citation_count" : data.get("influentialCitationCount", 0) or 0,
                    "venue"                      : data.get("venue", "") or "",
                    "citations"                  : citations,
                    "references"                 : references
                }
            })

        # checkpoint toutes les 50 papers
        if checkpoint_file and (i + 1) % 50 == 0:
            with open(checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(enriched, f, ensure_ascii=False)
            print(f"  Checkpoint sauvegarde — {len(enriched)} papers | "
                  f"trouves={found} non_trouves={not_found}")

    logger.info(f"Enrichissement termine — {found} trouves, {not_found} non trouves")
    print(f"\nResultats : {found} trouves sur S2, {not_found} non trouves")
    return enriched


def run_semantic_scholar_collection(input_file: str = None) -> list[dict]:
    """Pipeline complet"""
    if input_file is None:
        input_file = os.path.join(DATA_RAW_PATH, "all_papers.json")

    checkpoint = os.path.join(DATA_RAW_PATH, "enriched_checkpoint.json")

    print(f"Chargement : {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        papers = json.load(f)

    print(f"{len(papers)} papers charges")
    print(f"API Key  : {SEMANTIC_SCHOLAR_API_KEY[:12]}...")
    print(f"Checkpoint : {checkpoint}")
    print(f"Duree estimee : ~{500 * DELAY / 60:.0f} minutes\n")

    enriched = enrich_papers(papers, max_papers=500, checkpoint_file=checkpoint)

    output_path = os.path.join(DATA_RAW_PATH, "enriched_papers.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    # supprimer checkpoint
    if os.path.exists(checkpoint):
        os.remove(checkpoint)

    print(f"Sauvegarde : {output_path}")
    logger.info(f"Enrichissement sauvegarde — {len(enriched)} papers")
    return enriched


if __name__ == "__main__":
    print("Demarrage enrichissement Semantic Scholar...")
    enriched = run_semantic_scholar_collection()
    print(f"Total enrichi : {len(enriched)} papers")
    print("Termine !")