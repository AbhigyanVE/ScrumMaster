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
        
        # ============================================================
        # ADVANCED HEALTH ANALYSIS PATTERN
        # ============================================================
        
        # Pattern 10: Advanced health report
        self.patterns.append(QueryPattern(
            pattern=re.compile(r"advanced.*health|health.*advanced", re.IGNORECASE),
            description="Comprehensive health analysis with at-risk tickets, workload, and assignments",
            sql_template="""
                -- Status distribution
                SELECT 'status' as section, status as label, COUNT(*) as count, NULL as detail1, NULL as detail2, NULL as detail3
                FROM issues 
                WHERE project_key = '{project_key}'
                GROUP BY status
                
                UNION ALL
                
                -- At-risk tickets (stale in progress)
                SELECT 'at_risk_stale' as section, issue_key as label, 
                       CAST(julianday('now') - julianday(updated) as INTEGER) as count,
                       status as detail1, assignee as detail2, summary as detail3
                FROM issues
                WHERE project_key = '{project_key}'
                AND status IN ('In Progress', 'In Review')
                AND julianday('now') - julianday(updated) > 7
                
                UNION ALL
                
                -- At-risk tickets (unassigned high priority)
                SELECT 'at_risk_unassigned' as section, issue_key as label, 
                       0 as count, priority as detail1, status as detail2, summary as detail3
                FROM issues
                WHERE project_key = '{project_key}'
                AND assignee = 'Unassigned'
                AND priority IN ('High', 'Critical')
                AND status NOT IN ('Done', 'Closed')
                
                UNION ALL
                
                -- Blocked tickets
                SELECT 'at_risk_blocked' as section, issue_key as label,
                       0 as count, status as detail1, assignee as detail2, summary as detail3
                FROM issues
                WHERE project_key = '{project_key}'
                AND status = 'Blocked'
                
                UNION ALL
                
                -- Workload distribution
                SELECT 'workload' as section, assignee as label, COUNT(*) as count,
                       NULL as detail1, NULL as detail2, NULL as detail3
                FROM issues
                WHERE project_key = '{project_key}'
                AND status NOT IN ('Done', 'Closed', 'Cancelled')
                AND assignee != 'Unassigned'
                GROUP BY assignee
                
                UNION ALL
                
                -- Recent activity per developer
                SELECT 'recent_activity' as section, assignee as label,
                       COUNT(*) as count, NULL as detail1, NULL as detail2, NULL as detail3
                FROM issues
                WHERE project_key = '{project_key}'
                AND julianday('now') - julianday(updated) <= 1
                AND assignee != 'Unassigned'
                GROUP BY assignee
                
                ORDER BY section, count DESC;
            """,
            requires_date=False
        ))
        
        # ============================================================
        # ADVANCED STANDUP SUMMARY PATTERN
        # ============================================================
        
        # Pattern 11: Advanced standup summary
        self.patterns.append(QueryPattern(
            pattern=re.compile(r"advanced.*standup|standup.*advanced", re.IGNORECASE),
            description="Detailed standup with per-developer status and blockers",
            sql_template="""
                -- Completed yesterday (updated in last 24h and Done)
                SELECT 'completed_yesterday' as section, assignee as label, issue_key as count,
                       summary as detail1, updated as detail2, NULL as detail3
                FROM issues
                WHERE project_key = '{project_key}'
                AND status = 'Done'
                AND julianday('now') - julianday(updated) <= 1
                AND assignee != 'Unassigned'
                
                UNION ALL
                
                -- Working today (In Progress)
                SELECT 'working_today' as section, assignee as label, issue_key as count,
                       summary as detail1, status as detail2, NULL as detail3
                FROM issues
                WHERE project_key = '{project_key}'
                AND status IN ('In Progress', 'In Review')
                AND assignee != 'Unassigned'
                
                UNION ALL
                
                -- Blockers per developer
                SELECT 'blockers' as section, assignee as label, issue_key as count,
                       summary as detail1, 'Blocked' as detail2, description as detail3
                FROM issues
                WHERE project_key = '{project_key}'
                AND status = 'Blocked'
                AND assignee != 'Unassigned'
                
                UNION ALL
                
                -- Inactive developers (no updates in 7+ days)
                SELECT 'inactive' as section, assignee as label, 
                       CAST(julianday('now') - julianday(MAX(updated)) as INTEGER) as count,
                       NULL as detail1, NULL as detail2, NULL as detail3
                FROM issues
                WHERE project_key = '{project_key}'
                AND assignee != 'Unassigned'
                GROUP BY assignee
                HAVING julianday('now') - julianday(MAX(updated)) > 7
                
                ORDER BY section, label;
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


def format_advanced_health_response(results_df, project_key: str) -> str:
    """
    Format advanced health analysis into structured report
    """
    # Organize data by section
    status_data = results_df[results_df['section'] == 'status']
    at_risk_stale = results_df[results_df['section'] == 'at_risk_stale']
    at_risk_unassigned = results_df[results_df['section'] == 'at_risk_unassigned']
    at_risk_blocked = results_df[results_df['section'] == 'at_risk_blocked']
    workload_data = results_df[results_df['section'] == 'workload']
    
    # Calculate health score
    total_at_risk = len(at_risk_stale) + len(at_risk_unassigned) + len(at_risk_blocked)
    if total_at_risk == 0:
        health_score = "✅ GOOD"
    elif total_at_risk <= 3:
        health_score = "⚠️ WARNING"
    else:
        health_score = "🚨 CRITICAL"
    
    # Build response
    response = f"### 📊 Advanced Health Analysis for {project_key}\n\n"
    
    # Sprint Health Report
    response += "#### Sprint Health Report\n\n"
    response += "**Ticket Counts:**\n"
    for _, row in status_data.iterrows():
        response += f"- **{row['label']}**: {int(row['count'])}\n"
    
    # At-Risk Tickets
    response += "\n**At-Risk Tickets:**\n"
    if total_at_risk == 0:
        response += "- ✅ No at-risk tickets identified\n"
    else:
        # Stale tickets
        for _, row in at_risk_stale.iterrows():
            response += f"- **{row['label']}**: {row['detail3'][:50]}... – Stuck in {row['detail1']} for {int(row['count'])} days (Assignee: {row['detail2']})\n"
        
        # Unassigned high priority
        for _, row in at_risk_unassigned.iterrows():
            response += f"- **{row['label']}**: {row['detail3'][:50]}... – Unassigned {row['detail1']} priority\n"
        
        # Blocked
        for _, row in at_risk_blocked.iterrows():
            response += f"- **{row['label']}**: {row['detail3'][:50]}... – Blocked (Assignee: {row['detail2']})\n"
    
    response += f"\n**Health Score**: {health_score}\n\n"
    
    # Workload Distribution
    response += "#### Workload Distribution\n\n"
    if len(workload_data) > 0:
        for _, row in workload_data.iterrows():
            workload = int(row['count'])
            if workload > 10:
                emoji = "🔴"
            elif workload > 5:
                emoji = "🟡"
            else:
                emoji = "🟢"
            response += f"{emoji} **{row['label']}**: {workload} active tasks\n"
    else:
        response += "No active workload data available.\n"
    
    # Assignment Suggestions
    response += "\n#### Assignment Suggestions\n\n"
    if len(workload_data) >= 2:
        # Find overloaded and underloaded
        workload_sorted = workload_data.sort_values('count', ascending=False)
        overloaded = workload_sorted.iloc[0] if len(workload_sorted) > 0 else None
        underloaded = workload_sorted.iloc[-1] if len(workload_sorted) > 0 else None
        
        if overloaded is not None and underloaded is not None and overloaded['count'] - underloaded['count'] > 3:
            response += f"1. **Rebalance workload**\n"
            response += f"   - From: {overloaded['label']} ({int(overloaded['count'])} tasks)\n"
            response += f"   - To: {underloaded['label']} ({int(underloaded['count'])} tasks)\n"
            response += f"   - Reason: Significant workload imbalance\n"
            response += f"   - Expected Impact: Improved team velocity\n\n"
    
    # Handle unassigned
    if len(at_risk_unassigned) > 0:
        response += f"2. **Assign high-priority unassigned tickets**\n"
        for idx, row in at_risk_unassigned.iterrows():
            response += f"   - Issue: {row['label']}\n"
            response += f"   - Priority: {row['detail1']}\n"
            response += f"   - Expected Impact: Risk reduction\n\n"
    
    if len(workload_data) < 2 and len(at_risk_unassigned) == 0:
        response += "No immediate reassignment needed.\n"
    
    # Executive Summary
    response += "\n#### Executive Summary\n\n"
    
    # Overall status
    overload_count = len(workload_data[workload_data['count'] > 10])
    unassigned_count = len(at_risk_unassigned)
    
    if overload_count == 0 and unassigned_count == 0 and total_at_risk == 0:
        overall_status = "✅ GOOD"
    elif overload_count > 0 or unassigned_count > 0 or total_at_risk <= 3:
        overall_status = "⚠️ WARNING"
    else:
        overall_status = "🚨 CRITICAL"
    
    response += f"**Overall Sprint Status**: {overall_status}\n\n"
    
    # Key Risks
    response += "**Key Risks:**\n"
    if total_at_risk > 0:
        if len(at_risk_stale) > 0:
            response += f"- {len(at_risk_stale)} ticket(s) stalled beyond acceptable thresholds\n"
        if len(at_risk_unassigned) > 0:
            response += f"- {len(at_risk_unassigned)} high-priority unassigned issue(s)\n"
        if len(at_risk_blocked) > 0:
            response += f"- {len(at_risk_blocked)} blocked ticket(s)\n"
        if overload_count > 0:
            response += f"- {overload_count} team member(s) overloaded\n"
    else:
        response += "- ✅ No significant risks identified\n"
    
    # Immediate Actions
    response += "\n**Immediate Actions:**\n"
    if total_at_risk > 0 or overload_count > 0:
        if overload_count > 0:
            response += "- Rebalance workload to prevent burnout\n"
        if len(at_risk_unassigned) > 0:
            response += "- Assign owners to high-priority unassigned tickets immediately\n"
        if len(at_risk_blocked) > 0:
            response += "- Resolve dependencies blocking progress\n"
        if len(at_risk_stale) > 0:
            response += "- Review and unstick stalled tickets\n"
    else:
        response += "- ✅ Maintain current momentum\n"
        response += "- Continue monitoring for emerging risks\n"
    
    return response


def format_advanced_standup_response(results_df, project_key: str) -> str:
    """
    Format advanced standup analysis into structured report
    """
    import pandas as pd
    
    # Organize data by section
    completed = results_df[results_df['section'] == 'completed_yesterday']
    working = results_df[results_df['section'] == 'working_today']
    blockers = results_df[results_df['section'] == 'blockers']
    inactive = results_df[results_df['section'] == 'inactive']
    
    # Get unique developers
    all_devs = set()
    for df in [completed, working, blockers, inactive]:
        all_devs.update(df['label'].unique())
    
    response = f"# 📋 Advanced Standup Summary for {project_key}\n\n"
    
    # Per-developer standup
    response += "## Team Member Updates\n\n"
    
    for dev in sorted(all_devs):
        response += f"### 👤 Developer: {dev}\n\n"
        
        # Yesterday
        dev_completed = completed[completed['label'] == dev]
        response += "**Yesterday:**\n"
        if len(dev_completed) > 0:
            for _, row in dev_completed.iterrows():
                response += f"- ✅ Completed **{row['count']}**: {row['detail1'][:60]}...\n"
        else:
            response += "- No completed tasks recorded\n"
        
        # Today
        dev_working = working[working['label'] == dev]
        response += "\n**Today:**\n"
        if len(dev_working) > 0:
            for _, row in dev_working.iterrows():
                response += f"- 🔨 Working on **{row['count']}**: {row['detail1'][:60]}...\n"
        else:
            response += "- No active In Progress tickets\n"
        
        # Blockers
        dev_blockers = blockers[blockers['label'] == dev]
        response += "\n**Blockers:**\n"
        if len(dev_blockers) > 0:
            for _, row in dev_blockers.iterrows():
                response += f"- ⚠️ **{row['count']}** is blocked: {row['detail1'][:60]}...\n"
        else:
            response += "- None\n"
        
        response += "\n---\n\n"
    
    # Inactive developers
    if len(inactive) > 0:
        response += "## ⚠️ Inactive Developers\n\n"
        for _, row in inactive.iterrows():
            response += f"- **{row['label']}**: No updates for {int(row['count'])} days\n"
        response += "\n"
    
    # Summary
    response += "## Summary\n\n"
    response += f"- **Active developers**: {len(all_devs) - len(inactive)}\n"
    response += f"- **Tasks completed yesterday**: {len(completed)}\n"
    response += f"- **Tasks in progress**: {len(working)}\n"
    response += f"- **Blocked tasks**: {len(blockers)}\n"
    
    if len(blockers) > 0:
        response += f"\n⚠️ **Action Required**: {len(blockers)} blocker(s) need immediate attention\n"
    
    return response


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