"""
Scientific Graph — Pipeline Orchestrateur
==========================================
Lance toutes les phases dans l'ordre ou individuellement.

Usage :
    python main.py                    # pipeline complet
    python main.py --phase collect    # collecte seulement
    python main.py --phase process    # nettoyage + kafka + spark
    python main.py --phase graph      # schema + chargement Neo4j
    python main.py --phase analysis   # requetes + stats
    python main.py --phase bonus      # recommandation + communautes
    python main.py --phase dashboard  # lance Streamlit
    python main.py --skip-collect     # tout sauf la collecte
"""

import os
import sys
import time
import argparse
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.logging_config import setup_logger

logger = setup_logger("main")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def step(msg: str):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {msg}...")


def ok(msg: str):
    print(f"  OK — {msg}")


def run_phase(name: str, fn, *args, **kwargs):
    """Execute une phase avec gestion d'erreur"""
    header(name)
    start = time.time()
    try:
        result = fn(*args, **kwargs)
        elapsed = time.time() - start
        print(f"\n  Phase '{name}' terminee en {elapsed:.1f}s")
        logger.info(f"Phase '{name}' OK en {elapsed:.1f}s")
        return result
    except Exception as e:
        print(f"\n  ERREUR dans '{name}' : {e}")
        logger.error(f"Phase '{name}' ERREUR : {e}", exc_info=True)
        raise


# ─── Phases ──────────────────────────────────────────────────────────────────

def phase_collect():
    """Phase 2 + 3 : Collecte arXiv + enrichissement CrossRef"""
    from collectors.arxiv_collector import run_arxiv_collection
    from collectors.semantic_scholar import run_crossref_collection

    step("Collecte arXiv")
    papers = run_arxiv_collection()
    ok(f"{len(papers)} papers collectes depuis arXiv")

    step("Enrichissement CrossRef")
    enriched = run_crossref_collection()
    ok(f"{len(enriched)} papers enrichis via CrossRef")

    return enriched


def phase_process():
    """Phase 4 + 5 : Nettoyage + Kafka + Spark"""
    from processing.cleaner import run_cleaning
    from processing.kafka_producer import send_papers
    from processing.kafka_consumer import consume_papers
    from processing.spark_processor import process_papers
    import json
    from config.settings import DATA_PROCESSED_PATH

    step("Nettoyage des papers")
    cleaned = run_cleaning()
    ok(f"{len(cleaned)} papers nets")

    step("Envoi vers Kafka (producer)")
    sent = send_papers()
    ok(f"{sent} messages envoyes")

    step("Consommation Kafka (consumer)")
    consumed = consume_papers(max_messages=len(cleaned))
    ok(f"{len(consumed)} messages reçus")

    step("Traitement Spark")
    input_path = os.path.join(DATA_PROCESSED_PATH, "cleaned_papers.json")
    with open(input_path, "r", encoding="utf-8") as f:
        papers = json.load(f)
    processed = process_papers(papers)
    ok(f"{len(processed)} papers traites par Spark")

    return processed


def phase_graph():
    """Phase 6 + 7 : Schema Neo4j + Chargement"""
    from graph.schema import init_schema
    from graph.loader import run_loading

    step("Initialisation schema Neo4j")
    init_schema()
    ok("Contraintes et index crees")

    step("Chargement des donnees dans Neo4j")
    stats = run_loading()
    ok(f"Graphe charge : {stats}")

    return stats


def phase_analysis():
    """Phase 8 : Requetes et statistiques"""
    from graph.queries import (
        get_most_prolific_authors,
        get_most_cited_papers,
        get_top_topics,
        get_papers_by_year,
        get_category_distribution,
        get_collaboration_network
    )

    step("Calcul des statistiques du graphe")

    print("\n  Top 5 auteurs prolifiques :")
    for r in get_most_prolific_authors(5):
        print(f"    {r['author']:<35} {r['papers']} papers")

    print("\n  Top 5 papers cites :")
    for r in get_most_cited_papers(5):
        print(f"    {r['title'][:50]:<50} {r['citations']} citations")

    print("\n  Top 5 topics :")
    for r in get_top_topics(5):
        print(f"    {r['topic']:<25} {r['papers']} papers")

    print("\n  Distribution par annee (5 dernieres) :")
    for r in get_papers_by_year()[:5]:
        print(f"    {r['year']} : {r['papers']} papers")

    ok("Analyse terminee")


def phase_bonus():
    """Phase 10 + 11 : Recommandation + Communautes"""
    from bonus.recommender import run_recommender
    from bonus.community import run_community_detection

    step("Systeme de recommandation TF-IDF")
    papers, tfidf = run_recommender()
    ok(f"Relations SIMILAR_TO stockees dans Neo4j")

    step("Detection de communautes (Louvain)")
    result = run_community_detection()
    if result:
        ok(f"{result['n_communities']} communautes detectees")
    else:
        print("  ATTENTION : detection de communautes echouee ou graphe vide")

    return result


def phase_dashboard():
    """Lance le dashboard Streamlit"""
    import subprocess
    header("Dashboard Streamlit")
    print("  Lancement de : streamlit run visualization/dashboard.py")
    print("  Ouvrir http://localhost:8501 dans le navigateur")
    print("  Ctrl+C pour arreter\n")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "visualization/dashboard.py"])


# ─── Pipeline complet ─────────────────────────────────────────────────────────

def run_full_pipeline(skip_collect: bool = False):
    """Lance toutes les phases dans l'ordre"""
    start = time.time()
    print("\n" + "=" * 60)
    print("  SCIENTIFIC GRAPH — PIPELINE COMPLET")
    print(f"  Debut : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    phases = []

    if not skip_collect:
        phases.append(("Collecte (arXiv + CrossRef)", phase_collect))

    phases += [
        ("Traitement (nettoyage + Kafka + Spark)", phase_process),
        ("Graphe Neo4j (schema + chargement)",     phase_graph),
        ("Analyse (requetes + stats)",              phase_analysis),
        ("Bonus (recommandation + communautes)",    phase_bonus),
    ]

    results = {}
    for name, fn in phases:
        try:
            results[name] = run_phase(name, fn)
        except Exception as e:
            print(f"\nPipeline interrompu a la phase '{name}' : {e}")
            print("Relancer avec --phase <nom> pour reprendre depuis cette phase.")
            sys.exit(1)

    elapsed = time.time() - start
    print("\n" + "=" * 60)
    print(f"  PIPELINE COMPLET TERMINE en {elapsed:.0f}s")
    print(f"  Fin : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print("\nLancer le dashboard avec : streamlit run visualization/dashboard.py")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scientific Graph — Pipeline Orchestrateur",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--phase",
        choices=["collect", "process", "graph", "analysis", "bonus", "dashboard"],
        help="Lancer une phase specifique uniquement"
    )
    parser.add_argument(
        "--skip-collect",
        action="store_true",
        help="Lancer le pipeline complet sans la collecte (si donnees deja presentes)"
    )

    args = parser.parse_args()

    if args.phase:
        phase_map = {
            "collect"   : phase_collect,
            "process"   : phase_process,
            "graph"     : phase_graph,
            "analysis"  : phase_analysis,
            "bonus"     : phase_bonus,
            "dashboard" : phase_dashboard,
        }
        run_phase(args.phase, phase_map[args.phase])
    else:
        run_full_pipeline(skip_collect=args.skip_collect)


if __name__ == "__main__":
    main()