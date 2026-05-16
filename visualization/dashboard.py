import os
import sys
import streamlit as st
import plotly.express as px
import pandas as pd
import tempfile
import networkx as nx
from pyvis.network import Network

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph.queries import (
    get_most_prolific_authors,
    get_most_cited_papers,
    get_top_topics,
    get_collaboration_network,
    get_papers_by_year,
    get_topics_by_year,
    get_author_collaborators,
    get_author_papers,
    get_category_distribution,
    get_papers_by_topic
)
from graph.schema import get_driver, get_graph_stats

# ─── Config page ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Scientific Graph Explorer",
    page_icon="🔬",
    layout="wide"
)

st.title("🔬 Scientific Graph Explorer")
st.markdown("Analyse des publications scientifiques via Neo4j")
st.divider()

# ─── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.title("Navigation")
page = st.sidebar.selectbox("Choisir une vue", [
    "Vue Generale",
    "Reseau de Collaborations",
    "Topics & Tendances",
    "Recherche Auteur",
    "Recherche Topic",
    "Communautes de Chercheurs",  # ← PAGE 6 (Phase 11)
])

# ─── PAGE 1 : Vue Generale ───────────────────────────────────────────────────
if page == "Vue Generale":
    st.header("Vue Generale")

    driver = get_driver()
    with driver.session() as session:
        stats = get_graph_stats(session)
    driver.close()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Papers",         stats["papers"])
    col2.metric("Auteurs",        stats["authors"])
    col3.metric("Topics",         stats["topics"])
    col4.metric("Collaborations", stats["collaborated"])

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Publications par annee")
        by_year = get_papers_by_year()
        df_year = pd.DataFrame(by_year)
        if not df_year.empty:
            fig = px.bar(
                df_year.head(15),
                x="year", y="papers",
                color="papers",
                color_continuous_scale="Blues",
                labels={"year": "Annee", "papers": "Nombre de papers"}
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Top 10 Categories arXiv")
        cats = get_category_distribution()
        df_cat = pd.DataFrame(cats[:10])
        if not df_cat.empty:
            fig = px.pie(
                df_cat,
                names="category",
                values="papers",
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top 10 Auteurs les plus prolifiques")
    df_authors = pd.DataFrame(get_most_prolific_authors(10))
    if not df_authors.empty:
        fig = px.bar(
            df_authors,
            x="papers", y="author",
            orientation="h",
            color="papers",
            color_continuous_scale="Viridis",
            labels={"papers": "Nombre de papers", "author": "Auteur"}
        )
        fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top 10 Topics globaux")
    df_topics = pd.DataFrame(get_top_topics(10))
    if not df_topics.empty:
        fig = px.bar(
            df_topics,
            x="papers", y="topic",
            orientation="h",
            color="papers",
            color_continuous_scale="Turbo",
            labels={"papers": "Nombre de papers", "topic": "Topic"}
        )
        fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

# ─── PAGE 2 : Reseau de Collaborations ───────────────────────────────────────
elif page == "Reseau de Collaborations":
    st.header("Reseau de Collaborations")

    limit = st.slider("Nombre de collaborations a afficher", 20, 200, 50)
    collabs = get_collaboration_network(limit=limit)

    if not collabs:
        st.warning("Aucune collaboration trouvee.")
    else:
        G = nx.Graph()
        for r in collabs:
            G.add_edge(r["author1"], r["author2"], weight=r["collaborations"])

        st.info(f"Noeuds : {G.number_of_nodes()} auteurs | Aretes : {G.number_of_edges()} collaborations")

        net = Network(height="600px", width="100%", bgcolor="#0e1117", font_color="white")
        net.from_nx(G)

        for node in net.nodes:
            degree = G.degree(node["id"])
            node["size"]  = 10 + degree * 3
            node["title"] = f"{node['id']} ({degree} collaborateurs)"
            node["color"] = "#4FC3F7"

        for edge in net.edges:
            edge["width"] = edge.get("weight", 1)
            edge["color"] = "#555555"

        net.set_options("""
        {
          "physics": {
            "forceAtlas2Based": {
              "gravitationalConstant": -50,
              "centralGravity": 0.01,
              "springLength": 100
            },
            "solver": "forceAtlas2Based"
          }
        }
        """)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
            net.save_graph(f.name)
            html_content = open(f.name, "r", encoding="utf-8").read()

        st.components.v1.html(html_content, height=620, scrolling=True)

        st.subheader("Top collaborations")
        df = pd.DataFrame(collabs[:20])
        st.dataframe(df, use_container_width=True)

# ─── PAGE 3 : Topics & Tendances ─────────────────────────────────────────────
elif page == "Topics & Tendances":
    st.header("Topics & Tendances")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top 20 Topics globaux")
        topics = get_top_topics(limit=20)
        df = pd.DataFrame(topics)
        if not df.empty:
            fig = px.bar(
                df, x="papers", y="topic",
                orientation="h",
                color="papers",
                color_continuous_scale="Turbo",
                labels={"papers": "Nombre de papers", "topic": "Topic"}
            )
            fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False, height=600)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Topics par annee")
        years = list(range(2026, 2009, -1))
        selected_year = st.selectbox("Selectionner une annee", years)
        topics_year = get_topics_by_year(selected_year, limit=15)
        df_y = pd.DataFrame(topics_year)
        if not df_y.empty:
            fig = px.bar(
                df_y, x="papers", y="topic",
                orientation="h",
                color="papers",
                color_continuous_scale="Plasma",
                labels={"papers": "Nombre de papers", "topic": "Topic"}
            )
            fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False, height=500)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"Pas de topics pour {selected_year}")

    st.subheader("Evolution des topics dans le temps")
    top5 = [r["topic"] for r in get_top_topics(5)]
    by_year = get_papers_by_year()
    years_list = [r["year"] for r in by_year if r["year"]]

    trend_data = []
    for y in sorted(years_list):
        topics_y = get_topics_by_year(y, limit=50)
        for t in topics_y:
            if t["topic"] in top5:
                trend_data.append({"year": y, "topic": t["topic"], "papers": t["papers"]})

    if trend_data:
        df_trend = pd.DataFrame(trend_data)
        fig = px.line(
            df_trend, x="year", y="papers",
            color="topic",
            markers=True,
            labels={"year": "Annee", "papers": "Nombre de papers", "topic": "Topic"}
        )
        st.plotly_chart(fig, use_container_width=True)

