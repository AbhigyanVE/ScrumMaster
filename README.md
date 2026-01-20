# 🤖 AI Scrum Master Agent

![Static Badge](https://img.shields.io/badge/Version_3.4.2-_Web_App_Interface-blue)

An intelligent, context-aware AI Scrum Master that analyzes Jira data and helps teams stay productive by providing sprint health insights, standup summaries, workload analysis, and smart task assignment recommendations.

This project converts raw Jira project data into structured insights using **Streamlit**, **SQLite**, and **OpenAI**.


## ✨ Features

- **Project Health Analysis**
  - Sprint completion tracking  
  - Blocker and risk identification  
  - Priority and status distribution  

- **Team Insights**
  - Daily standup-style summaries  
  - Workload and velocity assessment  

- **Smart Task Assignment**
  - Recommends optimal assignees for tasks  
  - Balances workloads across team  

- **Context-Aware Conversations**
  - Remembers the last 5 interactions per user session  
  - Understands follow-up questions using session context  
  - Automatically clears context on farewell commands  

- **Structured AI Responses**
  - Uses **Pydantic** models for clean, validated outputs  
  - Displays raw SQL and structured data in the UI  

---

## 🏗️ Project Architecture

The project is built around three main components:

### 1. `extract_data.py`
- Fetches project and issue data from Jira using API tokens.
- Saves data as individual JSON files inside the `JSONs` folder.
- Each JSON file represents one Jira project.

### 2. `json_to_sqlite.py`
- Reads all JSON files from the `JSONs` folder.
- Converts and inserts the data into a SQLite database `jira_data.db`

### 3. `app.py`
- Streamlit-based web application.
- Connects to the SQLite database.
- Uses OpenAI to:
- Convert user questions to SQL
- Analyze query results
- Generate natural-language insights

### 4. `query_patterns.py`
- Made to identify and cater advanced queries like: *list me all the stuck tickets*.
- Currently developed only to cater stuck tickets and advanced project health reports but more functionalities can be added in future.


### 1'. `main.py`
- The program made to run all the 3 files mentioned above using 'nohup'.
- Fetching Data occurs at intervals of every 6hrs.

### 2'. `main_for_server.py`
- Built for the ssh server so that the functionality of 'main.py' can be achieved by initilisation using 'pm2'.



## 🧠 How It Works

1. User asks a question in natural language.
2. The system classifies the query type:
    - Health
    - Standup
    - Assignment
    - List
    - General
3. OpenAI converts the question into a **SQLite SQL query**.
4. The query is executed on `jira_data.db`.
5. Results are passed back to the AI for:
    - Analysis
    - Recommendations
    - Structured formatting
6. Conversation context is stored per session and reused when needed.

<br>

## 📁 Folder Structure
```sh
├── assets/
     ├── logo-1.png
     └── logo-2.png
├── Context/
     └── context_<session_id>.json
├── JSONs/
     └── <project>.json
├── app.py
├── extract_data.py
├── jira_data.db
├── json_to_sqlite.py
└── .env
```

## ▶️ Running the App

Run the Streamlit application with:
```sh
streamlit run app.py
```
Then open the local URL shown in your browser (usually http://localhost:8501).


## 🔐 Session & Context Management

- Each user session gets a unique ID.
- Context is stored in:
    * `Context/context_<session_id>.json`
- Only the last 5 interactions are preserved.
- Saying *“bye”*, *“goodbye”*, etc. clears:
    * Context files     *(only deletes the JSON file, Refer to Notes Section)*
    * Chat history
    * Session memory    *(presently facing some issues, refere to Notes Section)*

---

<br>

## Notes
### CURRENTLY IN DEVELOPMENT PHASE

1. If any change in LLM Response is to be found, <br> 
    *For Example:* In the previous versions, when it was asked about the *"Health of a Project"*, the response was there, but now, when the same question was being asked, then it gives an `ERROR`. <br>
    For these kind of **DISCREPANCIES** please check the **IMPORTANT RULES** section of the LLM present in `app.py` *(present in lines 563 in v3.1.1)*
2. The Response is **LIMITED**  to 1000 tokens, to increase tokens *(change `max_tokens=600` to `max_tokens=1000`  or more in `app.py`)*
3. The logo of **NM Agent** present in the Sidebar of Streamlit cannot be fixed, it will scroll *(Streamlit Limitation)*
4. The context count issue is fixed as of now.
5. Till v3.1, the deadline for an issue was not present in the database as it was not being extracted from jira. From v3.1.1 onwards, its fixed *(added `duedate` in line 22 of `extract_data.py`)*

### CURRENT BUGS *(Identified)*
6. *When any farewell message is sent as query, then in the frontend, the chat does get cleared, also the context json is also cleared but The LLM context cannot be cleared, hence, **THE CONTEXT IS NOT TRULY CLEARED**
6.1. This bug seems to be resolved in v3.1.1 but still needs a thorough check. *(Check assets/ContextNotes.png)*

7. **TO DO:**<br>
   Implement the function that when the bot is asked for how much time this issue is supposed to take, the chabot can answer it and also refer to the actual given deadline.