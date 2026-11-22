import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import login_required, current_user
from app.models import db, Ticket, TicketComment, User, Team, utcnow
from app.services.sla_service import calculate_priority, apply_sla_to_ticket, handle_status_sla_clock, check_ticket_sla_breach
from app.services.routing_engine import route_and_assign_ticket
from app.services.audit_service import log_ticket_activity

tickets_bp = Blueprint('tickets', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def generate_ticket_number():
    date_str = datetime.now().strftime("%Y%m%d")
    count_today = Ticket.query.filter(Ticket.ticket_number.like(f"INC-{date_str}-%")).count() + 1
    return f"INC-{date_str}-{count_today:04d}"

@tickets_bp.route('/')
@login_required
def list_tickets():
    query = Ticket.query
    
    # Role-based visibility
    if current_user.role == 'requester':
        query = query.filter_by(requester_id=current_user.id)
    elif current_user.role in ['agent', 'supervisor', 'team_admin']:
        default_view = 'team' if current_user.role in ['supervisor', 'team_admin'] else 'assigned'
        view_filter = request.args.get('view', default_view)
        if view_filter == 'assigned':
            query = query.filter_by(assigned_agent_id=current_user.id)
        elif view_filter == 'team' and current_user.team_id:
            query = query.filter_by(team_id=current_user.team_id)
        elif view_filter == 'unassigned':
            query = query.filter_by(assigned_agent_id=None)
            if current_user.team_id:
                query = query.filter_by(team_id=current_user.team_id)
            
    # Filters
    status_filter = request.args.get('status')
    if status_filter:
        query = query.filter_by(status=status_filter)
        
    priority_filter = request.args.get('priority')
    if priority_filter:
        query = query.filter_by(priority=priority_filter)
        
    search_query = request.args.get('q', '').strip()
    if search_query:
        query = query.filter(
            (Ticket.ticket_number.ilike(f"%{search_query}%")) |
            (Ticket.title.ilike(f"%{search_query}%")) |
            (Ticket.category.ilike(f"%{search_query}%"))
        )
        
    tickets = query.order_by(Ticket.created_at.desc()).all()
    
    # Run SLA breach checks on open tickets
    for t in tickets:
        check_ticket_sla_breach(t)
        
    return render_template('tickets/list.html', tickets=tickets)

@tickets_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_ticket():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', 'General IT')
        ticket_type = request.form.get('ticket_type', 'incident')
        urgency = request.form.get('urgency', 'medium')
        impact = request.form.get('impact', 'medium')
        
        if not title or not description:
            flash('Title and description are required.', 'danger')
            return render_template('tickets/create.html')
            
        # Calculate ITIL priority
        priority = calculate_priority(urgency, impact)
        ticket_number = generate_ticket_number()
        
        ticket = Ticket(
            ticket_number=ticket_number,
            title=title,
            description=description,
            category=category,
            ticket_type=ticket_type,
            urgency=urgency,
            impact=impact,
            priority=priority,
            requester_id=current_user.id,
            status='new'
        )
        
        # Apply SLA Policy
        apply_sla_to_ticket(ticket)
        
        # Run 2-Stage Routing & Workload-Aware Assignment Engine
        matched_rule, assigned_team, assigned_agent = route_and_assign_ticket(ticket)
        
        db.session.add(ticket)
        db.session.commit()
        
        # Log Audit Trail
        log_ticket_activity(ticket.id, current_user.id, 'created', new_value=f"Ticket created ({priority})")
        if matched_rule:
            log_ticket_activity(ticket.id, None, 'auto_routed', new_value=f"Matched rule '{matched_rule}' -> {assigned_team.name if assigned_team else 'None'}")
        if assigned_agent:
            log_ticket_activity(ticket.id, None, 'auto_assigned', new_value=f"Assigned to {assigned_agent.full_name} (workload: {assigned_agent.active_ticket_count} active tickets)")
            
        flash(f'Ticket {ticket.ticket_number} created successfully and routed to {ticket.team.name if ticket.team else "General Queue"}.', 'success')
        return redirect(url_for('tickets.ticket_detail', ticket_number=ticket.ticket_number))
        
    return render_template('tickets/create.html')

@tickets_bp.route('/<ticket_number>')
@login_required
def ticket_detail(ticket_number):
    ticket = Ticket.query.filter_by(ticket_number=ticket_number).first_or_404()
    
    # Requester access control
    if current_user.role == 'requester' and ticket.requester_id != current_user.id:
        abort(403)
        
    # Check SLA breach status
    check_ticket_sla_breach(ticket)
    
    # Filter comments: Requesters do NOT see internal agent notes
    if current_user.role == 'requester':
        comments = [c for c in ticket.comments if not c.is_internal]
    else:
        comments = ticket.comments
        
    all_teams = Team.query.order_by(Team.name.asc()).all()
    all_agents = User.query.filter(User.role.in_(['agent', 'supervisor', 'team_admin']), User.is_active == True).order_by(User.full_name.asc()).all()
    team_agents = [a for a in all_agents if a.team_id == ticket.team_id]
    
    return render_template(
        'tickets/detail.html',
        ticket=ticket,
        comments=comments,
        all_teams=all_teams,
        all_agents=all_agents,
        team_agents=team_agents
    )

@tickets_bp.route('/search')
@login_required
def search_tickets():
    q = request.args.get('q', '').strip()
    if not q:
        return redirect(url_for('tickets.list_tickets'))
        
    # Exact ticket number search (case-insensitive)
    exact = Ticket.query.filter(Ticket.ticket_number.ilike(q)).first()
    if exact:
        if current_user.role == 'requester' and exact.requester_id != current_user.id:
            flash(f'Ticket {exact.ticket_number} not found or access restricted.', 'warning')
            return redirect(url_for('tickets.list_tickets'))
        return redirect(url_for('tickets.ticket_detail', ticket_number=exact.ticket_number))
        
    # Partial ticket number match (e.g. typing "0001" or "20261120")
    partial_match = Ticket.query.filter(Ticket.ticket_number.ilike(f"%{q}%"))
    if current_user.role == 'requester':
        partial_match = partial_match.filter_by(requester_id=current_user.id)
    matches = partial_match.all()
    if len(matches) == 1:
        return redirect(url_for('tickets.ticket_detail', ticket_number=matches[0].ticket_number))
        
    # Multi-match or keyword fallback to filtered list view
    return redirect(url_for('tickets.list_tickets', q=q))

@tickets_bp.route('/<ticket_number>/comment', methods=['POST'])
@login_required
def add_comment(ticket_number):
    ticket = Ticket.query.filter_by(ticket_number=ticket_number).first_or_404()
    
    if current_user.role == 'requester' and ticket.requester_id != current_user.id:
        abort(403)
        
    body = request.form.get('body', '').strip()
    is_internal = request.form.get('is_internal') == 'true'
    
    # Requesters cannot post internal notes
    if current_user.role == 'requester':
        is_internal = False
        
    if not body:
        flash('Comment cannot be empty.', 'warning')
        return redirect(url_for('tickets.ticket_detail', ticket_number=ticket_number))
        
    # Handle optional file attachment
    attachment_filename = None
    if 'attachment' in request.files:
        file = request.files['attachment']
        if file and file.filename and allowed_file(file.filename):
            sec_name = secure_filename(file.filename)
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{sec_name}"
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            attachment_filename = unique_filename

    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        body=body,
        is_internal=is_internal,
        attachment_filename=attachment_filename
    )
    db.session.add(comment)
    
    # If this is the first agent response to requester, record first_response_at
    if current_user.role in ['agent', 'supervisor', 'team_admin', 'admin'] and not is_internal and not ticket.first_response_at:
        ticket.first_response_at = utcnow()
        log_ticket_activity(ticket.id, current_user.id, 'first_response', new_value=ticket.first_response_at.isoformat())

    # If requester replies while ticket is pending_user, automatically resume to in_progress
    if current_user.role == 'requester' and ticket.status == 'pending_user':
        handle_status_sla_clock(ticket, 'pending_user', 'in_progress')
        ticket.status = 'in_progress'
        log_ticket_activity(ticket.id, current_user.id, 'status_changed', old_value='pending_user', new_value='in_progress (user replied)')

    db.session.commit()
    log_ticket_activity(ticket.id, current_user.id, 'comment_added', new_value='Internal note' if is_internal else 'Public reply')
    
    flash('Response recorded successfully.', 'success')
    return redirect(url_for('tickets.ticket_detail', ticket_number=ticket_number))

