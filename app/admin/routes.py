from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.models import db, User, Team, Ticket, SLAPolicy, RoutingRule

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    total_tickets = Ticket.query.count()
    open_tickets = Ticket.query.filter(Ticket.status.in_(['new', 'assigned', 'in_progress', 'pending_user'])).count()
    resolved_tickets = Ticket.query.filter(Ticket.status.in_(['resolved', 'closed'])).count()
    breached_tickets = Ticket.query.filter_by(is_sla_breached=True).count()
    
    # SLA Compliance rate
    compliance_rate = 100.0
    if total_tickets > 0:
        compliance_rate = round(((total_tickets - breached_tickets) / total_tickets) * 100, 1)
        
    # CSAT Average
    csat_scores = [t.csat_rating for t in Ticket.query.filter(Ticket.csat_rating.isnot(None)).all()]
    avg_csat = round(sum(csat_scores) / len(csat_scores), 2) if csat_scores else 5.0
    
    # Priority counts
    priority_counts = {
        'P1': Ticket.query.filter_by(priority='P1').count(),
        'P2': Ticket.query.filter_by(priority='P2').count(),
        'P3': Ticket.query.filter_by(priority='P3').count(),
        'P4': Ticket.query.filter_by(priority='P4').count(),
    }
    
    # Status counts
    status_counts = {
        'New': Ticket.query.filter_by(status='new').count(),
        'Assigned': Ticket.query.filter_by(status='assigned').count(),
        'In Progress': Ticket.query.filter_by(status='in_progress').count(),
        'Pending User': Ticket.query.filter_by(status='pending_user').count(),
        'Resolved': Ticket.query.filter_by(status='resolved').count(),
        'Closed': Ticket.query.filter_by(status='closed').count(),
    }
    
    # Agent workloads
    agents = User.query.filter(User.role.in_(['agent', 'supervisor', 'team_admin'])).all()
    agent_workload = [{'name': a.full_name, 'load': a.active_ticket_count, 'team': a.team.name if a.team else 'No Team'} for a in agents]
    
    recent_breaches = Ticket.query.filter_by(is_sla_breached=True).order_by(Ticket.created_at.desc()).limit(5).all()

    return render_template(
        'admin/dashboard.html',
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

@admin_bp.route('/routing-rules', methods=['GET', 'POST'])
@login_required
@admin_required
def routing_rules():
    teams = Team.query.all()
    if request.method == 'POST':
        rule_name = request.form.get('rule_name', '').strip()
        keyword_pattern = request.form.get('keyword_pattern', '').strip()
        match_field = request.form.get('match_field', 'both')
        target_team_id = request.form.get('target_team_id')
        target_priority = request.form.get('target_priority') or None
        priority_order = int(request.form.get('priority_order', 10))
        
        if rule_name and keyword_pattern and target_team_id:
            rule = RoutingRule(
                rule_name=rule_name,
                keyword_pattern=keyword_pattern,
                match_field=match_field,
                target_team_id=int(target_team_id),
                target_priority=target_priority,
                priority_order=priority_order,
                is_active=True
            )
            db.session.add(rule)
            db.session.commit()
            flash(f'Routing rule "{rule_name}" created successfully.', 'success')
            return redirect(url_for('admin.routing_rules'))
            
    rules = RoutingRule.query.order_by(RoutingRule.priority_order.asc()).all()
    return render_template('admin/routing_rules.html', rules=rules, teams=teams)

@admin_bp.route('/routing-rules/<int:rule_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_rule(rule_id):
    rule = RoutingRule.query.get_or_404(rule_id)
    rule.is_active = not rule.is_active
    db.session.commit()
    flash(f"Rule '{rule.rule_name}' {'activated' if rule.is_active else 'deactivated'}.", 'info')
    return redirect(url_for('admin.routing_rules'))

@admin_bp.route('/routing-rules/<int:rule_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_rule(rule_id):
    rule = RoutingRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    flash(f"Rule '{rule.rule_name}' deleted.", 'warning')
    return redirect(url_for('admin.routing_rules'))

@admin_bp.route('/sla-policies', methods=['GET', 'POST'])
@login_required
@admin_required
def sla_policies():
    if request.method == 'POST':
        for priority in ['P1', 'P2', 'P3', 'P4']:
            resp_h = request.form.get(f'resp_{priority}')
            resol_h = request.form.get(f'resol_{priority}')
            policy = SLAPolicy.query.filter_by(priority=priority).first()
            if policy and resp_h and resol_h:
                policy.response_time_hours = float(resp_h)
                policy.resolution_time_hours = float(resol_h)
        db.session.commit()
        flash('SLA policies updated successfully.', 'success')
        return redirect(url_for('admin.sla_policies'))
        
    policies = SLAPolicy.query.order_by(SLAPolicy.priority.asc()).all()
    return render_template('admin/sla_policies.html', policies=policies)

@admin_bp.route('/users', methods=['GET', 'POST'])
@login_required
@admin_required
def users_management():
    teams = Team.query.all()
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        role = request.form.get('role')
        team_id = request.form.get('team_id')
        is_active = request.form.get('is_active') == 'true'
        
        user = User.query.get_or_404(int(user_id))
        user.role = role
        user.team_id = int(team_id) if team_id and team_id != 'none' else None
        user.is_active = is_active
        db.session.commit()
        flash(f'Updated user {user.full_name} ({user.username}).', 'success')
        return redirect(url_for('admin.users_management'))
        
    users = User.query.order_by(User.id.asc()).all()
    return render_template('admin/users.html', users=users, teams=teams)

@admin_bp.route('/teams', methods=['GET', 'POST'])
@login_required
@admin_required
def teams_management():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        team_admin_id = request.form.get('team_admin_id')
        if name:
            if Team.query.filter_by(name=name).first():
                flash('Team name already exists.', 'danger')
            else:
                team = Team(name=name, description=description)
                db.session.add(team)
                db.session.flush() # get team.id
                
                if team_admin_id and team_admin_id != 'none':
                    admin_user = User.query.get(int(team_admin_id))
                    if admin_user:
                        admin_user.role = 'team_admin'
                        admin_user.team_id = team.id
                        
                db.session.commit()
                flash(f'Team "{name}" created successfully.', 'success')
                return redirect(url_for('admin.teams_management'))
                
    teams = Team.query.all()
    # Users who could be designated as team admin
    assignable_users = User.query.filter(User.role.in_(['agent', 'supervisor', 'team_admin', 'requester'])).order_by(User.full_name.asc()).all()
    return render_template('admin/teams.html', teams=teams, assignable_users=assignable_users)

@admin_bp.route('/teams/<int:team_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_team(team_id):
    team = Team.query.get_or_404(team_id)
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    team_admin_id = request.form.get('team_admin_id')

    if not name:
        flash('Team name cannot be empty.', 'danger')
        return redirect(url_for('admin.teams_management'))

    existing = Team.query.filter(Team.name == name, Team.id != team.id).first()
    if existing:
        flash(f'Team name "{name}" is already taken by another department.', 'danger')
        return redirect(url_for('admin.teams_management'))

    team.name = name
    team.description = description

    # Handle Team Admin update
    if team_admin_id:
        if team_admin_id == 'none':
            # Demote current team admin to agent if any
            current_admin = team.team_admin
            if current_admin:
                current_admin.role = 'agent'
        else:
            new_admin_id = int(team_admin_id)
            current_admin = team.team_admin
            if current_admin and current_admin.id != new_admin_id:
                current_admin.role = 'agent'
            new_admin = User.query.get(new_admin_id)
            if new_admin:
                new_admin.role = 'team_admin'
                new_admin.team_id = team.id

    db.session.commit()
    flash(f'Team "{team.name}" updated successfully.', 'success')
    return redirect(url_for('admin.teams_management'))

@admin_bp.route('/teams/<int:team_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_team(team_id):
    team = Team.query.get_or_404(team_id)
    team_name = team.name

    # Safely reassign members and tickets to avoid orphan issues
    User.query.filter_by(team_id=team.id).update({'team_id': None})
    Ticket.query.filter_by(team_id=team.id).update({'team_id': None})
    RoutingRule.query.filter_by(target_team_id=team.id).delete()

    db.session.delete(team)
    db.session.commit()
    flash(f'Team "{team_name}" and its associated routing rules deleted successfully. Members and tickets set to unassigned.', 'warning')
    return redirect(url_for('admin.teams_management'))
