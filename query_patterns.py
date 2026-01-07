"""
Smart Query Patterns Module
Handles common Jira queries that require domain knowledge translation
"""

from datetime import datetime, timedelta
import re

class QueryPattern:
    """Base class for query patterns"""
    def __init__(self, pattern, description, sql_template, requires_date=False):
        self.pattern = pattern  # Regex or keywords to match
        self.description = description
        self.sql_template = sql_template
        self.requires_date = requires_date
    
    def matches(self, query: str) -> bool:
        """Check if query matches this pattern"""
        query_lower = query.lower()
        if isinstance(self.pattern, str):
            return self.pattern in query_lower
        elif isinstance(self.pattern, list):
            return any(p in query_lower for p in self.pattern)
        elif hasattr(self.pattern, 'search'):  # Regex
            return self.pattern.search(query_lower) is not None
        return False
    
    def generate_sql(self, **kwargs) -> str:
        """Generate SQL from template with provided parameters"""
        if self.requires_date:
            kwargs['current_date'] = datetime.now().strftime("%Y-%m-%d")
        return self.sql_template.format(**kwargs)


class SmartQueryPatterns:
    """
    Collection of smart query patterns that map common Jira terminology
    to actual database queries
    """
    
    def __init__(self):
        self.patterns = []
        self._initialize_patterns()
    
    def _initialize_patterns(self):
        """Define all smart query patterns"""
        
        # ============================================================
        # STUCK/STALE TICKETS PATTERNS
        # ============================================================
        
        # Pattern 1: Stuck tickets (general)
        self.patterns.append(QueryPattern(
            pattern=["stuck ticket", "stuck issue", "stale ticket", "stale issue", "stagnant"],
            description="Issues in progress but not updated in 7+ days",
            sql_template="""
                SELECT issue_key, summary, status, assignee, updated, 
                       project_key, priority, 
                       julianday('now') - julianday(updated) as days_since_update
                FROM issues 
                WHERE status IN ('In Progress', 'In Review') 
                AND julianday('now') - julianday(updated) > 7
                ORDER BY days_since_update DESC
            """,
            requires_date=False
        ))
        
        # Pattern 2: Stuck tickets (specific project)
        self.patterns.append(QueryPattern(
            pattern=re.compile(r"stuck.*in\s+(\w+)|(\w+).*stuck"),
            description="Stuck issues in a specific project",
            sql_template="""
                SELECT issue_key, summary, status, assignee, updated, 
                       project_key, priority,
                       julianday('now') - julianday(updated) as days_since_update
                FROM issues 
                WHERE project_key = '{project_key}'
                AND status IN ('In Progress', 'In Review')
                AND julianday('now') - julianday(updated) > 7
                ORDER BY days_since_update DESC
            """,
            requires_date=False
        ))
        
        # Pattern 3: Tickets not updated in X days
        self.patterns.append(QueryPattern(
            pattern=re.compile(r"not updated.*(\d+)\s*days?|(\d+)\s*days?.*not updated"),
            description="Issues not updated in specified days",
            sql_template="""
                SELECT issue_key, summary, status, assignee, updated, 
                       project_key, priority,
                       julianday('now') - julianday(updated) as days_since_update
                FROM issues 
                WHERE julianday('now') - julianday(updated) > {days}
                ORDER BY days_since_update DESC
            """,
            requires_date=False
        ))
        
        # ============================================================
        # OVERDUE PATTERNS
        # ============================================================
        
        # Pattern 4: Overdue tickets
        self.patterns.append(QueryPattern(
            pattern=["overdue", "past due", "missed deadline"],
            description="Issues past their due date",
            sql_template="""
                SELECT issue_key, summary, status, assignee, duedate, 
                       project_key, priority,
                       julianday('{current_date}') - julianday(duedate) as days_overdue
                FROM issues 
                WHERE duedate IS NOT NULL 
                AND duedate < '{current_date}'
                AND status NOT IN ('Done', 'Closed', 'Cancelled')
                ORDER BY days_overdue DESC
            """,
            requires_date=True
        ))
        
        # Pattern 5: Due soon (next 3 days)
        self.patterns.append(QueryPattern(
            pattern=["due soon", "upcoming deadline", "deadline this week"],
            description="Issues due in next 3 days",
            sql_template="""
                SELECT issue_key, summary, status, assignee, duedate, 
                       project_key, priority,
                       julianday(duedate) - julianday('{current_date}') as days_remaining
                FROM issues 
                WHERE duedate IS NOT NULL 
                AND duedate >= '{current_date}'
                AND julianday(duedate) - julianday('{current_date}') <= 3
                AND status NOT IN ('Done', 'Closed')
                ORDER BY duedate ASC
            """,
            requires_date=True
        ))
        
        # ============================================================
        # BLOCKER PATTERNS
        # ============================================================
        
        # Pattern 6: Blocked tickets
        self.patterns.append(QueryPattern(
            pattern=["blocked issue", "blocked ticket", "blockers"],
            description="Issues with 'Blocked' status",
            sql_template="""
                SELECT issue_key, summary, status, assignee, updated, 
                       project_key, priority, description
                FROM issues 
                WHERE status = 'Blocked'
                ORDER BY priority DESC, updated DESC
            """,
            requires_date=False
        ))
        
        # ============================================================
        # WORKLOAD PATTERNS
        # ============================================================
        
        # Pattern 7: Overloaded team members
        self.patterns.append(QueryPattern(
            pattern=["overloaded", "too many tasks", "heavy workload"],
            description="Team members with 10+ open issues",
            sql_template="""
                SELECT assignee, 
                       COUNT(*) as total_tasks,
                       SUM(CASE WHEN priority = 'High' THEN 1 ELSE 0 END) as high_priority,
                       SUM(CASE WHEN priority = 'Critical' THEN 1 ELSE 0 END) as critical_priority
                FROM issues 
                WHERE status NOT IN ('Done', 'Closed', 'Cancelled')
                AND assignee != 'Unassigned'
                GROUP BY assignee
                HAVING COUNT(*) > 10
                ORDER BY total_tasks DESC
            """,
            requires_date=False
        ))
        
        # ============================================================
        # UNASSIGNED PATTERNS
        # ============================================================
        
        # Pattern 8: Unassigned high priority
        self.patterns.append(QueryPattern(
            pattern=["unassigned.*high", "high.*unassigned", "urgent.*unassigned"],
            description="High priority unassigned issues",
            sql_template="""
                SELECT issue_key, summary, status, priority, created, 
                       project_key, issue_type
                FROM issues 
                WHERE assignee = 'Unassigned'
                AND priority IN ('High', 'Critical')
                AND status NOT IN ('Done', 'Closed')
                ORDER BY 
                    CASE priority 
                        WHEN 'Critical' THEN 1 
                        WHEN 'High' THEN 2 
                        ELSE 3 
                    END,
                    created ASC
            """,
            requires_date=False
        ))
        
        # ============================================================
        # BUG PATTERNS
        # ============================================================
        
        # Pattern 9: Critical bugs
        self.patterns.append(QueryPattern(
            pattern=["critical bug", "urgent bug", "high priority bug"],
            description="Critical or high priority bugs",
            sql_template="""
                SELECT issue_key, summary, status, assignee, created, 
                       project_key, priority
                FROM issues 
                WHERE issue_type = 'Bug'
                AND priority IN ('Critical', 'High')
                AND status NOT IN ('Done', 'Closed', 'Resolved')
                ORDER BY 
                    CASE priority 
                        WHEN 'Critical' THEN 1 
                        WHEN 'High' THEN 2 
                        ELSE 3 
                    END,
                    created ASC
            """,
            requires_date=False
        ))
    
    def find_matching_pattern(self, query: str) -> tuple:
        """
        Find the best matching pattern for a query
        Returns: (QueryPattern, extracted_params) or (None, None)
        """
        query_lower = query.lower()
        
        for pattern in self.patterns:
            if pattern.matches(query):
                # Extract parameters if needed
                params = {}
                
                # Extract project key if mentioned
                project_match = re.search(r'\b([A-Z]{2,10})\b', query)
                if project_match and "project_key" in pattern.sql_template:
                    params['project_key'] = project_match.group(1)
                
                # Extract number of days if mentioned
                days_match = re.search(r'(\d+)\s*days?', query_lower)
                if days_match and "days" in pattern.sql_template:
                    params['days'] = int(days_match.group(1))
                
                return pattern, params
        
        return None, None
    
    def get_smart_sql(self, query: str) -> tuple:
        """
        Get SQL for a query if it matches a pattern
        Returns: (sql: str, description: str) or (None, None)
        """
        pattern, params = self.find_matching_pattern(query)
        
        if pattern:
            try:
                sql = pattern.generate_sql(**params)
                return sql, pattern.description
            except KeyError as e:
                print(f"Missing parameter for pattern: {e}")
                return None, None
        
        return None, None


