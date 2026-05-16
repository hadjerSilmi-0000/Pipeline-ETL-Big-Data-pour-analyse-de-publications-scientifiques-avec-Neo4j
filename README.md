# Scientific Graph — Analyse de Publications Scientifiques

> Projet Big Data — Ing4 — Dr. Salmi Cheikh  
> Analyse de publications scientifiques basée sur les graphes avec Neo4j

---

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Collecte  | arXiv API, CrossRef API |
| Streaming | Apache Kafka 4.2.0 |
| Traitement | PySpark 3.5 |
| Graphe    | Neo4j AuraDB |
| ML / Bonus | TF-IDF (scikit-learn), Louvain (python-louvain), NetworkX |
| Dashboard | Streamlit + Plotly + PyVis |
| Runtime   | Python 3.10.9, Windows |

---

## Architecture du pipeline

```
arXiv API ──► arxiv_collector.py ──► all_papers.json (2389 papers)
                                         │
CrossRef API ◄── semantic_scholar.py ────┘
     │
     ▼
enriched_papers.json (500 papers)
     │
     ▼
cleaner.py ──► cleaned_papers.json (500 papers nets)
     │
     ▼
kafka_producer.py ──► [Kafka Topic: raw_papers]
                                │
                         kafka_consumer.py
                                │
                                ▼
                       spark_processor.py ──► spark_processed.json
                                │
                                ▼
                    schema.py + loader.py ──► Neo4j AuraDB
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
             recommender.py          community.py
          (SIMILAR_TO edges)    (community_id sur Authors)
                    │
                    ▼
            dashboard.py (Streamlit — 6 pages)
```

---

## Installation

```bash
# 1. Cloner le projet
git clone <repo>
cd scientific-graph

# 2. Creer l'environnement virtuel
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Installer les dependances
pip install -r requirements.txt
pip install python-louvain   # pour la detection de communautes

# 4. Configurer les variables d'environnement
cp .env.example .env
# Editer .env avec vos credentials Neo4j et Kafka
```

**`.env` :**
```env
NEO4J_URI=neo4j+ssc://<instance>.databases.neo4j.io
NEO4J_USER=<instance-id>
NEO4J_PASSWORD=<password>
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```

---

## Lancement

### Pipeline complet
```bash
# Demarrer Kafka d'abord (terminal separe)
C:\kafka\kafka_2.13-4.2.0\bin\windows\kafka-server-start.bat C:\kafka\kafka_2.13-4.2.0\config\server.properties

# Puis dans le venv :
python main.py
```

### Phases individuelles
```bash
python main.py --phase collect     # collecte arXiv + CrossRef
python main.py --phase process     # nettoyage + Kafka + Spark
python main.py --phase graph       # schema + chargement Neo4j
python main.py --phase analysis    # requetes + stats
python main.py --phase bonus       # recommandation + communautes
python main.py --phase dashboard   # lance Streamlit
```

### Sans recollecte (si donnees deja presentes)
```bash
python main.py --skip-collect
```

### Dashboard uniquement
```bash
streamlit run visualization/dashboard.py
# Ouvrir http://localhost:8501
```

---

## Structure du projet

```
scientific-graph/
├── config/
│   ├── settings.py          # variables d'environnement + constantes
│   └── logging_config.py    # logger unifie
├── collectors/
│   ├── arxiv_collector.py   # collecte via arXiv API (2389 papers)
│   └── semantic_scholar.py  # enrichissement CrossRef (500 papers)
├── processing/
│   ├── cleaner.py           # nettoyage + extraction keywords
│   ├── kafka_producer.py    # envoi vers Kafka
│   ├── kafka_consumer.py    # consommation Kafka
│   └── spark_processor.py   # traitement distribue PySpark
├── graph/
│   ├── schema.py            # contraintes + index Neo4j
│   ├── loader.py            # chargement des noeuds/relations
│   └── queries.py           # 9 fonctions de requetage Cypher
├── analysis/
│   ├── collaborations.py    # analyse du reseau de collaboration
│   ├── citations.py         # analyse des citations
│   └── topics.py            # analyse des topics
├── bonus/
│   ├── recommender.py       # systeme de recommandation TF-IDF
│   └── community.py         # detection de communautes (Louvain)
├── visualization/
│   └── dashboard.py         # Streamlit — 6 pages
├── tests/
│   ├── test_collectors.py
│   ├── test_processing.py
│   └── test_graph.py
├── data/
│   ├── raw/                 # papers bruts (git-ignored)
│   └── processed/           # papers traites (git-ignored)
├── main.py                  # orchestrateur CLI
└── requirements.txt
```

---

## Modele de graphe Neo4j

### Noeuds
| Label | Proprietes cles |
|-------|----------------|
| `Paper` | arxiv_id, title, abstract, year, citation_count, doi, pdf_url |
| `Author` | name, community_id |
| `Topic` | name |
| `Category` | name |
| `Community` | community_id, size |

### Relations
| Relation | Direction | Proprietes |
|----------|-----------|-----------|
| `WROTE` | Author → Paper | — |
| `HAS_TOPIC` | Paper → Topic | — |
| `BELONGS_TO` | Paper → Category | — |
| `COLLABORATED_WITH` | Author ↔ Author | count |
| `SIMILAR_TO` | Paper ↔ Paper | similarity (0–1) |
| `BELONGS_TO_COMMUNITY` | Author → Community | — |

---

## Stats du graphe (etat final)

```
papers               : 500
authors              : 2263
topics               : 2486
categories           : 86
collaborated         : 11605
similar_to           : 1500
community nodes      : ~N (selon Louvain)
```

---

## Dashboard — 6 pages

| Page | Description |
|------|-------------|
| Vue Generale | Metriques globales, distribution temporelle, top auteurs/topics |
| Reseau de Collaborations | Graphe interactif PyVis des co-auteurs |
| Topics & Tendances | Evolution temporelle des topics, tendances par annee |
| Recherche Auteur | Papers, collaborateurs et reseau d'un auteur |
| Recherche Topic | Papers lies a un topic, scatter citations vs annee |
| Communautes | Visualisation des communautes Louvain, recherche par auteur |

---

## Tests

```bash
# Tous les tests
python -m pytest tests/ -v

# Par module
python -m pytest tests/test_processing.py -v   # tests sans Neo4j
python -m pytest tests/test_graph.py -v        # necessite Neo4j actif
python -m pytest tests/test_collectors.py -v   # necessite connexion internet
```

---

## Notes importantes

- `venv\Scripts\activate` avant chaque session
- Kafka doit tourner dans un terminal separe avant `process` ou `--full`
- Neo4j AuraDB Free peut se mettre en pause apres inactivite — reveiller via le dashboard web
- Spark affiche des `SUCCESS: Process terminated` a la fin — comportement normal Windows
- `python-louvain` est requis pour la detection de communautes (fallback Girvan-Newman sinon)

---
