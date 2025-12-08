import streamlit as st
import sqlite3
import pandas as pd
import openai
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional, Dict
from datetime import datetime
import json

# Load environment variables from .env file
load_dotenv()

# === CONFIGURATION ===
DATABASE_NAME = "jira_data.db"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

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
    
class ScrumMasterOutput(BaseModel):
    """Generic output from Scrum Master agent"""
    query_type: str = Field(..., description="Type of query: health/standup/assignment/general")
    analysis: str = Field(..., description="Natural language analysis")
    sql_query: Optional[str] = Field(None, description="SQL query used if applicable")
    structured_data: Optional[List[Dict]] = Field(None, description="Structured output data as list of records")
    recommendations: List[str] = Field(default_factory=list, description="Action items")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    class Config:
        arbitrary_types_allowed = True

# ----------------------------------------------------------------------------
# AI-02: Agent Persona Definition
# ----------------------------------------------------------------------------

class ScrumMasterAgent:
    """
    AI Scrum Master Agent with defined role, goal, and backstory
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
    """
    
    context_memory: List[Dict] = []  # Stores conversation history
    
    @classmethod
    def get_persona_prompt(cls) -> str:
        """Returns the agent persona as a system prompt"""
        return f"""Role: {cls.role}

Goal: {cls.goal}

Backstory: {cls.backstory}

You have access to a Jira database and must provide insights based on real data.
Always be specific, actionable, and supportive of the team."""

    @classmethod
    def add_to_context(cls, user_query: str, response: str):
        """Add interaction to context memory"""
        cls.context_memory.append({
            "timestamp": datetime.now().isoformat(),
            "query": user_query,
            "response": response
        })
        # Keep only last 10 interactions to avoid token limits
        if len(cls.context_memory) > 10:
            cls.context_memory.pop(0)
    
    @classmethod
    def get_context_summary(cls) -> str:
        """Get summary of recent conversation context"""
        if not cls.context_memory:
            return "No previous context."
        
        summary = "Recent conversation context:\n"
        for item in cls.context_memory[-3:]:  # Last 3 interactions
            summary += f"- User asked: {item['query'][:100]}...\n"
        return summary

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
    - summary (TEXT)
    - status (TEXT) - values like: 'To Do', 'In Progress', 'Done', 'Blocked', etc.
    - assignee (TEXT) - person's name or 'Unassigned'
    - priority (TEXT) - values like: 'High', 'Medium', 'Low', 'Critical', etc.
    - created (TEXT) - date in format YYYY-MM-DD
    - updated (TEXT) - date in format YYYY-MM-DD
    - time_spent (INTEGER) - time in seconds
    - parent_key (TEXT) - parent issue key if this is a subtask
    """
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

# ============================================================================
# AI AGENT PROCESSING FUNCTIONS
# ============================================================================

def classify_query_type(question: str) -> str:
    """Classify the type of user query"""
    question_lower = question.lower()
    
    if any(word in question_lower for word in ["health", "sprint", "project status"]):
        return "health"
    elif any(word in question_lower for word in ["standup", "daily", "what did", "working on"]):
        return "standup"
    elif any(word in question_lower for word in ["assign", "who should", "suggest", "recommend"]):
        return "assignment"
    else:
        return "general"

def generate_sql_from_question(question: str, query_type: str) -> str:
    """Use OpenAI GPT-4o to convert natural language question to SQL with agent context"""
    
    schema = get_db_schema()
    assignees = get_available_assignees()
    projects = get_available_projects()
    persona = ScrumMasterAgent.get_persona_prompt()
    context = ScrumMasterAgent.get_context_summary()
    
    system_prompt = f"""{persona}

{schema}

Available assignees: {', '.join(assignees[:20])}  
Available projects: {', '.join([f"{p[0]} ({p[1]})" for p in projects[:10]])}

{context}

Query Type: {query_type}

IMPORTANT RULES:
1. Return ONLY the SQL query, nothing else
2. No explanations, no markdown, no code blocks
3. Use proper SQLite syntax
4. For health queries: get status distribution, priorities, blocked issues
5. For standup queries: focus on specific assignee's recent activity
6. For assignment queries: analyze workload distribution
7. Always use proper string matching for names (use LIKE or exact match)
8. Use GROUP BY for aggregations
9. Use COUNT, SUM for metrics"""

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
    
    results_text = results_df.to_string(index=False, max_rows=20)
    persona = ScrumMasterAgent.get_persona_prompt()
    
    # Get appropriate template based on query type
    if query_type == "health":
        template_context = "This is a project health analysis query."
    elif query_type == "standup":
        template_context = "This is a standup summary query."
    elif query_type == "assignment":
        template_context = "This is a task assignment suggestion query."
    else:
        template_context = "This is a general query."
    
    system_prompt = f"""{persona}

{template_context}

Based on the SQL results, provide analysis and recommendations.
Be specific, actionable, and supportive."""

    user_prompt = f"""User asked: {question}

SQL query used: {sql_query}

Results:
{results_text}

Provide your analysis as a Scrum Master. Include:
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
            max_tokens=600
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
        
        # Add to context memory
        ScrumMasterAgent.add_to_context(question, analysis)
        
        return output
        
    except Exception as e:
        return ValidationHandler.create_fallback_output(query_type, str(e))

# ============================================================================
# STREAMLIT UI
# ============================================================================

def main():
    st.set_page_config(page_title="AI Scrum Master", page_icon="🤖", layout="wide")
    
    st.title("🤖 AI Scrum Master Agent")
    st.markdown("*Your intelligent Agile assistant with context-aware reasoning*")
    
    # Check for API key
    if not OPENAI_API_KEY:
        st.error("⚠️ OpenAI API key not found!")
        st.info("Please add your API key to the .env file")
        st.stop()
    
    # Sidebar
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
        st.markdown("### 🎯 Agent Capabilities")
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
        """)
        
        st.markdown("---")
        
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
        
        st.markdown("---")
        st.caption("Powered by ⚡ GPT-4o | Built with 🧠 Pydantic")
    
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
                            st.dataframe(pd.DataFrame(output.structured_data), use_container_width=True)
    
    # Chat input
    if prompt := st.chat_input("Ask about projects, team efficiency, health reports..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("🤔 Analyzing with AI Scrum Master agent..."):
                # Classify query type
                query_type = classify_query_type(prompt)
                
                # Generate SQL
                sql_query = generate_sql_from_question(prompt, query_type)
                
                # Execute SQL
                results_df, error = execute_sql(sql_query)
                
                if error:
                    output = ValidationHandler.create_fallback_output(query_type, error)
                    st.error(f"Query Error: {error}")
                    st.code(sql_query, language="sql")
                else:
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
                            st.dataframe(pd.DataFrame(output.structured_data), use_container_width=True)
                
                # Save to history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": output.analysis,
                    "structured_output": output
                })
    
    # Clear chat button
    if st.sidebar.button("🗑️ Clear Chat & Context"):
        st.session_state.messages = []
        ScrumMasterAgent.context_memory = []
        st.rerun()

if __name__ == "__main__":
    main()