# ─── PAGE 4 : Recherche Auteur ────────────────────────────────────────────────
elif page == "Recherche Auteur":
    st.header("Recherche par Auteur")

    author_input = st.text_input("Nom de l'auteur", placeholder="ex: Bengio")

    if author_input:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Papers publies")
            papers = get_author_papers(author_input)
            if papers:
                df = pd.DataFrame(papers)
                st.dataframe(df, use_container_width=True)
                st.info(f"{len(papers)} papers trouves")
            else:
                st.warning("Aucun paper trouve pour cet auteur.")

        with col2:
            st.subheader("Collaborateurs")
            collabs = get_author_collaborators(author_input)
            if collabs:
                df_c = pd.DataFrame(collabs)
                fig = px.bar(
                    df_c.head(15),
                    x="shared_papers", y="collaborator",
                    orientation="h",
                    color="shared_papers",
                    color_continuous_scale="Blues",
                    labels={"shared_papers": "Papers communs", "collaborator": "Collaborateur"}
                )
                fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Aucun collaborateur trouve.")

        st.subheader("Reseau de collaborations")
        if collabs:
            G = nx.Graph()
            G.add_node(author_input)
            for c in collabs[:20]:
                G.add_edge(author_input, c["collaborator"], weight=c["shared_papers"])

            net = Network(height="400px", width="100%", bgcolor="#0e1117", font_color="white")
            net.from_nx(G)

            for node in net.nodes:
                if node["id"] == author_input:
                    node["color"] = "#FF6B6B"
                    node["size"]  = 30
                else:
                    node["color"] = "#4FC3F7"
                    node["size"]  = 15

            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
                net.save_graph(f.name)
                html_content = open(f.name, "r", encoding="utf-8").read()

            st.components.v1.html(html_content, height=420, scrolling=True)

