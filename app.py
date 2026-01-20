import streamlit as st
import sqlite3
import pandas as pd
import openai
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, ConfigDict
from typing import List, Optional, Dict
from datetime import datetime
import json
import uuid
from query_patterns import *

# Load environment variables from .env file
load_dotenv()

# === CONFIGURATION ===
DATABASE_NAME = "jira_data.db"
CONTEXT_FOLDER = "Context"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Create Context folder if it doesn't exist
if not os.path.exists(CONTEXT_FOLDER):
    os.makedirs(CONTEXT_FOLDER)
    print(f"Created directory: {CONTEXT_FOLDER}")

# ============================================================================
# PHASE 2 - AI AGENT FOUNDATION
# ============================================================================

# ----------------------------------------------------------------------------
# AI-01: Pydantic Models for Structured Outputs
# ----------------------------------------------------------------------------

class TicketSummary(BaseModel):
    """Summary of a specific ticket/issue"""
    ticket_key: str = Field(..., description="Jira ticket key")
    summary: str = Field(..., description="Brief summary of the ticket")
    status: str = Field(..., description="Current status")
    assignee: str = Field(..., description="Assigned team member")
    priority: str = Field(..., description="Priority level")
    blockers: Optional[str] = Field(None, description="Any blockers or issues")
    
class SprintHealthReport(BaseModel):
    """Health report for a project/sprint"""
    project_key: str = Field(..., description="Project identifier")
    total_issues: int = Field(..., description="Total number of issues")
    completed_issues: int = Field(..., description="Completed issues")
    in_progress_issues: int = Field(..., description="Issues in progress")
    blocked_issues: int = Field(..., description="Blocked issues")
    completion_rate: float = Field(..., description="Completion percentage")
    health_status: str = Field(..., description="Overall health: Healthy/At Risk/Critical")
    recommendations: List[str] = Field(..., description="Action items and recommendations")
    
class StandupSummary(BaseModel):
    """Daily standup summary for team members"""
    team_member: str = Field(..., description="Team member name")
    completed_yesterday: List[str] = Field(..., description="Tasks completed")
    planned_today: List[str] = Field(..., description="Tasks planned for today")
    blockers: List[str] = Field(..., description="Any blockers or impediments")
    velocity: str = Field(..., description="Current velocity assessment")
    
class AssignmentSuggestion(BaseModel):
    """Suggestion for task assignment"""
    ticket_key: str = Field(..., description="Ticket to be assigned")
    suggested_assignee: str = Field(..., description="Recommended team member")
    reasoning: str = Field(..., description="Why this person is recommended")
    current_workload: int = Field(..., description="Assignee's current workload")
    
# class ScrumMasterOutput(BaseModel):
#     """Generic output from Scrum Master agent"""
#     query_type: str = Field(..., description="Type of query: health/standup/assignment/general")
#     analysis: str = Field(..., description="Natural language analysis")
#     sql_query: Optional[str] = Field(None, description="SQL query used if applicable")
#     structured_data: Optional[List[Dict]] = Field(None, description="Structured output data as list of records")
#     recommendations: List[str] = Field(default_factory=list, description="Action items")
#     timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    
#     class Config:
#         arbitrary_types_allowed = True

# Updated ScrumMasterOutput with ConfigDict for Pydantic's v2 compatibility
class ScrumMasterOutput(BaseModel):
    query_type: str
    analysis: str
    sql_query: Optional[str] = None
    structured_data: Optional[List[Dict]] = None
    recommendations: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    model_config = ConfigDict(arbitrary_types_allowed=True)

# ----------------------------------------------------------------------------
# Context Management System (Per-Session)
# ----------------------------------------------------------------------------