@tickets_bp.route('/<ticket_number>/status', methods=['POST'])
@login_required
def update_status(ticket_number):
    ticket = Ticket.query.filter_by(ticket_number=ticket_number).first_or_404()
    new_status = request.form.get('status')
    
    allowed_states = ['new', 'assigned', 'in_progress', 'pending_user', 'resolved', 'closed', 'reopened']
    if new_status not in allowed_states:
        flash('Invalid status transition.', 'danger')
        return redirect(url_for('tickets.ticket_detail', ticket_number=ticket_number))
        
    # Requester permissions: can only reopen or close a resolved ticket
    if current_user.role == 'requester':
        if new_status not in ['closed', 'reopened']:
            abort(403)
            
    old_status = ticket.status
    if old_status != new_status:
        # Manage SLA clock pausing/resuming
        handle_status_sla_clock(ticket, old_status, new_status)
        ticket.status = new_status
        db.session.commit()
        
        log_ticket_activity(ticket.id, current_user.id, 'status_changed', old_value=old_status, new_value=new_status)
        flash(f'Ticket status updated from {old_status.replace("_", " ").title()} to {new_status.replace("_", " ").title()}.', 'success')
        
    return redirect(url_for('tickets.ticket_detail', ticket_number=ticket_number))

@tickets_bp.route('/<ticket_number>/reassign', methods=['POST'])
@login_required
def reassign_ticket(ticket_number):
    if current_user.role not in ['agent', 'supervisor', 'team_admin', 'admin']:
        abort(403)
        
    ticket = Ticket.query.filter_by(ticket_number=ticket_number).first_or_404()
    team_id = request.form.get('team_id')
    agent_id = request.form.get('agent_id')
    
    old_agent = ticket.assigned_agent.full_name if ticket.assigned_agent else 'Unassigned'
    old_team = ticket.team.name if ticket.team else 'Unassigned'
    
    if team_id:
        ticket.team_id = int(team_id)
    if agent_id:
        ticket.assigned_agent_id = int(agent_id) if agent_id != 'none' else None
        ticket.status = 'assigned' if ticket.assigned_agent_id else 'new'
        
    db.session.commit()
    
    new_agent = ticket.assigned_agent.full_name if ticket.assigned_agent else 'Unassigned'
    new_team = ticket.team.name if ticket.team else 'Unassigned'
    
    log_ticket_activity(ticket.id, current_user.id, 'reassigned', old_value=f"{old_team} / {old_agent}", new_value=f"{new_team} / {new_agent}")
    flash(f'Ticket reassigned to {new_team} / {new_agent}.', 'success')
    return redirect(url_for('tickets.ticket_detail', ticket_number=ticket_number))

@tickets_bp.route('/<ticket_number>/csat', methods=['POST'])
@login_required
def submit_csat(ticket_number):
    ticket = Ticket.query.filter_by(ticket_number=ticket_number).first_or_404()
    if ticket.requester_id != current_user.id:
        abort(403)
        
    rating = request.form.get('rating')
    feedback = request.form.get('feedback', '').strip()
    
    if rating:
        ticket.csat_rating = int(rating)
        ticket.csat_feedback = feedback
        db.session.commit()
        log_ticket_activity(ticket.id, current_user.id, 'csat_submitted', new_value=f"{rating} Stars")
        flash('Thank you for providing your feedback!', 'success')
        
    return redirect(url_for('tickets.ticket_detail', ticket_number=ticket_number))