# ─── PAGE 5 : Recherche Topic ────────────────────────────────────────────────
elif page == "Recherche Topic":
    st.header("Recherche par Topic")

    topic_input = st.text_input("Topic", placeholder="ex: neural")

    if topic_input:
        st.subheader(f"Papers lies a '{topic_input}'")
        papers = get_papers_by_topic(topic_input, limit=20)
        if papers:
            df = pd.DataFrame(papers)
            st.dataframe(df, use_container_width=True)

            col1, col2 = st.columns(2)

            with col1:
                fig = px.scatter(
                    df,
                    x="year", y="citations",
                    hover_data=["title"],
                    size_max=30,
                    color="citations",
                    color_continuous_scale="Viridis",
                    labels={"year": "Annee", "citations": "Citations"}
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig2 = px.histogram(
                    df, x="year",
                    nbins=15,
                    color_discrete_sequence=["#4FC3F7"],
                    labels={"year": "Annee", "count": "Nombre de papers"}
                )
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.warning(f"Aucun paper trouve pour '{topic_input}'")

# ─── PAGE 6 : Communautes de Chercheurs ──────────────────────────────────────
elif page == "Communautes de Chercheurs":
    st.header("🧩 Communautes de Chercheurs")
    st.markdown("Detection de communautes via l'algorithme de **Louvain** sur le reseau de collaborations.")

    # verifier si les communautes sont deja calculees
    from bonus.community import get_communities_from_neo4j, get_author_community

    communities_data = get_communities_from_neo4j(limit=50)

    if not communities_data:
        st.warning("Aucune communaute detectee dans Neo4j.")
        st.info("Lancer d'abord : `python bonus/community.py`")
        if st.button("Lancer la detection maintenant"):
            with st.spinner("Detection en cours (peut prendre quelques minutes)..."):
                from bonus.community import run_community_detection
                result = run_community_detection()
                if result:
                    st.success(f"{result['n_communities']} communautes detectees !")
                    st.rerun()
                else:
                    st.error("Echec de la detection. Verifier les logs.")
    else:
        # ── Stats globales
        total_authors = sum(c["size"] for c in communities_data)
        n_comm        = len(communities_data)

        col1, col2, col3 = st.columns(3)
        col1.metric("Communautes detectees", n_comm)
        col2.metric("Auteurs assignes",      total_authors)
        col3.metric("Taille moyenne",        f"{total_authors / n_comm:.1f}" if n_comm else "—")

        st.divider()

        # ── Distribution des tailles
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Taille des communautes")
            df_comm = pd.DataFrame(communities_data)
            df_comm["community_label"] = df_comm["community_id"].apply(lambda x: f"Comm #{x}")

            fig = px.bar(
                df_comm.head(20),
                x="size", y="community_label",
                orientation="h",
                color="size",
                color_continuous_scale="Viridis",
                labels={"size": "Nombre de membres", "community_label": "Communaute"}
            )
            fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False, height=500)
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            st.subheader("Repartition des membres")
            fig2 = px.pie(
                df_comm.head(15),
                names="community_label",
                values="size",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig2.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig2, use_container_width=True)

        # ── Top membres par communaute
        st.subheader("Top membres par communaute")
        for comm in communities_data[:10]:
            members_preview = comm.get("top_members", [])
            with st.expander(f"Communaute #{comm['community_id']} — {comm['size']} membres"):
                if members_preview:
                    st.write(", ".join(members_preview))
                else:
                    st.write("Aucun membre disponible")

        # ── Visualisation graphe colore par communaute
        st.subheader("Reseau colore par communaute")
        n_collab = st.slider("Collaborations a afficher", 30, 150, 60)

        driver = get_driver()
        query = """
        MATCH (a1:Author)-[r:COLLABORATED_WITH]-(a2:Author)
        WHERE id(a1) < id(a2)
          AND a1.community_id IS NOT NULL
          AND a2.community_id IS NOT NULL
        RETURN a1.name AS author1, a1.community_id AS comm1,
               a2.name AS author2, a2.community_id AS comm2,
               r.count AS weight
        ORDER BY r.count DESC
        LIMIT $limit
        """
        with driver.session() as session:
            rows = [dict(r) for r in session.run(query, limit=n_collab)]
        driver.close()

        if rows:
            # palette de couleurs par communaute
            comm_ids = list(set([r["comm1"] for r in rows] + [r["comm2"] for r in rows]))
            palette  = px.colors.qualitative.Plotly + px.colors.qualitative.Safe
            color_map = {cid: palette[i % len(palette)] for i, cid in enumerate(sorted(comm_ids))}

            G = nx.Graph()
            node_comm = {}
            for r in rows:
                G.add_edge(r["author1"], r["author2"], weight=r["weight"])
                node_comm[r["author1"]] = r["comm1"]
                node_comm[r["author2"]] = r["comm2"]

            net = Network(height="600px", width="100%", bgcolor="#0e1117", font_color="white")
            net.from_nx(G)

            for node in net.nodes:
                nid    = node["id"]
                comm   = node_comm.get(nid, 0)
                degree = G.degree(nid)
                node["size"]  = 10 + degree * 2
                node["color"] = color_map.get(comm, "#888888")
                node["title"] = f"{nid}\nCommunaute #{comm}"

            for edge in net.edges:
                edge["color"] = "#333333"
                edge["width"] = max(1, edge.get("weight", 1) * 0.5)

            net.set_options("""
            {
              "physics": {
                "forceAtlas2Based": {
                  "gravitationalConstant": -60,
                  "centralGravity": 0.01,
                  "springLength": 120
                },
                "solver": "forceAtlas2Based"
              }
            }
            """)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
                net.save_graph(f.name)
                html_content = open(f.name, "r", encoding="utf-8").read()

            st.components.v1.html(html_content, height=620, scrolling=True)
            st.caption("Chaque couleur represente une communaute distincte detectee par Louvain.")
        else:
            st.info("Pas assez de donnees pour la visualisation. "
                    "Verifier que community_id est bien stocke sur les auteurs.")

        # ── Recherche par auteur
        st.divider()
        st.subheader("Trouver la communaute d'un auteur")
        author_search = st.text_input("Nom de l'auteur", placeholder="ex: LeCun")

        if author_search:
            result = get_author_community(author_search)
            if result:
                st.success(f"L'auteur appartient a la **Communaute #{result['community_id']}** "
                           f"({result['community_size']} membres)")
                st.write("Membres de la communaute (extrait) :")
                st.write(", ".join(result["members"]))
            else:
                st.warning("Auteur non trouve ou pas encore assigne a une communaute.")