class ContextManager:
    """Manages conversation context per session with file persistence"""
    
    @staticmethod
    def get_session_id():
        """Get or create a unique session ID for this user"""
        if 'session_id' not in st.session_state:
            st.session_state.session_id = str(uuid.uuid4())
        return st.session_state.session_id
    
    @staticmethod
    def get_context_file_path():
        """Get the file path for this session's context"""
        session_id = ContextManager.get_session_id()
        return os.path.join(CONTEXT_FOLDER, f"context_{session_id}.json")
    
    @staticmethod
    def load_context():
        """Load context from file for this session"""
        file_path = ContextManager.get_context_file_path()
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    @staticmethod
    def save_context(context_data):
        """Save context to file for this session (keep last 5)"""
        file_path = ContextManager.get_context_file_path()
        
        # Keep only last 5 entries
        context_to_save = context_data[-5:] if len(context_data) > 5 else context_data
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(context_to_save, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving context: {e}")
    
    @staticmethod
    def add_to_context(user_query: str, response: str, sql_query: str = None):
        """Add interaction to context and save to file"""
        # Get current context
        if 'context' not in st.session_state:
            st.session_state.context = ContextManager.load_context()
        
        # Add new entry
        entry = {
            "timestamp": datetime.now().isoformat(),
            "query": user_query,
            "response": response,
            "sql_query": sql_query
        }
        
        st.session_state.context.append(entry)
        
        # Save to file (automatically keeps last 5)
        ContextManager.save_context(st.session_state.context)
    
    @staticmethod
    def get_context_summary():
        """Get summary of recent conversation context for LLM"""
        if 'context' not in st.session_state:
            st.session_state.context = ContextManager.load_context()
        
        if not st.session_state.context:
            return "No previous context in this session."
        
        summary = "Recent conversation context (last 5 interactions):\n"
        for i, item in enumerate(st.session_state.context[-5:], 1):
            summary += f"{i}. User asked: {item['query'][:100]}...\n"
            if item.get('sql_query'):
                summary += f"   (Query involved: {item['sql_query'][:80]}...)\n"
        
        return summary
    
    @staticmethod
    def clear_context():
        """Clear context for this session and delete file"""
        file_path = ContextManager.get_context_file_path()
        
        # Delete file if exists
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Deleted context file: {file_path}")
            except Exception as e:
                print(f"Error deleting context file: {e}")
        
        # Clear session state AND mark that context was just cleared
        st.session_state.context = []
        st.session_state.context_cleared = True  # Flag to indicate fresh start
    
    @staticmethod
    def get_context_for_sql_generation():
        """Get formatted context specifically for SQL generation"""
        # Check if context was just cleared
        if st.session_state.get('context_cleared', False):
            return "\n⚠️ CRITICAL: NO PREVIOUS CONTEXT EXISTS. This is a completely fresh query with ZERO prior conversation history. If user refers to 'this project', 'that team', 'those issues' - you MUST ask them to specify which project/team/issues they mean, as you have NO context to reference."
        
        # ALWAYS load from file to ensure fresh data
        current_context = ContextManager.load_context()
        
        if not current_context:
            return "\nNO PREVIOUS CONTEXT: This is a fresh query with no prior conversation history. If user uses pronouns like 'this', 'that', 'those', ask for clarification."
        
        # Get last interaction
        last_interaction = current_context[-1] if current_context else None
        
        if not last_interaction:
            return "\nNO PREVIOUS CONTEXT: This is a fresh query with no prior conversation history."
        
        context = "\nRECENT CONTEXT:\n"
        context += f"Previous question: {last_interaction['query']}\n"
        
        if last_interaction.get('sql_query'):
            # Extract key entities from previous query (projects, assignees, etc.)
            prev_sql = last_interaction['sql_query']
            
            # Try to find project references
            if 'project_key' in prev_sql and '=' in prev_sql:
                # Extract project key from SQL
                import re
                match = re.search(r"project_key\s*=\s*['\"](\w+)['\"]", prev_sql)
                if match:
                    project = match.group(1)
                    context += f"User was asking about project: {project}\n"
                    context += f"IMPORTANT: If the current question refers to 'this project', 'that project', or uses context words like 'it', 'there', 'those', assume they mean project '{project}'\n"
        
        return context

# ----------------------------------------------------------------------------
# AI-02: Agent Persona Definition (Updated to use ContextManager)
# ----------------------------------------------------------------------------

class ScrumMasterAgent:
    """
    AI Scrum Master Agent with defined role, goal, and backstory
    Note: Context is now managed per-session via ContextManager instead of
    context_memory: List[Dict] = []        (in version 2.2 line 117 & 419)
    """
    
    role = "Senior Scrum Master & Agile Coach"
    
    goal = """
    To facilitate team productivity, remove blockers, provide actionable insights,
    and ensure healthy sprint execution through data-driven analysis.
    """
    
    backstory = """
    You are an experienced Scrum Master with 10+ years in Agile environments.
    You have deep expertise in:
    - Sprint planning and execution
    - Team velocity tracking
    - Identifying and removing impediments
    - Data-driven decision making
    - Team performance optimization
    
    You are analytical yet empathetic, always focusing on team success.
    You speak clearly and provide actionable recommendations.
    You use data from Jira to back up your insights.
    You maintain context across the conversation and understand when users refer to previous topics.
    """
    
    @classmethod
    def get_persona_prompt(cls) -> str:
        """Returns the agent persona as a system prompt"""
        return f"""Role: {cls.role}

Goal: {cls.goal}

Backstory: {cls.backstory}

You have access to a Jira database and must provide insights based on real data.
Always be specific, actionable, and supportive of the team."""

# ----------------------------------------------------------------------------
# AI-03: Task Templates (Reusable Prompts)
# ----------------------------------------------------------------------------

class TaskTemplates:
    """Predefined templates for common Scrum Master tasks"""
    
    @staticmethod
    def project_health_template(project_key: str) -> str:
        """Template for analyzing project health"""
        return f"""Analyze the health of project {project_key}.

Provide a comprehensive health report including:
1. Total issues and their status distribution
2. Completion rate and velocity
3. Blocked issues and their impact
4. Priority distribution
5. Health status (Healthy/At Risk/Critical)
6. Specific recommendations to improve project health

Use data from the database to support your analysis."""

    @staticmethod
    def standup_summary_template(team_member: str) -> str:
        """Template for generating standup summaries"""
        return f"""Generate a standup summary for {team_member}.

Include:
1. What they completed recently (status = 'Done', recently updated)
2. What they're currently working on (status = 'In Progress')
3. Any blockers or impediments (status = 'Blocked')
4. Their current workload and velocity

Format this as a brief standup update."""

    @staticmethod
    def assignment_suggestion_template() -> str:
        """Template for suggesting task assignments"""
        return """Analyze unassigned tasks and suggest optimal assignments.

Consider:
1. Current workload of each team member
2. Task priority and complexity
3. Team member's recent completion rate
4. Balance across the team

Provide specific assignment recommendations with reasoning."""

    @staticmethod
    def general_query_template(question: str) -> str:
        """Template for general queries"""
        return f"""Answer the following question about the Jira projects and team:

{question}

Provide a clear, data-driven answer with specific insights."""

# ----------------------------------------------------------------------------
# AI-04: Model Validation and Error Handling
# ----------------------------------------------------------------------------

class ValidationHandler:
    """Handles Pydantic model validation and errors"""
    
    @staticmethod
    def validate_and_parse(model_class: BaseModel, data: Dict) -> tuple:
        """
        Validates data against Pydantic model
        Returns: (success: bool, result: Model or error message)
        """
        try:
            validated_model = model_class(**data)
            return True, validated_model
        except ValidationError as e:
            error_msg = f"Validation Error: {str(e)}"
            return False, error_msg
    
    @staticmethod
    def create_fallback_output(query_type: str, error: str) -> ScrumMasterOutput:
        """Creates a fallback output when validation fails"""
        return ScrumMasterOutput(
            query_type=query_type,
            analysis=f"I encountered an issue processing your request: {error}",
            recommendations=["Please try rephrasing your question", "Check if the data exists in the system"]
        )

# ----------------------------------------------------------------------------
# AI-05: Static Testing Functions (for offline validation)
# ----------------------------------------------------------------------------

class StaticTester:
    """Functions for testing agent logic with static inputs"""
    
    @staticmethod
    def test_pydantic_models():
        """Test all Pydantic models with sample data"""
        tests = []
        
        # Test TicketSummary
        try:
            ticket = TicketSummary(
                ticket_key="TEST-123",
                summary="Sample ticket",
                status="In Progress",
                assignee="John Doe",
                priority="High"
            )
            tests.append(("TicketSummary", True, str(ticket)))
        except Exception as e:
            tests.append(("TicketSummary", False, str(e)))
        
        # Test SprintHealthReport
        try:
            health = SprintHealthReport(
                project_key="TEST",
                total_issues=100,
                completed_issues=75,
                in_progress_issues=20,
                blocked_issues=5,
                completion_rate=75.0,
                health_status="Healthy",
                recommendations=["Keep up the good work"]
            )
            tests.append(("SprintHealthReport", True, str(health)))
        except Exception as e:
            tests.append(("SprintHealthReport", False, str(e)))
        
        return tests
    
    @staticmethod
    def test_agent_persona():
        """Test agent persona initialization"""
        persona = ScrumMasterAgent.get_persona_prompt()
        return len(persona) > 0, persona[:200]
    
    @staticmethod
    def test_task_templates():
        """Test all task templates"""
        templates = {
            "health": TaskTemplates.project_health_template("TEST"),
            "standup": TaskTemplates.standup_summary_template("John Doe"),
            "assignment": TaskTemplates.assignment_suggestion_template()
        }
        return all(len(t) > 0 for t in templates.values()), templates

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def get_db_schema():
    """Get database schema for context"""
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
    - summary (TEXT) - brief title of the issue
    - description (TEXT) - detailed description of work (CAN BE NULL)
    - status (TEXT) - values like: 'To Do', 'In Progress', 'Done', 'Blocked', etc.
    - assignee (TEXT) - person's name or 'Unassigned'
    - reporter (TEXT) - person who created the issue
    - priority (TEXT) - 'High', 'Medium', 'Low', 'Critical', etc.
    - issue_type (TEXT) - 'Bug', 'Story', 'Task', 'Epic', etc.
    - labels (TEXT) - comma-separated tags (CAN BE NULL)
    - story_points (REAL) - effort estimate (CAN BE NULL)
    - created (TEXT) - creation date in YYYY-MM-DD
    - updated (TEXT) - last update date in YYYY-MM-DD
    - duedate (TEXT) - deadline in YYYY-MM-DD (CAN BE NULL)
    - resolution (TEXT) - how it was resolved like 'Done', 'Won't Do' (NULL if unresolved)
    - time_spent (INTEGER) - actual time spent in seconds
    - time_estimate (INTEGER) - original time estimate in seconds
    - parent_key (TEXT) - parent issue key if this is a subtask
    
    EVALUATION QUERIES:
    When user asks to evaluate deadlines or feasibility:
    1. Get issue details: description, status, duedate, time_estimate, assignee
    2. Consider: complexity from description, time remaining, current progress (status)
    3. Provide intelligent assessment with reasoning
    """
    # Add to the Above, if the DB behaves differently, same goes for description as well. (check v3.2.2 when it was added.)
    # IMPORTANT: When querying duedate, ALWAYS check if it is NULL. If duedate IS NULL, explicitly state "No due date set" in your response.

    return schema

def execute_sql(query):
    """Execute SQL query and return results as DataFrame. Handles multiple queries."""
    try:
        # Check if there are multiple queries (separated by semicolons)
        queries = [q.strip() for q in query.split(';') if q.strip()]
        
        if len(queries) == 0:
            return None, "No valid SQL query provided"
        
        conn = sqlite3.connect(DATABASE_NAME)
        
        if len(queries) == 1:
            # Single query - execute normally
            df = pd.read_sql_query(queries[0], conn)
            conn.close()
            return df, None
        else:
            # Multiple queries - execute each and combine results
            all_results = []
            for i, q in enumerate(queries):
                try:
                    df = pd.read_sql_query(q, conn)
                    # Add a column to identify which query this came from
                    df['query_section'] = f"Query_{i+1}"
                    all_results.append(df)
                except Exception as e:
                    # If one query fails, add error info
                    error_df = pd.DataFrame({
                        'error': [f"Query {i+1} failed: {str(e)}"],
                        'query_section': [f"Query_{i+1}"]
                    })
                    all_results.append(error_df)
            
            conn.close()
            
            # Combine all results into one DataFrame
            combined_df = pd.concat(all_results, ignore_index=True, sort=False)
            return combined_df, None
            
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

# ============================================================================
# AI AGENT PROCESSING FUNCTIONS
# ============================================================================

def get_issue_key_from_context():
    """Extract issue key from recent context if user refers to 'this project' or 'this issue'"""
    current_context = ContextManager.load_context()
    
    if not current_context:
        return None
    
    last_interaction = current_context[-1]
    if last_interaction.get('sql_query'):
        import re
        # Try to find issue_key in the SQL
        match = re.search(r"issue_key\s*=\s*['\"]([A-Z]+-\d+)['\"]", last_interaction['sql_query'])
        if match:
            return match.group(1)
    
    return None

def validate_evaluation_prerequisites(issue_key):
    """
    Check if issue has description and duedate before attempting evaluation.
    Returns: (valid: bool, message: str, has_description: bool, has_duedate: bool)
    """
    if not issue_key:
        return False, "I'm not sure which issue you're referring to. Please specify an issue key (e.g., AFSP-95).", False, False
    
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT description, duedate 
            FROM issues 
            WHERE issue_key = ?
        """, (issue_key,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return False, f"Issue {issue_key} not found in the database.", False, False
        
        description, duedate = result
        
        # STRICT validation - check for None, empty string, or whitespace-only
        has_desc = description is not None and len(description.strip()) > 0
        has_due = duedate is not None and len(duedate.strip()) > 0
        
        print(f"DEBUG: Issue {issue_key} - Description: '{description}' (has_desc={has_desc}), Duedate: '{duedate}' (has_due={has_due})")
        
        # Check what's missing
        if not has_desc and not has_due:
            return False, f"❌ **Cannot evaluate deadline for {issue_key}**\n\n**Missing:**\n- Description not available\n- Deadline not set\n\n**Required:** Both description and deadline are needed for evaluation.", False, False
        elif not has_desc:
            return False, f"❌ **Cannot evaluate deadline for {issue_key}**\n\n**Missing:**\n- Description not available\n\n**Why this matters:** I need to understand the task scope and complexity to assess if the deadline is realistic.\n\n**Suggestion:** Add a description in Jira, then ask me again.", False, True
        elif not has_due:
            return False, f"❌ **Cannot evaluate deadline for {issue_key}**\n\n**Missing:**\n- Deadline not set\n\n**Why this matters:** There's no deadline to evaluate.\n\n**Suggestion:** Set a due date in Jira, then ask me to evaluate it.", True, False
        
        return True, "Valid", True, True
        
    except Exception as e:
        print(f"ERROR in validation: {e}")
        return False, f"Error checking issue: {str(e)}", False, False

def classify_query_type(question: str) -> str:
    """Classify the type of user query"""
    question_lower = question.lower()
    
    # Check for greetings/casual conversation first
    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "thanks", "thank you"]
    farewells = ["bye", "goodbye", "good bye", "see you", "later"]
    
    # Check for farewells (triggers context cleanup)
    if any(farewell == question_lower.strip() or question_lower.strip().startswith(farewell + " ") for farewell in farewells):
        return "farewell"
    
    # Check for greetings
    if any(greeting == question_lower.strip() or question_lower.strip().startswith(greeting + " ") for greeting in greetings):
        return "greeting"
    
    # Check for ADVANCED queries (special handling)
    if "advanced" in question_lower:
        if "health" in question_lower:
            return "advanced_health"
        elif "standup" in question_lower:
            return "advanced_standup"
        
    # Check for evaluation queries (needs special handling)
    if any(word in question_lower for word in ["is this correct", "is this a correct", "feasible", "realistic", "assess", "reasonable deadline", "evaluate deadline", "deadline correct"]):
        return "evaluation"
    
    if any(word in question_lower for word in ["health", "sprint", "project status"]):
        return "health"
    elif any(word in question_lower for word in ["standup", "daily", "what did", "working on"]):
        return "standup"
    elif any(word in question_lower for word in ["assign", "who should", "suggest", "recommend"]):
        return "assignment"
    elif any(word in question_lower for word in ["list", "show me", "give me", "all team", "all project", "all member"]):
        return "list"
    else:
        return "general"

def generate_sql_from_question(question: str, query_type: str) -> str:
    """Use OpenAI GPT-4o to convert natural language question to SQL with agent context"""
    
    # FIRST: Check if this matches a smart pattern
    has_pattern, smart_sql, pattern_desc = check_smart_pattern(question)
    
    if has_pattern:
        print(f"Smart pattern matched: {pattern_desc}")
        # print(f"✓ Generated SQL: {smart_sql[:100]}...")
        return smart_sql
    
    # FALLBACK: Use LLM for non-pattern queries
    schema = get_db_schema()
    assignees = get_available_assignees()
    projects = get_available_projects()
    persona = ScrumMasterAgent.get_persona_prompt()
    context = ContextManager.get_context_for_sql_generation()           # Updated to use ContextManager
    
    # Add current date context
    from datetime import datetime
    current_date = datetime.now().strftime("%Y-%m-%d")
    print(f"Current date for SQL generation: {current_date}")
    
    system_prompt = f"""{persona}

{schema}

Available assignees: {', '.join(assignees[:20])}  
Available projects: {', '.join([f"{p[0]} ({p[1]})" for p in projects[:10]])}

{context}

CURRENT DATE: {current_date} (Use this for calculating time remaining, overdue tasks, etc.)

Query Type: {query_type}

IMPORTANT RULES:
1. Return ONLY the SQL query, nothing else
2. No explanations, no markdown, no code blocks
3. Use proper SQLite syntax
4. PREFER SINGLE QUERIES: Try to get all needed data in ONE query using JOINs, subqueries, or UNION
5. If you absolutely need multiple queries, separate them with semicolons (they will be executed sequentially)
6. For health queries: Use CASE statements and subqueries to get status distribution, priorities, and blocked issues in ONE query
7. For standup queries: focus on specific assignee's recent activity
8. For assignment queries: analyze workload distribution
9. Always use proper string matching for names (use LIKE or exact match)
10. Use GROUP BY for aggregations
11. Use COUNT, SUM for metrics
12. PAY ATTENTION TO CONTEXT: If user says "these", "this", "that project", "these issues", refer to the context above to understand what they mean
13. For duedate/deadline queries: ALWAYS SELECT duedate column. If result is NULL, tell user "No due date set"
14. NEVER substitute updated date for duedate - they are different fields
15. For EVALUATION queries: Always select description, duedate, status, time_estimate, created, assignee, issue_type
- ALWAYS compute deadline_status using CURRENT DATE
- Use julianday() for date comparison
- Return a column named deadline_status with values:
  'OVERDUE', 'DUE TODAY', or 'ON TRACK'
Example for EVALUATION queries (DEADLINE STATUS):
CASE
  WHEN duedate IS NULL THEN 'NO DEADLINE'
  WHEN julianday(duedate) < julianday('2025-12-18') THEN 'OVERDUE'
  WHEN julianday(duedate) = julianday('2025-12-18') THEN 'DUE TODAY'
  ELSE 'ON TRACK'
END AS deadline_status

EXAMPLE for project health (SINGLE QUERY):
SELECT 
  'Status Distribution' as metric_type,
  status as category,
  COUNT(*) as count
FROM issues 
WHERE project_key = 'ABC'
GROUP BY status
UNION ALL
SELECT 
  'Priority Distribution' as metric_type,
  priority as category,
  COUNT(*) as count
FROM issues 
WHERE project_key = 'ABC'
GROUP BY priority;

CRITICAL:
- NEVER say a task has "ample time" unless deadline_status = 'ON TRACK'
- If deadline_status = 'OVERDUE', explicitly say the deadline has already passed
- Do NOT infer timelines from status alone
"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0,
            max_tokens=500
        )
        
        sql_query = response.choices[0].message.content.strip()
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
        
        return sql_query
    except Exception as e:
        return f"Error generating SQL: {str(e)}"

def generate_structured_response(question: str, query_type: str, sql_query: str, results_df: pd.DataFrame) -> ScrumMasterOutput:
    """Generate structured response using Pydantic models"""
    
    if results_df is None or results_df.empty:
        return ValidationHandler.create_fallback_output(query_type, "No data found")
    
    results_text = results_df.to_string(index=False, max_rows=100)  # Increased from 20 to 100
    persona = ScrumMasterAgent.get_persona_prompt()
    
    # Get appropriate template based on query type
    if query_type == "health":
        template_context = "This is a project health analysis query."
    elif query_type == "standup":
        template_context = "This is a standup summary query."
    elif query_type == "assignment":
        template_context = "This is a task assignment suggestion query."
    elif query_type == "list":
        template_context = "This is a list query. Show ALL items from the data clearly."
    else:
        template_context = "This is a general query."
    
    system_prompt = f"""{persona}

{template_context}

Based on the SQL results, provide analysis and recommendations.
Be specific, actionable, and supportive.

IMPORTANT: If the user asked to "list" or "show" items (team members, projects, etc.), 
you MUST display ALL items from the results clearly, not just summarize them."""

    user_prompt = f"""User asked: {question}

SQL query used: {sql_query}

Results (showing up to 100 rows):
{results_text}

Provide your response. If this is a LIST query, format it clearly:
1. Start with a brief intro
2. List ALL items from the data (use bullet points or numbered list)
3. End with a summary count

If this is an ANALYSIS query, include:
1. Clear summary of the data
2. Key insights and patterns
3. At least 2-3 specific recommendations
4. Any concerns or blockers to address"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=5000  # Increased from 1000 to handle longer lists
        )
        
        analysis = response.choices[0].message.content.strip()
        
        # Extract recommendations from the analysis
        recommendations = []
        lines = analysis.split('\n')
        for line in lines:
            if any(keyword in line.lower() for keyword in ['recommend', 'suggest', 'should', 'consider', 'action']):
                recommendations.append(line.strip('- •'))
        
        # Create structured output
        output = ScrumMasterOutput(
            query_type=query_type,
            analysis=analysis,
            sql_query=sql_query,
            structured_data=results_df.to_dict('records'),
            recommendations=recommendations[:5] if recommendations else ["Continue monitoring the situation"]
        )
        
        # Add to context memory using ContextManager
        ContextManager.add_to_context(question, analysis, sql_query)
        
        return output
        
    except Exception as e:
        return ValidationHandler.create_fallback_output(query_type, str(e))

