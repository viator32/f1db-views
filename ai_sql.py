# ai_sql.py
import os, re, sqlparse
from functools import lru_cache
import google.generativeai as genai
from db import run_query           # your helper from yesterday

###############
#  3.1  Init  #
###############
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

@lru_cache
def _model():
    return genai.GenerativeModel(
        model_name=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        generation_config={
            "response_mime_type": "text/plain",
            "temperature": 0.0,       # deterministic SQL
            "max_output_tokens": 256,
        },
    )

###############
#  3.2  NL→SQL #
###############
SCHEMA_SNIPPET = """
Tables / Views you can use (PostgreSQL):

driver(driver_id, broadcast_name, first_name, last_name, full_name, country_code, picture_url, acronym)
team(team_name, team_colour)
session(session_id, meeting_id, session_name, session_type, start_time, end_time)
team_membership(team_name, driver_id, session_id)
lap(lap_id, driver_id, session_id, lap_number, duration, out_lap, top_speed)
v_session_results(session_id, session_name, meeting_name, year, acronym, full_name, position, points, team_name, team_colour)
v_lap_detail(lap_id, session_id, driver_id, lap_number, lap_time_s, sector1_s, sector2_s, sector3_s)
"""

SYSTEM_PROMPT = f"""You are a Postgres SQL generator for an F1 telemetry database.
Return **only** one valid SQL SELECT statement, never multiple commands, never DDL/DML.
Use table aliases. Prefer the two helper views when possible:
  * v_session_results –  final positions & points per driver per session
  * v_lap_detail      –  lap times incl. sectors
Columns are seconds unless stated otherwise.
Schema:
{SCHEMA_SNIPPET}
"""

def question_to_sql(question: str) -> str:
    response = _model().generate_content(
        [{"role": "system", "parts": [SYSTEM_PROMPT]},
         {"role": "user",   "parts": [question]}]
    )
    sql = response.text.strip().strip("`").strip()
    
    # ---- 3.3  Safety gate  ----------------------------------------------
    parsed = sqlparse.parse(sql)[0]
    if parsed.get_type() != "SELECT":
        raise ValueError("Only SELECT statements are allowed.")
    # forbid ; or DROP etc.
    if re.search(r";|\b(update|delete|insert|drop|alter)\b", sql, re.I):
        raise ValueError("Unsafe SQL detected.")
    return sql

###################
#  3.4  End-to-end #
###################
def ask(question: str):
    sql = question_to_sql(question)
    df  = run_query(sql)
    return sql, df
