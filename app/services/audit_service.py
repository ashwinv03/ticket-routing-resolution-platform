from app.models import db, TicketHistory

def log_ticket_activity(ticket_id, user_id, action, old_value=None, new_value=None):
    """
    Records an entry in the TicketHistory audit log.
    action: e.g., 'created', 'status_changed', 'reassigned', 'priority_changed', 'sla_breached', 'comment_added'
    """
    history_entry = TicketHistory(
        ticket_id=ticket_id,
        user_id=user_id,
        action=action,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None
    )
    db.session.add(history_entry)
    db.session.commit()
