from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user
from app.models import Ticket, User, db
from app.services.ai_service import summarize_ticket, suggest_resolution, generate_draft_response

api_bp = Blueprint('api', __name__)

@api_bp.route('/ai/summarize/<ticket_number>', methods=['POST'])
@login_required
def api_summarize(ticket_number):
    if current_user.role not in ['agent', 'supervisor', 'team_admin', 'admin']:
        abort(403)
        
    ticket = Ticket.query.filter_by(ticket_number=ticket_number).first_or_404()
    summary = summarize_ticket(ticket)
    return jsonify({'success': True, 'summary': summary})

@api_bp.route('/ai/suggest-resolution/<ticket_number>', methods=['POST'])
@login_required
def api_suggest_resolution(ticket_number):
    if current_user.role not in ['agent', 'supervisor', 'team_admin', 'admin']:
        abort(403)
        
    ticket = Ticket.query.filter_by(ticket_number=ticket_number).first_or_404()
    suggestions = suggest_resolution(ticket)
    return jsonify({'success': True, 'suggestions': suggestions})

@api_bp.route('/ai/draft-response/<ticket_number>', methods=['POST'])
@login_required
def api_draft_response(ticket_number):
    if current_user.role not in ['agent', 'supervisor', 'team_admin', 'admin']:
        abort(403)
        
    ticket = Ticket.query.filter_by(ticket_number=ticket_number).first_or_404()
    draft = generate_draft_response(ticket, agent_name=current_user.full_name)
    return jsonify({'success': True, 'draft': draft})

@api_bp.route('/metrics/overview')
@login_required
def api_metrics():
    total = Ticket.query.count()
    breached = Ticket.query.filter_by(is_sla_breached=True).count()
    open_count = Ticket.query.filter(Ticket.status.in_(['new', 'assigned', 'in_progress', 'pending_user'])).count()
    resolved_count = Ticket.query.filter(Ticket.status.in_(['resolved', 'closed'])).count()
    
    return jsonify({
        'total': total,
        'open': open_count,
        'resolved': resolved_count,
        'breached': breached,
        'compliance_rate': round(((total - breached) / total * 100), 1) if total > 0 else 100.0
    })
