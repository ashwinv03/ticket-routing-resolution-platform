from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.models import db, User, Team, Ticket, RoutingRule

team_admin_bp = Blueprint('team_admin', __name__)

def team_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role not in ['team_admin', 'supervisor', 'admin']:
            abort(403)
        if not current_user.team_id and current_user.role != 'admin':
            flash('You are not currently assigned to a department/team.', 'warning')
            return redirect(url_for('tickets.list_tickets'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_team():
    if current_user.team_id:
        return db.session.get(Team, current_user.team_id)
    # If global admin visits without team, pick the first team
    return Team.query.first()

@team_admin_bp.route('/dashboard')
@login_required
@team_admin_required
def dashboard():
    team = get_current_team()
    if not team:
        flash('No team found.', 'warning')
        return redirect(url_for('tickets.list_tickets'))

    team_tickets_query = Ticket.query.filter_by(team_id=team.id)
    total_tickets = team_tickets_query.count()
    open_tickets = team_tickets_query.filter(Ticket.status.in_(['new', 'assigned', 'in_progress', 'pending_user'])).count()
    resolved_tickets = team_tickets_query.filter(Ticket.status.in_(['resolved', 'closed'])).count()
    breached_tickets = team_tickets_query.filter_by(is_sla_breached=True).count()
    
    compliance_rate = 100.0
    if total_tickets > 0:
        compliance_rate = round(((total_tickets - breached_tickets) / total_tickets) * 100, 1)

    csat_scores = [t.csat_rating for t in team_tickets_query.filter(Ticket.csat_rating.isnot(None)).all()]
    avg_csat = round(sum(csat_scores) / len(csat_scores), 2) if csat_scores else 5.0

    priority_counts = {
        'P1': team_tickets_query.filter_by(priority='P1').count(),
        'P2': team_tickets_query.filter_by(priority='P2').count(),
        'P3': team_tickets_query.filter_by(priority='P3').count(),
        'P4': team_tickets_query.filter_by(priority='P4').count(),
    }

    status_counts = {
        'New': team_tickets_query.filter_by(status='new').count(),
        'Assigned': team_tickets_query.filter_by(status='assigned').count(),
        'In Progress': team_tickets_query.filter_by(status='in_progress').count(),
        'Pending User': team_tickets_query.filter_by(status='pending_user').count(),
        'Resolved': team_tickets_query.filter_by(status='resolved').count(),
        'Closed': team_tickets_query.filter_by(status='closed').count(),
    }

    team_agents = User.query.filter(User.team_id == team.id, User.role.in_(['agent', 'supervisor', 'team_admin'])).all()
    agent_workload = [{'name': a.full_name, 'role': a.role, 'load': a.active_ticket_count, 'username': a.username} for a in team_agents]
    recent_breaches = team_tickets_query.filter_by(is_sla_breached=True).order_by(Ticket.created_at.desc()).limit(5).all()

    return render_template(
        'team_admin/dashboard.html',
        team=team,
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        resolved_tickets=resolved_tickets,
        breached_tickets=breached_tickets,
        compliance_rate=compliance_rate,
        avg_csat=avg_csat,
        priority_counts=priority_counts,
        status_counts=status_counts,
        agent_workload=agent_workload,
        recent_breaches=recent_breaches
    )

@team_admin_bp.route('/agents', methods=['GET', 'POST'])
@login_required
@team_admin_required
def manage_agents():
    team = get_current_team()
    if request.method == 'POST':
        action = request.form.get('action')
        
        # Action 1: Add existing user to team
        if action == 'add_existing':
            user_id = request.form.get('user_id')
            user = db.session.get(User, int(user_id)) if user_id else None
            if user:
                user.team_id = team.id
                if user.role == 'requester':
                    user.role = 'agent'
                db.session.commit()
                flash(f'Added {user.full_name} to {team.name} as {user.role}.', 'success')
            return redirect(url_for('team_admin.manage_agents'))

        # Action 2: Create a brand new agent for this team
        elif action == 'create_new':
            full_name = request.form.get('full_name', '').strip()
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            
            if User.query.filter_by(username=username).first():
                flash('Username already exists.', 'danger')
            elif User.query.filter_by(email=email).first():
                flash('Email already registered.', 'danger')
            elif full_name and username and email and password:
                new_agent = User(
                    full_name=full_name,
                    username=username,
                    email=email,
                    role='agent',
                    team_id=team.id,
                    is_active=True
                )
                new_agent.set_password(password)
                db.session.add(new_agent)
                db.session.commit()
                flash(f'New agent {full_name} created and assigned to {team.name}.', 'success')
            return redirect(url_for('team_admin.manage_agents'))

    team_agents = User.query.filter(User.team_id == team.id, User.role.in_(['agent', 'supervisor', 'team_admin'])).all()
    # Users eligible to be added to this team (not already in this team)
    available_users = User.query.filter((User.team_id != team.id) | (User.team_id.is_(None))).filter(User.role != 'admin').all()

    return render_template('team_admin/agents.html', team=team, agents=team_agents, available_users=available_users)

@team_admin_bp.route('/agents/<int:user_id>/remove', methods=['POST'])
@login_required
@team_admin_required
def remove_agent(user_id):
    team = get_current_team()
    user = User.query.get_or_404(user_id)
    
    if user.team_id != team.id:
        abort(403)

    if user.id == current_user.id:
        flash('You cannot remove yourself from your own team.', 'danger')
        return redirect(url_for('team_admin.manage_agents'))

    user.team_id = None
    # Reassign open tickets of this agent to unassigned pool of the team
    Ticket.query.filter_by(assigned_agent_id=user.id).filter(Ticket.status.in_(['assigned', 'in_progress', 'pending_user'])).update({'assigned_agent_id': None, 'status': 'assigned'})
    
    db.session.commit()
    flash(f'{user.full_name} has been removed from {team.name}. Active tickets returned to team queue.', 'info')
    return redirect(url_for('team_admin.manage_agents'))

@team_admin_bp.route('/routing-rules', methods=['GET', 'POST'])
@login_required
@team_admin_required
def routing_rules():
    team = get_current_team()
    if request.method == 'POST':
        rule_name = request.form.get('rule_name', '').strip()
        keyword_pattern = request.form.get('keyword_pattern', '').strip()
        match_field = request.form.get('match_field', 'both')
        target_priority = request.form.get('target_priority') or None
        priority_order = int(request.form.get('priority_order', 10))

        if rule_name and keyword_pattern:
            rule = RoutingRule(
                rule_name=rule_name,
                keyword_pattern=keyword_pattern,
                match_field=match_field,
                target_team_id=team.id,
                target_priority=target_priority,
                priority_order=priority_order,
                is_active=True
            )
            db.session.add(rule)
            db.session.commit()
            flash(f'Routing rule "{rule_name}" created for {team.name}.', 'success')
            return redirect(url_for('team_admin.routing_rules'))

    rules = RoutingRule.query.filter_by(target_team_id=team.id).order_by(RoutingRule.priority_order.asc()).all()
    return render_template('team_admin/routing_rules.html', team=team, rules=rules)

@team_admin_bp.route('/routing-rules/<int:rule_id>/toggle', methods=['POST'])
@login_required
@team_admin_required
def toggle_rule(rule_id):
    team = get_current_team()
    rule = RoutingRule.query.get_or_404(rule_id)
    if rule.target_team_id != team.id and current_user.role != 'admin':
        abort(403)
        
    rule.is_active = not rule.is_active
    db.session.commit()
    flash(f"Rule '{rule.rule_name}' {'activated' if rule.is_active else 'deactivated'}.", 'info')
    return redirect(url_for('team_admin.routing_rules'))

@team_admin_bp.route('/routing-rules/<int:rule_id>/delete', methods=['POST'])
@login_required
@team_admin_required
def delete_rule(rule_id):
    team = get_current_team()
    rule = RoutingRule.query.get_or_404(rule_id)
    if rule.target_team_id != team.id and current_user.role != 'admin':
        abort(403)
        
    db.session.delete(rule)
    db.session.commit()
    flash(f"Rule '{rule.rule_name}' deleted.", 'warning')
    return redirect(url_for('team_admin.routing_rules'))
