import arxiv
import json
import os
import time
from datetime import datetime
from tqdm import tqdm

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    ARXIV_MAX_RESULTS,
    ARXIV_SEARCH_QUERIES,
    DATA_RAW_PATH
)
from config.logging_config import setup_logger

logger = setup_logger("arxiv_collector")


def collect_papers(query: str, max_results: int = ARXIV_MAX_RESULTS) -> list[dict]:
    print(f"Collecte en cours : '{query}'...")
    logger.info(f"Collecte arXiv — query: '{query}' — max: {max_results}")

    client = arxiv.Client(
        page_size=100,
        delay_seconds=3,
        num_retries=3
    )

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance
    )

    papers = []

    for result in tqdm(client.results(search), total=max_results, desc=f"arXiv: {query}"):
        paper = {
            "arxiv_id"    : result.entry_id.split("/")[-1],
            "title"       : result.title.strip(),
            "abstract"    : result.summary.strip(),
            "authors"     : [a.name for a in result.authors],
            "categories"  : result.categories,
            "published"   : result.published.strftime("%Y-%m-%d") if result.published else None,
            "updated"     : result.updated.strftime("%Y-%m-%d") if result.updated else None,
            "doi"         : result.doi,
            "pdf_url"     : result.pdf_url,
            "query"       : query,
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        papers.append(paper)

    print(f"{len(papers)} papers collectes pour '{query}'")
    logger.info(f"{len(papers)} papers collectes pour '{query}'")
    return papers


def save_papers(papers: list[dict], query: str) -> str:
    os.makedirs(DATA_RAW_PATH, exist_ok=True)

    filename = query.replace(" ", "_") + ".json"
    filepath = os.path.join(DATA_RAW_PATH, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)

    print(f"Sauvegarde : {filepath}")
    logger.info(f"Sauvegarde : {filepath} ({len(papers)} papers)")
    return filepath


def run_arxiv_collection() -> list[dict]:
    all_papers = []
    seen_ids   = set()

    for query in ARXIV_SEARCH_QUERIES:
        papers = collect_papers(query)

        unique = []
        for p in papers:
            if p["arxiv_id"] not in seen_ids:
                seen_ids.add(p["arxiv_id"])
                unique.append(p)

        save_papers(unique, query)
        all_papers.extend(unique)

        print(f"Total unique jusqu'ici : {len(all_papers)}")
        time.sleep(2)

    global_path = os.path.join(DATA_RAW_PATH, "all_papers.json")
    with open(global_path, "w", encoding="utf-8") as f:
        json.dump(all_papers, f, ensure_ascii=False, indent=2)

    print(f"Collection terminee — {len(all_papers)} papers uniques au total")
    return all_papers


if __name__ == "__main__":
    print("Demarrage de la collection arXiv...")
    papers = run_arxiv_collection()
    print(f"Total collecte : {len(papers)} papers")
    print("Termine !")