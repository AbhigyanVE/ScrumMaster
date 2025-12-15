import sqlite3
import json
import os
from datetime import datetime, timedelta
import sys

# === CONFIGURATION ===
JSON_FOLDER = "JSONs"  # Your folder with JSON files
DATABASE_NAME = "jira_data.db"  # This will be created

def create_database():
    """Creates the SQLite database and tables"""
    print("Creating database and tables...")

    # FIX: Delete the old database file if it exists
    if os.path.exists(DATABASE_NAME):
        print(f"Cleaning up existing database: {DATABASE_NAME}")
        try:
            os.remove(DATABASE_NAME)
            print("  [OK] Database file deleted.")
        except Exception as e:
            print(f"[ERROR] Could not delete {DATABASE_NAME}. Please check permissions or if the file is open: {e}")
            # Exit the program if the critical file cannot be deleted
            sys.exit(1)
        
    # Connect to SQLite (creates file if doesn't exist)
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Create Projects table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            project_key TEXT PRIMARY KEY,
            project_name TEXT,
            project_id TEXT,
            issue_count INTEGER
        )
    """)
    
    # Create Issues table with duedate
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            issue_key TEXT PRIMARY KEY,
            project_key TEXT,
            summary TEXT,
            status TEXT,
            assignee TEXT,
            priority TEXT,
            created TEXT,
            updated TEXT,
            duedate TEXT,
            time_spent INTEGER,
            parent_key TEXT,
            FOREIGN KEY (project_key) REFERENCES projects(project_key)
        )
    """)
    
    conn.commit()
    print("  [OK] Database created successfully!")
    return conn

def parse_datetime(date_string):
    """Safely parse Jira datetime strings"""
    if not date_string:
        return None
    try:
        # Jira format: 2024-01-15T10:30:45.123+0000
        # Or just date: 2024-01-15
        if 'T' in date_string:
            return date_string.split('T')[0]  # Get date part
        else:
            return date_string  # Already just a date
    except:
        return None

def insert_project_data(conn, json_folder):
    """Reads all JSON files and inserts data into database"""
    cursor = conn.cursor()
    
    # Get all JSON files
    json_files = [f for f in os.listdir(json_folder) if f.endswith('.json')]
    
    if not json_files:
        print(f"No JSON files found in '{json_folder}' folder!")
        return
    
    print(f"\nFound {len(json_files)} project files. Importing...")
    
    total_issues_imported = 0
    
    for json_file in json_files:
        filepath = os.path.join(json_folder, json_file)
        
        try:
            # Read the JSON file
            with open(filepath, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            # Extract project info
            project_key = project_data.get('key') or json_file.replace('_issues.json', '')
            project_name = project_data.get('name', 'Unknown')
            project_id = project_data.get('id', '')
            issue_count = project_data.get('issue_count', 0)
            
            # Insert project
            cursor.execute("""
                INSERT OR REPLACE INTO projects (project_key, project_name, project_id, issue_count)
                VALUES (?, ?, ?, ?)
            """, (project_key, project_name, project_id, issue_count))
            
            # Insert issues
            issues = project_data.get('issues', [])
            issues_imported = 0
            
            for issue in issues:
                issue_key = issue.get('key', '')
                fields = issue.get('fields', {})
                
                # Extract fields safely (handle None values)
                summary = fields.get('summary', '')
                status = (fields.get('status') or {}).get('name', 'Unknown')
                assignee_obj = fields.get('assignee')
                assignee = assignee_obj.get('displayName', 'Unassigned') if assignee_obj else 'Unassigned'
                priority_obj = fields.get('priority')
                priority = priority_obj.get('name', 'None') if priority_obj else 'None'
                created = parse_datetime(fields.get('created'))
                updated = parse_datetime(fields.get('updated'))
                duedate = parse_datetime(fields.get('duedate'))  # NEW: Extract duedate
                time_spent = fields.get('timespent', 0) or 0
                parent_obj = fields.get('parent')
                parent_key = parent_obj.get('key') if parent_obj else None
                
                cursor.execute("""
                    INSERT OR REPLACE INTO issues 
                    (issue_key, project_key, summary, status, assignee, priority, 
                     created, updated, duedate, time_spent, parent_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (issue_key, project_key, summary, status, assignee, priority,
                      created, updated, duedate, time_spent, parent_key))
                
                issues_imported += 1
            
            conn.commit()
            total_issues_imported += issues_imported
            print(f"  [OK] Imported {project_key}: {issues_imported} issues")
            
        except Exception as e:
            print(f"  [ER] Error importing {json_file}: {e}")
            continue
    
    print(f"\n=== Import Complete ===")
    print(f"Total issues imported: {total_issues_imported}")
    print(f"Database saved as: {DATABASE_NAME}")

def show_sample_data(conn):
    """Display some sample data to verify import"""
    cursor = conn.cursor()
    
    print("\n=== Sample Data ===")
    
    # Count projects
    cursor.execute("SELECT COUNT(*) FROM projects")
    project_count = cursor.fetchone()[0]
    print(f"\nProjects in database: {project_count}")
    
    # Count issues
    cursor.execute("SELECT COUNT(*) FROM issues")
    issue_count = cursor.fetchone()[0]
    print(f"Issues in database: {issue_count}")
    
    # Show some projects
    print("\n--- Projects ---")
    cursor.execute("SELECT project_key, project_name, issue_count FROM projects LIMIT 5")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} ({row[2]} issues)")
    
    # Show some issues
    print("\n--- Sample Issues ---")
    cursor.execute("""
        SELECT issue_key, summary, status, assignee, duedate 
        FROM issues 
        LIMIT 5
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1][:50]}...")
        print(f"    Status: {row[2]}, Assignee: {row[3]}, Due: {row[4] or 'Not set'}")

# === MAIN EXECUTION ===
if __name__ == "__main__":
    print("=" * 60)
    print("JIRA JSON to SQLite Converter")
    print("=" * 60)
    
    # Check if JSON folder exists
    if not os.path.exists(JSON_FOLDER):
        print(f"Error: Folder '{JSON_FOLDER}' not found!")
        print("Make sure your JSON files are in the 'JSONs' folder.")
        exit()
    
    # Create database
    conn = create_database()
    
    # Import data
    insert_project_data(conn, JSON_FOLDER)
    
    # Show sample
    show_sample_data(conn)
    
    # Close connection
    conn.close()
    
    print("\n[OK] Done! You can now use 'jira_data.db' with your chatbot.")
    print(f"  Database location: {os.path.abspath(DATABASE_NAME)}")