import os
import sys
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import networkx as nx

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
    get_papers_by_topic,
)
from graph.schema import get_driver, get_graph_stats

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Scientific Graph Explorer",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: #FFFFFF;
    color: #1A0030;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #000000 !important;
    border-right: 1.5px solid #2A2A2A;
}

section[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
}

section[data-testid="stSidebar"] .stSelectbox > div > div {
    background: #111111 !important;
    border: 1px solid #333333 !important;
    color: #FFFFFF !important;
}

/* Selectbox dropdown */
div[data-baseweb="popover"] {
    background-color: #111111 !important;
}

div[data-baseweb="popover"] * {
    color: #FFFFFF !important;
}
/* Header */
.sg-header {
    background: linear-gradient(135deg, #9112BC 0%, #AE75DA 100%);
    padding: 28px 36px;
    border-radius: 12px;
    margin-bottom: 28px;
}
.sg-header h1 {
    font-family: 'DM Serif Display', serif;
    color: #FFFCB8;
    font-size: 2rem;
    margin: 0;
    letter-spacing: -0.5px;
}

/* Metrics */
div[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 2px solid #AE75DA;
    border-radius: 10px;
    padding: 16px 20px;
}
div[data-testid="stMetric"] label {
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: #9112BC !important;
    font-weight: 600 !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-family: 'DM Serif Display', serif;
    color: #9112BC !important;
    font-size: 2rem !important;
}

/* Section titles */
.section-title {
    font-family: 'DM Serif Display', serif;
    font-size: 1.15rem;
    color: #9112BC;
    margin: 20px 0 10px 0;
    padding-bottom: 6px;
    border-bottom: 2px solid #AE75DA;
    display: inline-block;
}

/* Paper cards */
.paper-card {
    background: #FFFFFF;
    border: 1.5px solid #AE75DA;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 10px;
    transition: border-color 0.15s, box-shadow 0.15s;
}
.paper-card:hover {
    border-color: #9112BC;
    box-shadow: 0 4px 12px rgba(145,18,188,0.12);
}
.paper-title {
    font-family: 'DM Serif Display', serif;
    font-size: 0.95rem;
    color: #9112BC;
    margin-bottom: 6px;
}
.paper-badge {
    display: inline-block;
    background: #FFFFFF;
    color: #9112BC;
    border: 1px solid #AE75DA;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 12px;
    margin-right: 5px;
}

/* Divider */
.sg-divider { border: none; border-top: 1.5px solid #AE75DA; margin: 18px 0; }

/* Author pill */
.author-pill {
    display: inline-block;
    background: #FFACAC;
    color: #1A0030;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 16px;
    margin: 3px;
}

/* Charts container */
.stPlotlyChart {
    border: 1.5px solid #AE75DA;
    border-radius: 10px;
    overflow: hidden;
    background: #FFFFFF;
}

/* DataFrame */
.stDataFrame { border: 1.5px solid #AE75DA; border-radius: 8px; }

/* Tabs */
button[data-baseweb="tab"] {
    font-family: 'DM Sans', sans-serif;
    font-weight: 600;
    color: #AE75DA !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #9112BC !important;
    border-bottom-color: #9112BC !important;
}

/* Slider */
div[data-testid="stSlider"] * { color: #9112BC !important; }
div[data-testid="stSlider"] [data-testid="stThumbValue"] {
    background: #000000 !important; color: #FFFCB8 !important;
}

/* Expander */
details { border: 1.5px solid #AE75DA !important; border-radius: 8px !important; }
summary { color: #9112BC !important; font-weight: 600 !important; }

/* Block container */
.block-container { padding-top: 1rem !important; }

/* Warning / info boxes */
div[data-testid="stAlert"] { border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)

# ─── Plotly theme ─────────────────────────────────────────────────────────────
PL = dict(
    font_family="DM Sans",
    paper_bgcolor="#FFFFFF",
    plot_bgcolor="#FFFFFF",
    margin=dict(l=12, r=12, t=28, b=12),
    coloraxis_showscale=False,
)
PURPLES = ["#F3E6FA", "#D9AEF0", "#AE75DA", "#9112BC", "#5A0078"]
ACCENT  = "#FFACAC"

# ─── Header ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="sg-header">
  <h1>Scientific Graph Explorer</h1>
</div>
""", unsafe_allow_html=True)

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Navigation")
    page = st.selectbox("Page", [
        "Overview",
        "Collaboration Network",
        "Topics & Trends",
        "Author Search",
        "Topic Search",
        "Research Communities",
    ], label_visibility="collapsed")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
if page == "Overview":

    driver = get_driver()
    with driver.session() as session:
        stats = get_graph_stats(session)
    driver.close()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Papers",         f"{stats['papers']:,}")
    c2.metric("Authors",        f"{stats['authors']:,}")
    c3.metric("Topics",         f"{stats['topics']:,}")
    c4.metric("Collaborations", f"{stats['collaborated']:,}")
    c5.metric("Citations",      f"{stats['cites']:,}")

    st.markdown("<hr class='sg-divider'>", unsafe_allow_html=True)

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("<div class='section-title'>Publications by Year</div>", unsafe_allow_html=True)
        df_year = pd.DataFrame(get_papers_by_year()).head(15)
        if not df_year.empty:
            fig = px.bar(df_year, x="year", y="papers",
                         color="papers", color_continuous_scale=PURPLES)
            fig.update_layout(**PL, xaxis_title="Year", yaxis_title="Papers", height=300)
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("<div class='section-title'>arXiv Categories</div>", unsafe_allow_html=True)
        df_cat = pd.DataFrame(get_category_distribution()[:10])
        if not df_cat.empty:
            fig = px.pie(df_cat, names="category", values="papers",
                         color_discrete_sequence=PURPLES + [ACCENT])
            fig.update_layout(**PL, height=300)
            fig.update_traces(textposition="inside", textinfo="percent+label", textfont_size=10)
            st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("<div class='section-title'>Most Prolific Authors</div>", unsafe_allow_html=True)
        df_auth = pd.DataFrame(get_most_prolific_authors(12))
        if not df_auth.empty:
            fig = px.bar(df_auth, x="papers", y="author", orientation="h",
                         color="papers", color_continuous_scale=PURPLES)
            fig.update_layout(**PL, yaxis=dict(autorange="reversed"),
                              xaxis_title="Papers", yaxis_title="", height=380)
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.markdown("<div class='section-title'>Top Topics</div>", unsafe_allow_html=True)
        df_top = pd.DataFrame(get_top_topics(12))
        if not df_top.empty:
            fig = px.bar(df_top, x="papers", y="topic", orientation="h",
                         color="papers", color_continuous_scale=PURPLES)
            fig.update_layout(**PL, yaxis=dict(autorange="reversed"),
                              xaxis_title="Papers", yaxis_title="", height=380)
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("<div class='section-title'>Most Cited Papers</div>", unsafe_allow_html=True)
    for r in get_most_cited_papers(10):
        st.markdown(f"""
        <div class="paper-card">
            <div class="paper-title">{r['title'][:120]}</div>
            <div>
                <span class="paper-badge">{r.get('year','—')}</span>
                <span class="paper-badge">{r['citations']:,} citations</span>
                <span class="paper-badge">arXiv:{r['arxiv_id']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — COLLABORATION NETWORK
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Collaboration Network":
    st.markdown("<div class='section-title'>Author Collaboration Network</div>", unsafe_allow_html=True)

    limit   = st.slider("Number of collaborations to display", 20, 200, 60)
    collabs = get_collaboration_network(limit=limit)

    if not collabs:
        st.warning("No collaborations found.")
    else:
        G = nx.Graph()
        for r in collabs:
            G.add_edge(r["author1"], r["author2"], weight=r["collaborations"])

        col_i, col_ii = st.columns([2, 1])

        with col_i:
            pos = nx.spring_layout(G, seed=42, k=1.2)
            edge_x, edge_y = [], []
            for u, v in G.edges():
                x0, y0 = pos[u]; x1, y1 = pos[v]
                edge_x += [x0, x1, None]; edge_y += [y0, y1, None]

            degrees = [G.degree(n) for n in G.nodes()]
            labels  = list(G.nodes())

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines",
                                     line=dict(width=0.7, color="#D9AEF0"),
                                     hoverinfo="none"))
            fig.add_trace(go.Scatter(
                x=[pos[n][0] for n in G.nodes()],
                y=[pos[n][1] for n in G.nodes()],
                mode="markers+text",
                marker=dict(size=[8 + d * 1.5 for d in degrees],
                            color=degrees,
                            colorscale=PURPLES,
                            line=dict(width=1, color="#FFFCB8")),
                text=[l if G.degree(l) > 3 else "" for l in labels],
                textposition="top center",
                textfont=dict(size=8, color="#1A0030"),
                hovertext=[f"{l} — {G.degree(l)} collaborators" for l in labels],
                hoverinfo="text",
            ))
            fig.update_layout(**PL, height=460, showlegend=False,
                              xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                              yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
            st.plotly_chart(fig, use_container_width=True)

        with col_ii:
            st.markdown("<div class='section-title'>Top Pairs</div>", unsafe_allow_html=True)
            for _, row in pd.DataFrame(collabs[:15]).iterrows():
                st.markdown(f"""
                <div class="paper-card" style="padding:10px 14px;">
                  <div style="font-size:0.82rem;font-weight:600;color:#9112BC">{row['author1'][:30]}</div>
                  <div style="font-size:0.75rem;color:#AE75DA;margin:2px 0">{row['collaborations']} shared papers</div>
                  <div style="font-size:0.82rem;font-weight:600;color:#9112BC">{row['author2'][:30]}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<hr class='sg-divider'>", unsafe_allow_html=True)
        cs1, cs2, cs3 = st.columns(3)
        cs1.metric("Authors", G.number_of_nodes())
        cs2.metric("Edges",   G.number_of_edges())
        cs3.metric("Components", len(list(nx.connected_components(G))))


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — TOPICS & TRENDS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Topics & Trends":
    st.markdown("<div class='section-title'>Topics & Research Trends</div>", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["Global Distribution", "By Year", "Evolution"])

    with tab1:
        df = pd.DataFrame(get_top_topics(limit=25))
        if not df.empty:
            fig = px.bar(df, x="papers", y="topic", orientation="h",
                         color="papers", color_continuous_scale=PURPLES)
            fig.update_layout(**PL, yaxis=dict(autorange="reversed"),
                              xaxis_title="Papers", yaxis_title="", height=600)
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        selected_year = st.selectbox("Year", list(range(2026, 2009, -1)))
        df_y = pd.DataFrame(get_topics_by_year(selected_year, limit=20))
        if not df_y.empty:
            fig = px.bar(df_y, x="papers", y="topic", orientation="h",
                         color="papers", color_continuous_scale=PURPLES)
            fig.update_layout(**PL, yaxis=dict(autorange="reversed"),
                              xaxis_title="Papers", yaxis_title="", height=520)
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"No topics for {selected_year}.")

    with tab3:
        top5 = [r["topic"] for r in get_top_topics(5)]
        years_list = sorted([r["year"] for r in get_papers_by_year() if r["year"]])
        trend_data = []
        for y in years_list:
            for t in get_topics_by_year(y, limit=50):
                if t["topic"] in top5:
                    trend_data.append({"Year": y, "Topic": t["topic"], "Papers": t["papers"]})
        if trend_data:
            fig = px.line(pd.DataFrame(trend_data), x="Year", y="Papers", color="Topic",
                          markers=True, color_discrete_sequence=PURPLES + [ACCENT])
            fig.update_layout(**PL, height=400)
            st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — AUTHOR SEARCH
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Author Search":
    st.markdown("<div class='section-title'>Author Profile</div>", unsafe_allow_html=True)

    author_input = st.text_input("Author name", placeholder="e.g. Bengio, LeCun, Vaswani",
                                  label_visibility="collapsed")

    if author_input:
        col1, col2 = st.columns([3, 2])

        with col1:
            st.markdown("**Published Papers**")
            papers = get_author_papers(author_input)
            if papers:
                for p in papers[:15]:
                    st.markdown(f"""
                    <div class="paper-card">
                        <div class="paper-title">{p['title'][:110]}</div>
                        <div>
                            <span class="paper-badge">{p.get('year','—')}</span>
                            <span class="paper-badge">{p.get('citations',0) or 0:,} citations</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                st.caption(f"{len(papers)} papers found")
            else:
                st.warning("No papers found.")

        with col2:
            st.markdown("**Top Collaborators**")
            collabs = get_author_collaborators(author_input)
            if collabs:
                df_c = pd.DataFrame(collabs[:15])
                fig = px.bar(df_c, x="shared_papers", y="collaborator", orientation="h",
                             color="shared_papers", color_continuous_scale=PURPLES)
                fig.update_layout(**PL, yaxis=dict(autorange="reversed"),
                                  xaxis_title="Shared papers", yaxis_title="", height=380)
                fig.update_traces(marker_line_width=0)
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("**Network**")
                G = nx.Graph()
                G.add_node(author_input)
                for c in collabs[:20]:
                    G.add_edge(author_input, c["collaborator"], weight=c["shared_papers"])

                pos = nx.spring_layout(G, seed=42)
                edge_x, edge_y = [], []
                for u, v in G.edges():
                    x0, y0 = pos[u]; x1, y1 = pos[v]
                    edge_x += [x0, x1, None]; edge_y += [y0, y1, None]

                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines",
                                          line=dict(width=1, color="#D9AEF0"),
                                          hoverinfo="none"))
                fig2.add_trace(go.Scatter(
                    x=[pos[n][0] for n in G.nodes()],
                    y=[pos[n][1] for n in G.nodes()],
                    mode="markers+text",
                    marker=dict(
                        size=[20 if n == author_input else 11 for n in G.nodes()],
                        color=[ACCENT if n == author_input else "#9112BC" for n in G.nodes()],
                        line=dict(width=1, color="#FFFCB8")
                    ),
                    text=[n[:20] for n in G.nodes()],
                    textposition="top center",
                    textfont=dict(size=7),
                    hoverinfo="text",
                ))
                fig2.update_layout(**PL, height=270, showlegend=False,
                                   xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                   yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.warning("No collaborators found.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — TOPIC SEARCH
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Topic Search":
    st.markdown("<div class='section-title'>Topic Explorer</div>", unsafe_allow_html=True)

    topic_input = st.text_input("Topic", placeholder="e.g. neural, transformer, federated",
                                 label_visibility="collapsed")

    if topic_input:
        papers = get_papers_by_topic(topic_input, limit=20)
        if papers:
            st.caption(f"{len(papers)} papers found for **{topic_input}**")
            df = pd.DataFrame(papers)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Citations vs Year**")
                fig = px.scatter(df, x="year", y="citations",
                                 hover_data=["title"],
                                 color="citations", color_continuous_scale=PURPLES,
                                 size="citations", size_max=28)
                fig.update_layout(**PL, xaxis_title="Year", yaxis_title="Citations", height=300)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.markdown("**Papers per Year**")
                fig2 = px.histogram(df, x="year", nbins=12,
                                    color_discrete_sequence=["#9112BC"])
                fig2.update_layout(**PL, xaxis_title="Year", yaxis_title="Count", height=300)
                st.plotly_chart(fig2, use_container_width=True)

            st.markdown("**Papers**")
            for p in papers:
                st.markdown(f"""
                <div class="paper-card">
                    <div class="paper-title">{p['title'][:120]}</div>
                    <div>
                        <span class="paper-badge">{p.get('year','—')}</span>
                        <span class="paper-badge">{p.get('citations',0) or 0:,} citations</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning(f"No papers found for '{topic_input}'.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6 — COMMUNITIES
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Research Communities":
    from bonus.community import get_communities_from_neo4j, get_author_community

    st.markdown("<div class='section-title'>Research Communities — Louvain Detection</div>",
                unsafe_allow_html=True)

    communities_data = get_communities_from_neo4j(limit=50)

    if not communities_data:
        st.warning("No communities detected yet. Run: `python bonus/community.py`")
        if st.button("Run detection now"):
            with st.spinner("Detecting communities…"):
                from bonus.community import run_community_detection
                result = run_community_detection()
                if result:
                    st.success(f"{result['n_communities']} communities detected!")
                    st.rerun()
                else:
                    st.error("Detection failed. Check logs.")
    else:
        total_authors = sum(c["size"] for c in communities_data)
        n_comm        = len(communities_data)

        cm1, cm2, cm3 = st.columns(3)
        cm1.metric("Communities",      n_comm)
        cm2.metric("Authors assigned", f"{total_authors:,}")
        cm3.metric("Avg size",         f"{total_authors / n_comm:.1f}")

        st.markdown("<hr class='sg-divider'>", unsafe_allow_html=True)

        col_l, col_r = st.columns([3, 2])

        with col_l:
            st.markdown("<div class='section-title'>Community Sizes</div>", unsafe_allow_html=True)
            df_comm = pd.DataFrame(communities_data)
            df_comm["label"] = df_comm["community_id"].apply(lambda x: f"#{x}")
            fig = px.bar(df_comm.head(20), x="size", y="label", orientation="h",
                         color="size", color_continuous_scale=PURPLES)
            fig.update_layout(**PL, yaxis=dict(autorange="reversed"),
                              xaxis_title="Members", yaxis_title="", height=460)
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.markdown("<div class='section-title'>Distribution</div>", unsafe_allow_html=True)
            fig2 = px.pie(df_comm.head(12), names="label", values="size",
                          color_discrete_sequence=PURPLES + [ACCENT])
            fig2.update_layout(**PL, height=300)
            fig2.update_traces(textposition="inside", textinfo="percent+label", textfont_size=9)
            st.plotly_chart(fig2, use_container_width=True)

            st.markdown("**Top communities**")
            for comm in communities_data[:8]:
                members = comm.get("top_members", [])[:3]
                st.markdown(f"""
                <div class="paper-card" style="padding:10px 14px;">
                  <div style="font-size:0.78rem;font-weight:700;color:#9112BC">
                    Community #{comm['community_id']} &middot; {comm['size']} members
                  </div>
                  <div style="font-size:0.74rem;color:#AE75DA;margin-top:3px">
                    {', '.join(members)}{'...' if len(members) == 3 else ''}
                  </div>
                </div>
                """, unsafe_allow_html=True)

        # Network coloured by community
        st.markdown("<hr class='sg-divider'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>Network by Community</div>", unsafe_allow_html=True)
        n_collab = st.slider("Edges to display", 30, 150, 80)

        driver = get_driver()
        query = """
        MATCH (a1:Author)-[r:COLLABORATED_WITH]-(a2:Author)
        WHERE id(a1) < id(a2)
          AND a1.community_id IS NOT NULL AND a2.community_id IS NOT NULL
        RETURN a1.name AS author1, a1.community_id AS comm1,
               a2.name AS author2, a2.community_id AS comm2,
               r.count AS weight
        ORDER BY r.count DESC LIMIT $limit
        """
        with driver.session() as session:
            rows = [dict(r) for r in session.run(query, limit=n_collab)]
        driver.close()

        if rows:
            comm_ids  = sorted(set([r["comm1"] for r in rows] + [r["comm2"] for r in rows]))
            palette   = PURPLES + [ACCENT, "#FFFCB8", "#D9AEF0", "#F3E6FA",
                                   "#FF8080", "#FFD700", "#00BCD4", "#4CAF50"]
            color_map = {cid: palette[i % len(palette)] for i, cid in enumerate(comm_ids)}

            G = nx.Graph()
            node_comm = {}
            for r in rows:
                G.add_edge(r["author1"], r["author2"], weight=r["weight"])
                node_comm[r["author1"]] = r["comm1"]
                node_comm[r["author2"]] = r["comm2"]

            pos = nx.spring_layout(G, seed=42, k=1.5)
            edge_x, edge_y = [], []
            for u, v in G.edges():
                x0, y0 = pos[u]; x1, y1 = pos[v]
                edge_x += [x0, x1, None]; edge_y += [y0, y1, None]

            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines",
                                      line=dict(width=0.5, color="#D9AEF0"),
                                      hoverinfo="none"))
            fig3.add_trace(go.Scatter(
                x=[pos[n][0] for n in G.nodes()],
                y=[pos[n][1] for n in G.nodes()],
                mode="markers+text",
                marker=dict(
                    size=[10 + G.degree(n) * 1.8 for n in G.nodes()],
                    color=[color_map.get(node_comm.get(n, 0), "#AE75DA") for n in G.nodes()],
                    line=dict(width=1, color="#FFFFFF")
                ),
                text=[n[:16] if G.degree(n) > 4 else "" for n in G.nodes()],
                textposition="top center",
                textfont=dict(size=7, color="#1A0030"),
                hovertext=[f"{n} — Community #{node_comm.get(n,'?')}" for n in G.nodes()],
                hoverinfo="text",
            ))
            fig3.update_layout(**PL, height=500, showlegend=False,
                               xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                               yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
            st.plotly_chart(fig3, use_container_width=True)
            st.caption("Each color represents a distinct research community detected by Louvain.")

        # Author lookup
        st.markdown("<hr class='sg-divider'>", unsafe_allow_html=True)
        st.markdown("**Find an author's community**")
        author_search = st.text_input("Community author search",
                                       placeholder="e.g. LeCun, Bengio, Schmidhuber",
                                       label_visibility="collapsed",
                                       key="comm_author")
        if author_search:
            result = get_author_community(author_search)
            if result:
                st.success(f"Community #{result['community_id']} — {result['community_size']} members")
                members_html = "".join(
                    f'<span class="author-pill">{m}</span>' for m in result["members"]
                )
                st.markdown(members_html, unsafe_allow_html=True)
            else:
                st.warning("Author not found or not yet assigned to a community.")