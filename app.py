import streamlit as st
import plotly.express as px
import pandas as pd
from ssh_tunnel import start_ssh_tunnel

# Open the SSH tunnel before anything else
start_ssh_tunnel()

from db import run_query
from ai_sql import ask
from refresh_views import refresh  # optional manual refresh UI

st.set_page_config(page_title="F1 Analytics Suite", layout="wide")
st.title("🏎️ F1 Analytics Suite")

# ───────────────────────── Sidebar ──────────────────────────
with st.sidebar:
    st.header("Filters")
    seasons = run_query("SELECT DISTINCT year FROM meeting ORDER BY year DESC")["year"]
    sel_year = st.selectbox("Season", seasons, index=0)

    sessions = run_query(
        """
        SELECT s.session_id,
               CONCAT(m.meeting_name,' – ',s.session_name) AS label
        FROM session s
        JOIN meeting m ON m.meeting_id = s.meeting_id
        WHERE m.year = :yr
        ORDER BY m.start
        """, yr=int(sel_year))
    session_label = st.selectbox("Session", sessions["label"], index=len(sessions)-1)
    session_id = sessions.loc[sessions["label"] == session_label, "session_id"].iat[0]

    # optional manual refresh
    if st.button("↻ Refresh materialised views"):
        refresh_all = st.checkbox("Full refresh (can take minutes)", value=False)
        with st.spinner("Refreshing…"):
            from refresh_views import refresh_all, VIEWS
            if refresh_all:
                refresh_all()
            else:
                for v in VIEWS:
                    refresh(v)
        st.success("Done!")

# ───────────────────────── Tabs ──────────────────────────
tab_race, tab_lap, tab_stint, tab_pit, tab_sector, tab_season, tab_ai = st.tabs(
    ["🏁 Race results", "📈 Lap pace", "🛞 Stint cmp.", "🔧 Pit stops",
     "🚥 Sector bests", "📊 Season view", "🤖 Ask AI"])

# 1️⃣  Race results  (unchanged)
with tab_race:
    df = run_query(
        "SELECT * FROM v_session_results WHERE session_id = :sid ORDER BY position",
        sid=int(session_id))
    st.dataframe(df, use_container_width=True)
    fig = px.bar(df, x="acronym", y="points", color="team_name",
                 color_discrete_sequence=["#"+c for c in df.team_colour])
    st.plotly_chart(fig, use_container_width=True)

# 2️⃣  Lap pace  (unchanged)
with tab_lap:
    lap_df = run_query(
        """
        SELECT d.full_name, l.lap_number, l.lap_time_s
        FROM v_lap_detail l JOIN driver d USING (driver_id)
        WHERE session_id=:sid AND out_lap=0
        ORDER BY lap_number
        """, sid=int(session_id))
    fig = px.line(lap_df, x="lap_number", y="lap_time_s", color="full_name", markers=True)
    st.plotly_chart(fig, use_container_width=True)

# 3️⃣  Stint comparison
with tab_stint:
    st.subheader("Stint summary (analysis.mv_stint_summary)")
    stint_df = run_query(
        "SELECT * FROM analysis.mv_stint_summary WHERE session_id = :sid",
        sid=int(session_id))
    st.dataframe(stint_df, use_container_width=True)
    fig = px.bar(stint_df, x="full_name", y="avg_lap_s",
                 color="compound", barmode="group", hover_data=["best_lap_s"])
    st.plotly_chart(fig, use_container_width=True)

# 4️⃣  Pit-stop timeline
# 4️⃣  Pit-stop timeline
with tab_pit:
    pit_df = run_query(
        """
        SELECT *
        FROM analysis.mv_pit_stop_timeline
        WHERE session_id = :sid
        """,
        sid=int(session_id),
    )

    if pit_df.empty:
        st.info("No pit-stop data for this session.")
    else:
        st.subheader("Pit-stop timeline")

        # Plotly needs proper datetime objects
        pit_df["start_time"] = pd.to_datetime(pit_df["start_time"])
        pit_df["end_time"]   = pd.to_datetime(pit_df["end_time"])

        fig = px.timeline(
            pit_df,
            x_start="start_time",
            x_end="end_time",
            y="full_name",
            color="team_name",
            hover_data=["lap_number", "duration"],
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)


# 5️⃣  Sector performance
with tab_sector:
    sector_df = run_query(
        "SELECT * FROM analysis.mv_sector_performance WHERE session_id = :sid",
        sid=int(session_id))
    st.subheader("Best sector times")
    fig = px.bar(sector_df, x="full_name", y="best_sector_s",
                 color="sector_number", barmode="group")
    st.plotly_chart(fig, use_container_width=True)

# 6️⃣  Season driver summary
with tab_season:
    seas_df = run_query(
        "SELECT * FROM analysis.mv_driver_summary_season WHERE year = :y",
        y=int(sel_year))
    st.subheader(f"Season {sel_year} points")
    fig = px.bar(seas_df.sort_values("season_points", ascending=False),
                 x="full_name", y="season_points")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(seas_df, use_container_width=True)

# 7️⃣  Ask AI
with tab_ai:
    if "ai_history" not in st.session_state:
        st.session_state.ai_history = []

    q = st.text_input("Ask something about the F1 data")
    if st.button("Run AI query") and q:
        with st.spinner("Gemini Flash is thinking…"):
            res = ask(q)
        st.session_state.ai_history.append((q, res))

    # Show history, newest on top
    for i, (query, res) in enumerate(reversed(st.session_state.ai_history), 1):
        with st.expander(f"🧠 {i}. {query}", expanded=False):
            st.markdown("#### 📝 Raw Gemini response")
            st.code(res["raw"], language="text")

            if res["error"]:
                st.error(f"⚠️ {res['error']}")
                continue

            st.markdown("#### 💡 Generated SQL")
            st.code(res["sql"], language="sql")

            st.markdown("#### 🗒️ Answer summary")
            st.success(res["answer"])

            st.markdown("#### 📊 Result data")
            st.dataframe(res["df"], use_container_width=True)
