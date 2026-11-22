from datetime import timedelta
from app.models import db, SLAPolicy, Ticket, utcnow

PRIORITY_MATRIX = {
    ('low', 'low'): 'P4',
    ('low', 'medium'): 'P4',
    ('low', 'high'): 'P3',
    ('medium', 'low'): 'P4',
    ('medium', 'medium'): 'P3',
    ('medium', 'high'): 'P2',
    ('high', 'low'): 'P3',
    ('high', 'medium'): 'P2',
    ('high', 'high'): 'P1',
}

def calculate_priority(urgency, impact):
    """Calculates ITIL-compliant priority from urgency and impact."""
    u = (urgency or 'medium').lower()
    i = (impact or 'medium').lower()
    return PRIORITY_MATRIX.get((u, i), 'P3')

def get_or_create_sla_policy(priority):
    """Retrieves or creates default SLA policies for P1..P4."""
    defaults = {
        'P1': {'name': 'Critical SLA', 'response_h': 0.5, 'resolution_h': 4.0},
        'P2': {'name': 'High SLA', 'response_h': 1.0, 'resolution_h': 8.0},
        'P3': {'name': 'Medium SLA', 'response_h': 4.0, 'resolution_h': 24.0},
        'P4': {'name': 'Low SLA', 'response_h': 8.0, 'resolution_h': 48.0},
    }
    policy = SLAPolicy.query.filter_by(priority=priority).first()
    if not policy:
        cfg = defaults.get(priority, defaults['P3'])
        policy = SLAPolicy(
            name=cfg['name'],
            priority=priority,
            response_time_hours=cfg['response_h'],
            resolution_time_hours=cfg['resolution_h'],
            is_active=True
        )
        db.session.add(policy)
        db.session.commit()
    return policy

def ensure_naive(dt):
    """Safely strips tzinfo if present to prevent SQLite offset-naive vs offset-aware comparison errors."""
    if dt is not None and getattr(dt, 'tzinfo', None) is not None:
        return dt.replace(tzinfo=None)
    return dt

def apply_sla_to_ticket(ticket):
    """Assigns SLA policy and calculates initial resolution due date."""
    policy = get_or_create_sla_policy(ticket.priority)
    ticket.sla_policy_id = policy.id
    if not ticket.created_at:
        ticket.created_at = utcnow()
    else:
        ticket.created_at = ensure_naive(ticket.created_at)
    ticket.due_date = ticket.created_at + timedelta(hours=policy.resolution_time_hours)
    return ticket

def handle_status_sla_clock(ticket, old_status, new_status):
    """
    Manages SLA clock pausing when ticket is placed on hold (Pending User)
    and resumes clock by pushing due_date forward when reactivated.
    """
    now = ensure_naive(utcnow())
    if new_status == 'pending_user' and old_status != 'pending_user':
        # Pause clock
        ticket.paused_at = now
    elif old_status == 'pending_user' and new_status != 'pending_user' and ticket.paused_at:
        # Resume clock: calculate elapsed pause time
        paused_at = ensure_naive(ticket.paused_at)
        paused_seconds = int((now - paused_at).total_seconds())
        ticket.total_paused_seconds = (ticket.total_paused_seconds or 0) + paused_seconds
        if ticket.due_date:
            due_date = ensure_naive(ticket.due_date)
            ticket.due_date = due_date + timedelta(seconds=paused_seconds)
        ticket.paused_at = None

    # Track resolution time
    if new_status in ['resolved', 'closed'] and not ticket.resolved_at:
        ticket.resolved_at = now
    elif new_status not in ['resolved', 'closed']:
        ticket.resolved_at = None

def check_ticket_sla_breach(ticket):
    """Checks whether a ticket has breached its resolution SLA."""
    if ticket.status in ['resolved', 'closed']:
        return ticket.is_sla_breached
    
    if ticket.due_date:
        now = ensure_naive(utcnow())
        effective_due = ensure_naive(ticket.due_date)
        if ticket.status == 'pending_user' and ticket.paused_at:
            paused_at = ensure_naive(ticket.paused_at)
            current_pause = now - paused_at
            effective_due = effective_due + current_pause
            
        if now > effective_due:
            ticket.is_sla_breached = True
            db.session.commit()
            return True
            
    return ticket.is_sla_breached
