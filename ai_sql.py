# ai_sql.py
import os, re, sqlparse
from functools import lru_cache
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
Tables / Views you can use (PostgreSQL):

driver(driver_id, broadcast_name, first_name, last_name, full_name, country_code, picture_url, acronym)
team(team_name, team_colour)
session(session_id, meeting_id, session_name, session_type, start_time, end_time)
team_membership(team_name, driver_id, session_id)
lap(lap_id, driver_id, session_id, lap_number, duration, out_lap, top_speed)
v_session_results(session_id, session_name, meeting_name, year, acronym, full_name, position, points, team_name, team_colour)
v_lap_detail(lap_id, session_id, driver_id, lap_number, lap_time_s, sector1_s, sector2_s, sector3_s)
"""

SYSTEM_CONTEXT = f"""You are a helpful assistant that converts natural language into SQL queries 
for a Formula 1 Postgres database.
"""

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

# 4️⃣ Run query or fallback to raw
def ask(question: str):
    try:
        sql, raw, _ = question_to_sql(question)
        parsed = sqlparse.parse(sql)[0]

        if parsed.get_type() != "SELECT":
            raise ValueError("Not a SELECT")
        if re.search(r";|\b(update|delete|insert|drop|alter)\b", sql, re.I):
            raise ValueError("Unsafe SQL")

        df = run_query(sql)

        # Basic interpretation of results
        if df.empty:
            answer = "No results found."
        else:
            first_row = df.iloc[0].to_dict()
            formatted = ", ".join(f"{k} = {v}" for k, v in first_row.items())
            answer = f"Top result: {formatted}"

        return {"raw": raw, "sql": sql, "df": df, "answer": answer, "error": None}
    except Exception as e:
        return {
            "raw": locals().get("raw", "-- no raw text --"),
            "sql": None,
            "df": None,
            "answer": None,
            "error": str(e)
        }
