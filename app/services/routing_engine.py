import re
from app.models import db, RoutingRule, Team, User, Ticket

def route_and_assign_ticket(ticket):
    """
    Two-stage routing & assignment engine:
    1. Rule-based Team Routing (checks active routing rules ordered by priority_order)
    2. Workload-aware Agent Assignment (allocates to least-loaded active agent in the team)
    Returns: (matched_rule_name_or_none, assigned_team, assigned_agent)
    """
    matched_rule = None
    target_team = None
    
    # Text to match
    title_text = (ticket.title or '').lower()
    desc_text = (ticket.description or '').lower()
    combined_text = f"{title_text} {desc_text}"
    
    # 1. Evaluate configurable routing rules
    rules = RoutingRule.query.filter_by(is_active=True).order_by(RoutingRule.priority_order.asc()).all()
    
    for rule in rules:
        keywords = [k.strip().lower() for k in rule.keyword_pattern.split(',') if k.strip()]
        if not keywords:
            continue
            
        text_to_search = combined_text
        if rule.match_field == 'title':
            text_to_search = title_text
        elif rule.match_field == 'description':
            text_to_search = desc_text
            
        # Check if any keyword matches as a word or substring
        match_found = False
        for kw in keywords:
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, text_to_search, re.IGNORECASE):
                match_found = True
                break
                
        if match_found:
            matched_rule = rule
            target_team = rule.target_team
            if rule.target_priority:
                ticket.priority = rule.target_priority
            break

    # Fallback team determination if no rule matched
    if not target_team:
        # Match by category name or fallback to first team
        if ticket.category:
            target_team = Team.query.filter(Team.name.ilike(f"%{ticket.category}%")).first()
        if not target_team:
            target_team = Team.query.first()
            
    if target_team:
        ticket.team_id = target_team.id
        
    # 2. Workload-Aware Agent Allocation
    assigned_agent = None
    if target_team:
        # Find eligible agents in this team
        eligible_agents = User.query.filter(
            User.team_id == target_team.id,
            User.role.in_(['agent', 'supervisor', 'team_admin']),
            User.is_active == True
        ).all()
        
        if eligible_agents:
            # Sort by least loaded (active tickets)
            # active_ticket_count counts tickets with status in ['assigned', 'in_progress', 'pending_user']
            agents_with_load = [(agent, agent.active_ticket_count) for agent in eligible_agents]
            agents_with_load.sort(key=lambda item: item[1])
            assigned_agent = agents_with_load[0][0]
            ticket.assigned_agent_id = assigned_agent.id
            ticket.status = 'assigned'
        else:
            ticket.assigned_agent_id = None
            ticket.status = 'new'
    else:
        ticket.assigned_agent_id = None
        ticket.status = 'new'
        
    return (matched_rule.rule_name if matched_rule else None, target_team, assigned_agent)
