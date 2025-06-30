# ai_sql.py
import os
import re
import sqlparse
from functools import lru_cache
import pandas as pd
import google.generativeai as genai
from db import run_query

# 1️⃣ Gemini config
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

@lru_cache
def _model():
    return genai.GenerativeModel(
        model_name=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
        generation_config={
            "response_mime_type": "text/plain",
            "temperature": 0.0,
            "max_output_tokens": 512,
        },
    )

# 2️⃣ Prompt setup
SCHEMA_SNIPPET = """
Tables you can query (PostgreSQL):

driver(driver_id, broadcast_name, first_name, last_name, full_name, country_code, picture_url, acronym)
team(team_name, team_colour)
circuit(circuit_id, short_name, official_name, country_code, country_key, location)
meeting(meeting_id, meeting_name, official_name, circuit_id, start, year)
session(session_id, meeting_id, start_time, end_time, session_name, session_type)
team_membership(team_name, driver_id, session_id)
weather(session_id, time, temperature, humidity, air_pressure, rainfall, track_temperature, wind_direction, wind_speed)
race_control(session_id, time, driver_id, category, flag, lap_number, message, scope, sector)
result(driver_id, session_id, position, total_time, gap_to_winner, points, status)
location(time, driver_id, session_id, x, y, z)
position(time, driver_id, session_id, position)
intervals(time, driver_id, session_id, gap_to_leader, overlap_to_leader, gap_to_next, overlap_to_next)
lap(lap_id, driver_id, session_id, lap_number, start_time, i1_speed, i2_speed, out_lap, duration, top_speed)
sector(id, lap_id, sector_number, duration)
segment(sector_id, segment_number, segment_index, segment_status)
car_data(time, driver_id, session_id, brake_is_pressed, drs_status, gear, rpm, speed, throttle)
pit_stop(time, driver_id, session_id, duration, lap_number)
stint(driver_id, session_id, stint_number, compound, lap_start, lap_end, tire_age_at_start)
v_session_results(session_id, session_name, meeting_name, year, acronym, full_name, position, points, team_name, team_colour)
v_lap_detail(lap_id, session_id, driver_id, lap_number, lap_time_s, sector1_s, sector2_s, sector3_s)
v_driver_points(full_name, year, season_points)
"""

SYSTEM_CONTEXT = (
    "You convert user questions into SQL for a Formula 1 Postgres database. "
    "Use only the tables listed in the schema and return a single SELECT "
    "statement without explanations."
)

SUMMARY_CONTEXT = (
    "You are an expert data analyst. Using the query results preview, write a "
    "concise answer to the user's question without disclaimers."
)

# 3️⃣ Generate SQL from question
def question_to_sql(question: str) -> tuple[str, str, str]:
    response = _model().generate_content([
        f"{SYSTEM_CONTEXT}\n\nSchema:\n{SCHEMA_SNIPPET}",
        f"Natural language: {question}",
        "SQL:"
    ])

    raw_text = response.text.strip()
    cleaned_sql = raw_text.strip("`").strip()

    return cleaned_sql, raw_text, question


def _summarize(question: str, df: pd.DataFrame) -> str:
    """Use Gemini to summarise query results in natural language."""
    preview = df.head(5).to_csv(index=False)
    resp = _model().generate_content([
        SUMMARY_CONTEXT,
        f"Question: {question}",
        f"Results:\n{preview}",
        "Answer:",
    ])
    return resp.text.strip()

# 4️⃣ Run query or fallback to raw
def ask(question: str):
    if not os.getenv("GEMINI_API_KEY"):
        return {
            "raw": "",
            "sql": None,
            "df": None,
            "answer": None,
            "error": "GEMINI_API_KEY environment variable not set",
        }

    try:
        sql, raw, _ = question_to_sql(question)
        parsed = sqlparse.parse(sql)[0]

        if parsed.get_type() != "SELECT":
            raise ValueError("Not a SELECT")
        if re.search(r";|\b(update|delete|insert|drop|alter)\b", sql, re.I):
            raise ValueError("Unsafe SQL")

        df = run_query(sql)

        # Summarise results using Gemini
        if df.empty:
            answer = "No results found."
        else:
            answer = _summarize(question, df)

        return {"raw": raw, "sql": sql, "df": df, "answer": answer, "error": None}
    except Exception as e:
        return {
            "raw": locals().get("raw", "-- no raw text --"),
            "sql": None,
            "df": None,
            "answer": None,
            "error": str(e)
        }
