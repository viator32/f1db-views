Here's a simple and clean `README.md` file for your Streamlit project that documents how to set up and run everything using a `.venv` virtual environment:

---

````markdown
# 📊 My Streamlit App

This project is a Python-based Streamlit application. It uses a virtual environment (`.venv`) for dependency management.

---

## 🚀 Getting Started

### 1. Clone the Repository (if not already)
### 2. Create a Virtual Environment

We use `.venv` to isolate dependencies:

```bash
python3 -m venv .venv
```

### 3. Activate the Environment

#### On macOS / Linux:

```bash
source .venv/bin/activate
```

#### On Windows (CMD):

```cmd
.venv\Scripts\activate
```

#### On Windows (PowerShell):

```powershell
.venv\Scripts\Activate.ps1
```

---

### 4. Install Dependencies

```bash
pip install -r requirements.txt
pip install google-generativeai

```
### 4. Install ENV
### PostgreSQL 
PGHOST=localhost
PGPORT=5432
PGDATABASE=formula1
PGUSER=
PGPASSWORD=

### SSH tunnel info
SSH_HOST=
SSH_PORT=22
SSH_USER=
REMOTE_DB_PORT=5432
LOCAL_TUNNEL_PORT=5432


### Google Gemini 
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
### 6. Run the App

```bash
streamlit run app.py
```

> Replace `app.py` with the name of your main Streamlit script if different.

---

## 💡 Notes

* Every time you open a new terminal, remember to **activate the `.venv`**.
* To deactivate the environment:

```bash
deactivate
```

---