# ============================================================================
# STREAMLIT UI
# ============================================================================

def main():
    st.set_page_config(page_title="AI Scrum Master", page_icon="🤖", layout="wide")
    
    # # Add logo
    # st.image("assets\logo-1.png", width=120)
    
    # Header with title (left) and version (right)
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("## 🤖 AI Scrum Master Agent")
    with col2:
        st.markdown(
            "<p style='text-align: right; font-size: 20px; margin-top: 18px;'><b>Version 3.5</b></p>",
            unsafe_allow_html=True
        )
    st.markdown("*Your intelligent Agile assistant with context-aware reasoning*")
    
    # Check for API key
    if not OPENAI_API_KEY:
        st.error("⚠️ OpenAI API key not found!")
        st.info("Please add your API key to the .env file")
        st.stop()
    
    # Sidebar
    # with st.sidebar:
    #     st.image("assets/logo-1.png", width=100)
    #     # st.markdown("---")
    #     # st.header("📊 Quick Stats")
    #     st.markdown("<h3 style='font-size:22px;'>📊 Quick Stats</h3>", unsafe_allow_html=True)

    with st.sidebar:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image("assets/logo-1.png", width=100)
        st.markdown("<h3 style='font-size:22px;'>📊 Quick Stats</h3>", unsafe_allow_html=True)        

        try:
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM projects")
            project_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM issues")
            issue_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT assignee) FROM issues WHERE assignee != 'Unassigned'")
            assignee_count = cursor.fetchone()[0]
            
            # st.metric("Total Projects", project_count)
            # st.metric("Total Issues", issue_count)
            # st.metric("Team Members", assignee_count)

            stats_df = pd.DataFrame({
                "Metric": ["Total Projects", "Total Issues", "Team Members"],
                "Count": [project_count, issue_count, assignee_count]
            })

            st.table(stats_df.set_index("Metric"))
            
            conn.close()
        except:
            st.error("Database not found!")
        
        # st.markdown("---")

        # st.markdown("### 🎯 Agent Capabilities")
        st.markdown("<h3 style='font-size:22px;'>🎯 Agent Capabilities</h3>", unsafe_allow_html=True)

        st.markdown("""
        **Project Health Analysis**
        - Sprint velocity & completion
        - Blocker identification
        
        **Team Performance**
        - Standup summaries
        - Workload distribution
        
        **Smart Assignments**
        - Optimal task allocation
        - Capacity planning
        
        **Context-Aware**
        - Remembers last 5 interactions
        - Understands follow-up questions
        """)
        
        st.markdown("---")
        
        # Show session info
        session_id = ContextManager.get_session_id()
        st.caption(f"🔑 Session: {session_id[:8]}...")
        
        # Load context count
        if 'context' not in st.session_state:
            st.session_state.context = ContextManager.load_context()
        
        context_count = len(st.session_state.context)
        st.caption(f"💬 Context: {context_count}/5 interactions saved")
        
        # Testing interface
        with st.expander("🧪 Run Tests"):
            if st.button("Test Pydantic Models"):
                tests = StaticTester.test_pydantic_models()
                for name, success, result in tests:
                    if success:
                        st.success(f"✅ {name}")
                    else:
                        st.error(f"❌ {name}: {result}")
            
            if st.button("Test Agent Persona"):
                success, persona = StaticTester.test_agent_persona()
                st.write(persona)
            
            if st.button("View Context File"):
                context = ContextManager.load_context()
                if context:
                    st.json(context)
                else:
                    st.info("No context saved yet")
        
        st.markdown("---")

        # st.caption("Made by 👤 |  Powered by ⚡")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Show structured data if available
            if message["role"] == "assistant" and "structured_output" in message:
                output = message["structured_output"]
                
                # Show recommendations in a nice format
                if output.recommendations:
                    with st.expander("💡 Recommendations"):
                        for rec in output.recommendations:
                            st.markdown(f"- {rec}")
                
                # Show SQL and data
                if output.sql_query:
                    with st.expander("🔍 View SQL Query & Data"):
                        st.code(output.sql_query, language="sql")
                        if output.structured_data:
                            st.dataframe(pd.DataFrame(output.structured_data), width='content')
    
    # Chat input
    if prompt := st.chat_input("Ask about projects, team efficiency, health reports..."):
        # Classify query type FIRST (before adding to messages)
        query_type = classify_query_type(prompt)
        
        # Handle farewells IMMEDIATELY (clear context, no SQL, no saving to context)
        if query_type == "farewell":
            # Clear context file FIRST
            ContextManager.clear_context()
            
            # Clear chat history completely
            st.session_state.messages = []
            
            # Add only the farewell exchange to fresh chat
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            farewell_responses = {
                "bye": "Goodbye! I've completely erased all memory of our conversation. If you ask me about 'that project' or 'those issues' next, I won't know what you mean - you'll need to be specific!",
                "goodbye": "See you later! Everything has been wiped clean. Next question = brand new conversation with zero memory.",
                "good bye": "Take care! All context deleted. I won't remember anything we just discussed!",
                "see you": "See you! Memory wiped. Next query starts from scratch!",
                "later": "Catch you later! Context completely erased!"
            }
            
            # Find matching farewell
            response = "Goodbye! Memory wiped. Next question = fresh start!"
            for key, value in farewell_responses.items():
                if key in prompt.lower():
                    response = value
                    break
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": response
            })
            
            # Display the messages
            with st.chat_message("user"):
                st.markdown(prompt)
            
            with st.chat_message("assistant"):
                st.markdown(response)
                st.success("✨ All context erased!")
                st.warning("⚠️ I won't remember what we just talked about. Be specific in your next question!")
                
            # Force rerun to show empty context
            st.rerun()
        
        # Handle greetings (no SQL needed, no context saving for casual greetings)
        elif query_type == "greeting":
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            with st.chat_message("assistant"):
                greeting_responses = {
                    "hi": "Hello! I'm your AI Scrum Master. How can I help you with your projects and team today?",
                    "hello": "Hi there! Ready to dive into your Jira data? Ask me anything about your projects, team performance, or sprint health!",
                    "hey": "Hey! What would you like to know about your projects or team?",
                    "good morning": "Good morning! Let's make today productive. What can I help you analyze?",
                    "good afternoon": "Good afternoon! How can I assist with your Agile insights today?",
                    "good evening": "Good evening! What would you like to explore in your Jira data?",
                    "thanks": "You're welcome! Feel free to ask anything else about your projects.",
                    "thank you": "Happy to help! Let me know if you need anything else."
                }
                
                # Find matching greeting
                response = "Hello! How can I assist you with your Agile and Scrum needs today?"
                for key, value in greeting_responses.items():
                    if key in prompt.lower():
                        response = value
                        break
                
                st.markdown(response)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response
                })
        
        # Regular queries - need SQL and context saving
        else:
            # Clear the context_cleared flag if it exists (user is asking a new real question)
            if 'context_cleared' in st.session_state:
                del st.session_state['context_cleared']
            
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            with st.chat_message("assistant"):
                # Special handling for evaluation queries
                if query_type == "evaluation":
                    # Get issue key from context
                    issue_key = get_issue_key_from_context()
                    
                    # Validate prerequisites BEFORE any SQL
                    is_valid, message, has_desc, has_due = validate_evaluation_prerequisites(issue_key)
                    
                    if not is_valid:
                        # Show error message with clear guidance
                        st.error(message)
                        
                        # Add helpful suggestions based on what's missing
                        if issue_key:
                            if not has_desc and not has_due:
                                st.info("💡 **To evaluate a deadline, I need:**\n- A task description (to assess complexity)\n- A deadline (to evaluate)\n\nPlease add these in Jira first, then ask me again.")
                            elif not has_desc:
                                st.warning("⚠️ **Missing Description**\n\nI can't assess if the deadline is reasonable without knowing what work is involved. Please add a description in Jira.")
                                st.info(f"💡 Meanwhile, try: 'What's the status of {issue_key}?' or 'When was {issue_key} last updated?'")
                            elif not has_due:
                                st.warning("⚠️ **No Deadline Set**\n\nThere's no deadline to evaluate for this issue.")
                                st.info(f"💡 Try: 'What's the status of {issue_key}?' or 'Show me all overdue tasks'")
                        else:
                            st.info("💡 **How to use deadline evaluation:**\n1. First ask about a specific issue: 'Tell me about AFSP-95'\n2. Then ask: 'Is this deadline correct?'\n\nI'll remember which issue you asked about!")
                        
                        # Save error to history (no SQL, no structured output)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": message
                        })
                        # Don't rerun, don't add to context
                        
                    else:
                        # Valid evaluation - proceed normally
                        with st.spinner("🤔 Evaluating deadline feasibility..."):
                            sql_query = generate_sql_from_question(prompt, query_type)
                            results_df, error = execute_sql(sql_query)
                            
                            if error:
                                output = ValidationHandler.create_fallback_output(query_type, error)
                                st.error(f"Query Error: {error}")
                                st.code(sql_query, language="sql")
                            else:
                                output = generate_structured_response(prompt, query_type, sql_query, results_df)
                            
                            st.markdown(output.analysis)
                            
                            if output.recommendations:
                                with st.expander("💡 Recommendations"):
                                    for rec in output.recommendations:
                                        st.markdown(f"- {rec}")
                            
                            if output.sql_query:
                                with st.expander("🔍 View SQL Query & Data"):
                                    st.code(output.sql_query, language="sql")
                                    if output.structured_data:
                                        st.dataframe(pd.DataFrame(output.structured_data), width='content')
                            
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": output.analysis,
                                "structured_output": output
                            })
                            
                            st.rerun()
                
                # Normal query processing (not evaluation)
                else:
                    # Check if this is an advanced query
                    is_advanced = query_type in ["advanced_health", "advanced_standup"]
                    
                    # Check if query uses smart pattern
                    has_pattern, _, pattern_desc = check_smart_pattern(prompt)
                    
                    with st.spinner("🤔 Analyzing with AI Scrum Master agent..."):
                        # Show smart pattern indicator
                        if has_pattern:
                            st.info(f"🎯 Using optimized query pattern: {pattern_desc}")
                        elif is_advanced:
                            st.info(f"🚀 Generating comprehensive advanced analysis...")
                        
                        # Generate SQL
                        sql_query = generate_sql_from_question(prompt, query_type)
                        
                        # Execute SQL
                        results_df, error = execute_sql(sql_query)
                        
                        if error:
                            output = ValidationHandler.create_fallback_output(query_type, error)
                            st.error(f"Query Error: {error}")
                            st.code(sql_query, language="sql")
                        else:
                            # Handle advanced queries with custom formatting
                            if is_advanced and results_df is not None and not results_df.empty:
                                # Extract project key from query
                                project_match = re.search(r'\b([A-Z]{2,10})\b', prompt)
                                project_key = project_match.group(1) if project_match else "Unknown"
                                
                                if query_type == "advanced_health":
                                    formatted_response = format_advanced_health_response(results_df, project_key)
                                elif query_type == "advanced_standup":
                                    formatted_response = format_advanced_standup_response(results_df, project_key)

                                # FIX: Convert DataFrame to string type BEFORE creating output
                                # This prevents Arrow serialization errors with mixed types
                                results_df_clean = results_df.copy()
                                for col in results_df_clean.columns:
                                    results_df_clean[col] = results_df_clean[col].astype(str)
                                
                                # Create output object
                                output = ScrumMasterOutput(
                                    query_type=query_type,
                                    analysis=formatted_response,
                                    sql_query=sql_query,
                                    structured_data=results_df_clean.to_dict('records'),
                                    recommendations=["Review the key risks and take immediate actions as suggested"]
                                )
                                
                                # Add to context
                                ContextManager.add_to_context(prompt, formatted_response, sql_query)
                            else:
                                # Regular response generation
                                # Generate structured response
                                output = generate_structured_response(prompt, query_type, sql_query, results_df)
                        
                        # Display analysis
                        st.markdown(output.analysis)
                        
                        # Show recommendations
                        if output.recommendations:
                            with st.expander("💡 Recommendations"):
                                for rec in output.recommendations:
                                    st.markdown(f"- {rec}")
                        
                        # Show SQL and data
                        if output.sql_query:
                            with st.expander("🔍 View SQL Query & Data"):
                                st.code(output.sql_query, language="sql")
                                if output.structured_data:
                                    # Convert structured data to DataFrame and fix data types
                                    display_df = pd.DataFrame(output.structured_data)
                                    
                                    # Convert all columns to string for consistent display (avoids Arrow serialization issues)
                                    display_df = display_df.astype(str)
                                    
                                    st.dataframe(display_df, width='content')

                        # Save to history
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": output.analysis,
                            "structured_output": output
                        })
                        
                        # Force rerun to update context count in sidebar
                        st.rerun()
    
    # Clear chat button
    if st.sidebar.button("🗑️ Clear Chat & Context"):
        st.session_state.messages = []
        ContextManager.clear_context()
        st.rerun()

if __name__ == "__main__":
    main()