# ai_sql.py

import os
import re
import sqlparse
from functools import lru_cache
from typing import Optional

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

# ─── Few‑Shot Examples ──────────────────────────────────────────────
FEW_SHOT = """
-- Beispiel 1
-- NL: "Top 3 fastest laps in session 4711"
-- SQL:
SELECT d.full_name, l.lap_number, l.duration
FROM lap l
JOIN driver d USING(driver_id)
WHERE l.session_id = 4711
  AND l.out_lap = 0
ORDER BY l.duration ASC
LIMIT 3;

-- Beispiel 2
-- NL: "Anzahl der Fahrer im Rennen in session 4711"
-- SQL:
SELECT COUNT(DISTINCT driver_id) AS driver_count
FROM result
WHERE session_id = 4711;

-- Ende Beispiele
"""

# 2️⃣ Prompt setup
SCHEMA_SNIPPET = """
Database schema overview (PostgreSQL):

CREATE TABLE driver(
    driver_id int PRIMARY KEY,
    broadcast_name varchar(200) NOT NULL,
    first_name varchar(200) NOT NULL,
    last_name varchar(200) NOT NULL,
    full_name varchar(200) NOT NULL,
    country_code char(3) NOT NULL,
    picture_url varchar(200),
    acronym char(3) NOT NULL
);

CREATE TABLE team(
    team_name varchar(200) PRIMARY KEY,
    team_colour char(6) NOT NULL
);

CREATE TABLE circuit(
    circuit_id int PRIMARY KEY,
    short_name varchar(200) NOT NULL,
    official_name varchar(200) NOT NULL,
    country_code char(3) NOT NULL,
    country_key int NOT NULL,
    location varchar(200) NOT NULL
);

CREATE TABLE meeting(
    meeting_id int PRIMARY KEY,
    meeting_name varchar(200) NOT NULL,
    official_name varchar(200) NOT NULL,
    circuit_id int references circuit NOT NULL,
    start timestamp NOT NULL,
    year int
);

CREATE TABLE session(
    session_id int PRIMARY KEY,
    meeting_id int references meeting NOT NULL,
    start_time timestamp NOT NULL,
    end_time timestamp,
    session_name varchar(200) NOT NULL,
    session_type varchar(200) NOT NULL
);

CREATE TABLE team_membership(
    team_name varchar(200) references team NOT NULL,
    driver_id int references driver NOT NULL,
    session_id int references session NOT NULL,
    UNIQUE(team_name, driver_id, session_id)
);

CREATE TABLE weather(
    session_id int references session NOT NULL,
    time timestamp NOT NULL,
    temperature float,
    humidity int,
    air_pressure  float,
    rainfall float,
    track_temperature float,
    wind_direction int,
    wind_speed float,
    UNIQUE(session_id, time)
);

CREATE TABLE race_control(
    session_id int references session NOT NULL,
    time timestamp NOT NULL,
    driver_id int references driver DEFAULT NULL,
    category varchar(200) NOT NULL,
    flag varchar(200) DEFAULT NULL,
    lap_number int DEFAULT NULL,
    message varchar(500),
    scope varchar(200),
    sector int DEFAULT NULL,
    UNIQUE(session_id, driver_id, time)
);

CREATE TABLE result(
    driver_id int references driver NOT NULL,
    session_id int references session NOT NULL,
    position int NOT NULL,
    total_time float,
    gap_to_winner varchar(200),
    points int,
    status varchar(200),
    PRIMARY KEY(driver_id, session_id)
);

CREATE TABLE location(
    location_id SERIAL PRIMARY KEY,
    time timestamp NOT NULL,
    driver_id int references driver NOT NULL,
    session_id int references session NOT NULL,
    x int,
    y int,
    z int,
    UNIQUE(time, driver_id, session_id)
);

CREATE TABLE position(
    time timestamp NOT NULL,
    driver_id int references driver NOT NULL,
    session_id int references session NOT NULL,
    position int,
    PRIMARY KEY(time, driver_id, session_id)
);

CREATE TABLE intervals(
    time timestamp NOT NULL,
    driver_id int references driver NOT NULL,
    session_id int references session NOT NULL,
    gap_to_leader float,
    overlap_to_leader int DEFAULT 0,
    gap_to_next float,
    overlap_to_next int DEFAULT 0,
    PRIMARY KEY(time, driver_id, session_id)
);

CREATE TABLE lap(
    lap_id SERIAL PRIMARY KEY,
    driver_id int references driver NOT NULL,
    session_id int references session NOT NULL,
    lap_number int NOT NULL,
    start_time timestamp,
    i1_speed int,
    i2_speed int,
    out_lap int DEFAULT 0 NOT NULL,
    duration float,
    top_speed int,
    UNIQUE(driver_id, session_id, lap_number)
);

CREATE TABLE sector(
    id SERIAL PRIMARY KEY,
    lap_id int references lap NOT NULL,
    sector_number int NOT NULL,
    duration float NOT NULL,
    UNIQUE(lap_id, sector_number)
);

CREATE TABLE segment(
    sector_id int references sector NOT NULL,
    segment_number int NOT NULL,
    segment_index float NOT NULL,
    segment_status varchar(200) NOT NULL,
    UNIQUE(sector_id, segment_number)
);

CREATE TABLE car_data(
    time timestamp NOT NULL,
    driver_id int references driver NOT NULL,
    session_id int references session NOT NULL,
    brake_is_pressed int,
    drs_status int,
    gear int,
    rpm int,
    speed int,
    throttle int,
    UNIQUE(time, driver_id, session_id)
);

CREATE TABLE pit_stop(
    time timestamp NOT NULL,
    driver_id int references driver NOT NULL,
    session_id int references session NOT NULL,
    duration float,
    lap_number int,
    UNIQUE(time, driver_id, session_id)
);

CREATE TABLE stint(
    driver_id int references driver NOT NULL,
    session_id int references session NOT NULL,
    stint_number int NOT NULL,
    compound varchar(200),
    lap_start int,
    lap_end int,
    tire_age_at_start int,
    UNIQUE(driver_id, session_id, stint_number)
);

CREATE VIEW v_session_results(...);
CREATE VIEW v_lap_detail(...);
CREATE VIEW v_driver_points(...);
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
def question_to_sql(question: str, session_id: Optional[int] = None) -> tuple[str, str, str]:
    prompt = [
        f"{SYSTEM_CONTEXT}\n\nSchema:\n{SCHEMA_SNIPPET}",
        "Here are some examples of NL→SQL conversions:",
        FEW_SHOT,
        f"Natural language: \"{question}\"",
    ]
    if session_id is not None:
        prompt.append(
            f"The user is interested in data for session_id {session_id}. "
            "If appropriate, include a WHERE clause to filter results to this session."
        )
    prompt.append("SQL:")
    response = _model().generate_content(prompt)

    raw_text = response.text.strip()

    # strip any leading "SQL", "sql:", etc. before the actual SELECT
    cleaned_sql = re.sub(r'(?i)^\s*sql[:\s\n]*', '', raw_text)
    cleaned_sql = cleaned_sql.strip("`").strip()

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
def ask(question: str, session_id: Optional[int] = None):
    if not os.getenv("GEMINI_API_KEY"):
        return {
            "raw": "",
            "sql": None,
            "df": None,
            "answer": None,
            "error": "GEMINI_API_KEY environment variable not set",
        }

    sql, raw, _ = question_to_sql(question, session_id)

    # Versuch, das SQL zu parsen
    try:
        parsed = sqlparse.parse(sql)[0]
    except Exception:
        return {
            "raw": raw,
            "sql": sql,
            "df": None,
            "answer": None,
            "error": "Could not parse generated SQL. Please review manually.",
        }

    # Nur SELECT‑Statements erlaubt (Warnung statt Exception)
    if parsed.get_type() != "SELECT":
        return {
            "raw": raw,
            "sql": sql,
            "df": None,
            "answer": None,
            "error": "Warnung: Generiertes Statement ist kein SELECT. Bitte prüfen.",
        }

    # DML/DDL‑Keywords weiterhin blocken
    if re.search(r";|\b(update|delete|insert|drop|alter)\b", sql, re.I):
        return {
            "raw": raw,
            "sql": sql,
            "df": None,
            "answer": None,
            "error": "Unsafe SQL detected – please remove data‑modifying statements.",
        }

    # SQL ausführen
    df = run_query(sql)

    # Zusammenfassung erzeugen
    answer = "No results found." if df.empty else _summarize(question, df)

    return {
        "raw": raw,
        "sql": sql,
        "df": df,
        "answer": answer,
        "error": None,
    }