# ============================================================
# HELPER FUNCTIONS FOR APP.PY
# ============================================================

def check_smart_pattern(query: str) -> tuple:
    """
    Check if query matches any smart pattern
    Returns: (has_pattern: bool, sql: str, description: str)
    """
    smart_patterns = SmartQueryPatterns()
    sql, description = smart_patterns.get_smart_sql(query)
    
    if sql:
        return True, sql, description
    return False, None, None


def get_pattern_suggestions(query: str) -> list:
    """
    Get suggestions for queries that might need smart patterns
    Returns: list of suggested reformulations
    """
    suggestions = []
    query_lower = query.lower()
    
    if "stuck" in query_lower or "stale" in query_lower:
        suggestions.append("Try: 'show me stuck tickets' or 'list stale issues'")
    
    if "overdue" in query_lower or "late" in query_lower:
        suggestions.append("Try: 'show me overdue tickets' or 'list missed deadlines'")
    
    if "blocked" in query_lower or "blocker" in query_lower:
        suggestions.append("Try: 'show me blocked issues'")
    
    return suggestions


# ============================================================
# TESTING
# ============================================================

if __name__ == "__main__":
    """Test the patterns"""
    smart = SmartQueryPatterns()
    
    test_queries = [
        "list me all stuck tickets",
        "show me stuck issues in AFSP",
        "what tickets haven't been updated in 10 days",
        "show overdue tasks",
        "list blocked issues",
        "who is overloaded",
        "show unassigned high priority tickets"
    ]
    
    print("Testing Smart Query Patterns\n" + "="*60)
    
    for query in test_queries:
        sql, desc = smart.get_smart_sql(query)
        if sql:
            print(f"\nQuery: {query}")
            print(f"Description: {desc}")
            print(f"SQL Preview: {sql[:100]}...")
        else:
            print(f"\nQuery: {query}")
            print("No pattern matched")