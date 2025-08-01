import os
import streamlit as st
import plotly.express as px
import pandas as pd
from ssh_tunnel import start_ssh_tunnel

# Open the SSH tunnel before anything else
start_ssh_tunnel()

from db import run_query
from ai_sql import ask

st.set_page_config(page_title="F1 Analytics Suite", layout="wide")
st.title("🏎️ F1 Analytics Suite")

# ───────────────────────── Sidebar ──────────────────────────
with st.sidebar:
    st.header("Filters")
    seasons = run_query("SELECT DISTINCT year FROM meeting ORDER BY year DESC")["year"]
    sel_year = st.selectbox("Season", seasons, index=0)

    # fetch all Race sessions for the selected year, ordered by meeting start
    sessions = run_query(
        """
        SELECT s.session_id,
               m.meeting_name AS label,
               m.start
        FROM session s
        JOIN meeting m ON m.meeting_id = s.meeting_id
        WHERE m.year = :yr
          AND s.session_type = 'Race'
        ORDER BY m.start
        """,
        yr=int(sel_year)
    )

    # keep only one row per meeting_name (label), keeping the last (i.e. the latest by start)
    sessions = (
        sessions
        .drop_duplicates(subset="label", keep="last")
        .reset_index(drop=True)
    )

    # build the selectbox from the de‑duplicated labels
    session_label = st.selectbox("Race", sessions["label"], index=len(sessions) - 1)
    session_id = int(sessions.loc[sessions["label"] == session_label, "session_id"].iat[0])


# ───────────────────────── Tabs ──────────────────────────
tab_race, tab_lap, tab_stint, tab_pit, tab_sector, tab_season, tab_ai = st.tabs(
    ["🏁 Race results", "📈 Lap pace", "🛞 Stint cmp.", "🔧 Pit stops",
     "🚥 Sector bests", "📊 Season view", "🤖 Ask AI"])

# 1️⃣  Race results
with tab_race:
    df = run_query(
        "SELECT * FROM v_session_results WHERE session_id = :sid ORDER BY position",
        sid=session_id
    )
    st.dataframe(df, use_container_width=True)
    fig = px.bar(
        df,
        x="acronym",
        y="points",
        color="team_name",
        color_discrete_sequence=["#" + c for c in df.team_colour]
    )
    st.plotly_chart(fig, use_container_width=True)

# 2️⃣  Lap pace
with tab_lap:
    lap_df = run_query(
        """
        SELECT d.full_name, l.lap_number, l.lap_time_s
        FROM v_lap_detail l JOIN driver d USING (driver_id)
        WHERE session_id=:sid AND out_lap=0
        ORDER BY lap_number
        """,
        sid=session_id
    )
    fig = px.line(lap_df, x="lap_number", y="lap_time_s", color="full_name", markers=True)
    st.plotly_chart(fig, use_container_width=True)

# 3️⃣  Stint comparison (Best Lap)
with tab_stint:
    st.subheader("Best Lap per Stint (analysis.mv_stint_summary)")
    stint_df = run_query(
        """
        SELECT
            driver_id,
            full_name,
            team_name,
            team_colour,
            stint_number,
            compound,
            best_lap_s
        FROM analysis.mv_stint_summary
        WHERE session_id = :sid
        """,
        sid=session_id
    )
    st.dataframe(stint_df, use_container_width=True)
    fig = px.bar(
        stint_df,
        x="full_name",
        y="best_lap_s",
        color="compound",
        barmode="group",
        hover_data=["stint_number", "team_name"]
    )
    fig.update_layout(
        title="Best Lap per Stint",
        xaxis_title="Fahrer",
        yaxis_title="Best Lap Time (s)",
        legend_title="Reifencompound"
    )
    st.plotly_chart(fig, use_container_width=True)

# 4️⃣  Pit-stop timeline
with tab_pit:
    pit_df = run_query(
        """
        SELECT *
        FROM analysis.mv_pit_stop_timeline
        WHERE session_id = :sid
        """,
        sid=session_id
    )

    if pit_df.empty:
        st.info("No pit-stop data for this session.")
    else:
        st.subheader("Pit-stop timeline")
        pit_df["start_time"] = pd.to_datetime(pit_df["start_time"])
        pit_df["end_time"]   = pd.to_datetime(pit_df["end_time"])
        fig = px.timeline(
            pit_df,
            x_start="start_time",
            x_end="end_time",
            y="full_name",
            color="team_name",
            hover_data=["lap_number", "duration"]
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

# 5️⃣  Sector performance
with tab_sector:
    sector_df = run_query(
        "SELECT * FROM analysis.mv_sector_performance WHERE session_id = :sid",
        sid=session_id
    )
    st.subheader("Best sector times")
    fig = px.bar(
        sector_df,
        x="full_name",
        y="best_sector_s",
        color="sector_number",
        barmode="group"
    )
    st.plotly_chart(fig, use_container_width=True)

# 6️⃣  Season driver summary
with tab_season:
    seas_df = run_query(
        "SELECT * FROM analysis.mv_driver_summary_season WHERE year = :y",
        y=int(sel_year)
    )
    st.subheader(f"Season {sel_year} points")
    fig = px.bar(
        seas_df.sort_values("season_points", ascending=False),
        x="full_name",
        y="season_points"
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(seas_df, use_container_width=True)

# 7️⃣  Ask AI
with tab_ai:
    if "ai_history" not in st.session_state:
        st.session_state.ai_history = []
    if "manual_sql" not in st.session_state:
        st.session_state.manual_sql = ""
    if "sql_df" not in st.session_state:
        st.session_state.sql_df = None
    if "sql_error" not in st.session_state:
        st.session_state.sql_error = None

    if not os.getenv("GEMINI_API_KEY"):
        st.info("Set GEMINI_API_KEY to enable AI queries.")
    else:
        q = st.text_input("Ask something about the F1 data")
        if st.button("Run AI query") and q:
            with st.spinner("Gemini Flash is thinking…"):
                res = ask(q, session_id)
            st.session_state.ai_history.append((q, res))
            if res.get("sql"):
                st.session_state.manual_sql = res["sql"]
                st.session_state.sql_df = res["df"]
                st.session_state.sql_error = res["error"]

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

    st.markdown("### 🔍 Run custom SQL")
    st.text_area("SQL query", key="manual_sql", height=150)
    if st.button("Execute SQL") and st.session_state.manual_sql.strip():
        with st.spinner("Running SQL…"):
            try:
                st.session_state.sql_df = run_query(st.session_state.manual_sql)
                st.session_state.sql_error = None
            except Exception as e:
                st.session_state.sql_df = None
                st.session_state.sql_error = str(e)

    if st.session_state.sql_error:
        st.error(st.session_state.sql_error)
    if st.session_state.sql_df is not None:
        st.dataframe(st.session_state.sql_df, use_container_width=True)
