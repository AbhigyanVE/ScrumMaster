import streamlit as st
import sqlite3
import pandas as pd
import openai
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# === CONFIGURATION ===
DATABASE_NAME = "jira_data.db"

# Get OpenAI API key from .env file
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# === DATABASE FUNCTIONS ===

def get_db_schema():
    """Get database schema for context"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    schema = """
    DATABASE SCHEMA:
    
    Table: projects
    - project_key (TEXT, PRIMARY KEY)
    - project_name (TEXT)
    - project_id (TEXT)
    - issue_count (INTEGER)
    
    Table: issues
    - issue_key (TEXT, PRIMARY KEY)
    - project_key (TEXT, FOREIGN KEY)
    - summary (TEXT)
    - status (TEXT) - values like: 'To Do', 'In Progress', 'Done', 'Blocked', etc.
    - assignee (TEXT) - person's name or 'Unassigned'
    - priority (TEXT) - values like: 'High', 'Medium', 'Low', 'Critical', etc.
    - created (TEXT) - date in format YYYY-MM-DD
    - updated (TEXT) - date in format YYYY-MM-DD
    - time_spent (INTEGER) - time in seconds
    - parent_key (TEXT) - parent issue key if this is a subtask
    """
    
    conn.close()
    return schema

def execute_sql(query):
    """Execute SQL query and return results as DataFrame"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df, None
    except Exception as e:
        return None, str(e)

def get_available_assignees():
    """Get list of all assignees for context"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT assignee FROM issues WHERE assignee != 'Unassigned' ORDER BY assignee")
    assignees = [row[0] for row in cursor.fetchall()]
    conn.close()
    return assignees

def get_available_projects():
    """Get list of all projects for context"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT project_key, project_name FROM projects ORDER BY project_key")
    projects = cursor.fetchall()
    conn.close()
    return projects

# === OPENAI FUNCTIONS ===

def generate_sql_from_question(question):
    """Use OpenAI GPT-4o to convert natural language question to SQL"""
    
    schema = get_db_schema()
    assignees = get_available_assignees()
    projects = get_available_projects()
    
    system_prompt = f"""You are a SQL expert. Convert the user's question into a valid SQLite query.

{schema}

Available assignees: {', '.join(assignees[:20])}  
Available projects: {', '.join([f"{p[0]} ({p[1]})" for p in projects[:10]])}

IMPORTANT RULES:
1. Return ONLY the SQL query, nothing else
2. No explanations, no markdown, no code blocks
3. Use proper SQLite syntax
4. For efficiency/performance questions about a person, calculate:
   - Total issues assigned
   - Issues completed (status = 'Done')
   - Issues in progress
   - Completion rate
5. For project health, check:
   - Total issues
   - Issues by status
   - Issues by priority
   - Blocked issues
6. Always use proper string matching for names (use LIKE or exact match)
7. Use GROUP BY for aggregations
8. Use COUNT, SUM for metrics"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",  # Best model available
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0,
            max_tokens=500
        )
        
        sql_query = response.choices[0].message.content.strip()
        
        # Clean up the response (remove markdown if present)
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
        
        return sql_query
    except Exception as e:
        return f"Error generating SQL: {str(e)}"

def generate_natural_response(question, query, results_df):
    """Use OpenAI GPT-4o to generate a natural language response from SQL results"""
    
    if results_df is None or results_df.empty:
        return "No data found for your question."
    
    # Convert dataframe to string representation
    results_text = results_df.to_string(index=False, max_rows=20)
    
    system_prompt = """You are an AI Scrum Master analyzing Jira project data.
Based on the SQL results provided, give a clear, concise answer to the user's question. 
- Be conversational and helpful
- Highlight key insights
- If it's about efficiency, mention completion rates and performance
- If it's about project health, mention bottlenecks and priorities
- Use bullet points for clarity when needed
- Keep it under 200 words"""

    user_prompt = f"""User asked: {question}

SQL query used: {query}

Results:
{results_text}

Provide your analysis:"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",  # Best model available
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating response: {str(e)}"

# === STREAMLIT UI ===

def main():
    st.set_page_config(page_title="AI Scrum Master", page_icon="🤖", layout="wide")
    
    st.title("🤖 AI Scrum Master")
    st.markdown("Ask me anything about your Jira projects and team performance!")
    
    # Check for API key
    if not OPENAI_API_KEY:
        st.error("⚠️ OpenAI API key not found!")
        st.info("Please add your API key to the .env file:")
        st.code("""
# Create a .env file in your project directory with:
OPENAI_API_KEY=sk-proj-your-actual-api-key-here
        """)
        st.stop()
    
    # Sidebar with info
    with st.sidebar:
        st.header("📊 Quick Stats")
        
        try:
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM projects")
            project_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM issues")
            issue_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT assignee) FROM issues WHERE assignee != 'Unassigned'")
            assignee_count = cursor.fetchone()[0]
            
            st.metric("Total Projects", project_count)
            st.metric("Total Issues", issue_count)
            st.metric("Team Members", assignee_count)
            
            conn.close()
        except:
            st.error("Database not found!")
        
        st.markdown("---")
        st.markdown("### 💡 Example Questions")
        st.markdown("""
        - What's the health of project X?
        - How efficient is [member name]?
        - Show me all blocked issues
        - Which projects have the most issues?
        - Who has the most open tasks?
        - What's the completion rate for [name]?
        """)
        
        st.markdown("---")
        st.caption("🤖 Powered by OpenAI GPT-4o")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Show SQL and results if available
            if message["role"] == "assistant" and "sql" in message:
                with st.expander("🔍 View SQL Query & Data"):
                    st.code(message["sql"], language="sql")
                    if message.get("dataframe") is not None:
                        st.dataframe(message["dataframe"], width="stretch")
    
    # Chat input
    if prompt := st.chat_input("Ask about projects, team efficiency, or anything..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # Step 1: Generate SQL
                sql_query = generate_sql_from_question(prompt)
                
                # Step 2: Execute SQL
                results_df, error = execute_sql(sql_query)
                
                if error:
                    response = f"I had trouble executing the query. Error: {error}\n\nGenerated SQL:\n```sql\n{sql_query}\n```"
                    st.error(response)
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": response,
                        "sql": sql_query
                    })
                else:
                    # Step 3: Generate natural language response
                    response = generate_natural_response(prompt, sql_query, results_df)
                    st.markdown(response)
                    
                    # Show expandable SQL and data
                    with st.expander("🔍 View SQL Query & Data"):
                        st.code(sql_query, language="sql")
                        st.dataframe(results_df, width="stretch")
                    
                    # Save to history
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response,
                        "sql": sql_query,
                        "dataframe": results_df
                    })
    
    # Clear chat button
    if st.sidebar.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

if __name__ == "__main__":
    main()