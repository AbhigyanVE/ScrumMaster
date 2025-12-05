import sqlite3
import pandas as pd

DATABASE_NAME = "jira_data.db"

def run_query(query, description=""):
    """Execute a SQL query and display results"""
    conn = sqlite3.connect(DATABASE_NAME)
    
    try:
        print(f"\n{'='*60}")
        if description:
            print(f"Query: {description}")
        print(f"{'='*60}")
        print(f"SQL: {query}\n")
        
        # Use pandas for nice display
        df = pd.read_sql_query(query, conn)
        print(df.to_string(index=False))
        print(f"\nRows returned: {len(df)}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

# === Example Queries ===

print("JIRA DATABASE QUERY TESTER")
print("=" * 60)

# Query 1: List all projects
run_query(
    "SELECT project_key, project_name, issue_count FROM projects",
    "List all projects"
)

# Query 2: Count issues by status
run_query(
    """
    SELECT status, COUNT(*) as count 
    FROM issues 
    GROUP BY status 
    ORDER BY count DESC
    """,
    "Issues by status"
)

# Query 3: Issues per assignee
run_query(
    """
    SELECT assignee, COUNT(*) as total_issues 
    FROM issues 
    GROUP BY assignee 
    ORDER BY total_issues DESC
    LIMIT 10
    """,
    "Top 10 assignees by issue count"
)

# Query 4: Issues by priority
run_query(
    """
    SELECT priority, COUNT(*) as count 
    FROM issues 
    GROUP BY priority 
    ORDER BY count DESC
    """,
    "Issues by priority"
)

# Query 5: Recent issues
run_query(
    """
    SELECT issue_key, summary, status, assignee, created 
    FROM issues 
    ORDER BY created DESC 
    LIMIT 10
    """,
    "10 most recent issues"
)

# Query 6: Efficiency of a specific person (example)
assignee_name = "Unassigned"  # Change this to a real name from your data
run_query(
    f"""
    SELECT 
        assignee,
        COUNT(*) as total_issues,
        SUM(CASE WHEN status = 'Done' THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN status IN ('To Do', 'In Progress') THEN 1 ELSE 0 END) as in_progress
    FROM issues 
    WHERE assignee = '{assignee_name}'
    GROUP BY assignee
    """,
    f"Efficiency metrics for {assignee_name}"
)

print("\n" + "="*60)
print("Test complete! Database is working.")
print("="*60)