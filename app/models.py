from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def utcnow():
    """Returns naive UTC datetime consistent with SQLite DateTime storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='requester')  # requester, agent, supervisor, admin
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    
    # Relationships
    team = db.relationship('Team', back_populates='members')
    requested_tickets = db.relationship('Ticket', foreign_keys='Ticket.requester_id', back_populates='requester', lazy='dynamic')
    assigned_tickets = db.relationship('Ticket', foreign_keys='Ticket.assigned_agent_id', back_populates='assigned_agent', lazy='dynamic')
    comments = db.relationship('TicketComment', back_populates='author', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def active_ticket_count(self):
        """Used for workload-aware assignment: count tickets that are not resolved or closed."""
        return self.assigned_tickets.filter(Ticket.status.in_(['assigned', 'in_progress', 'pending_user'])).count()

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


class Team(db.Model):
    __tablename__ = 'teams'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=utcnow)
    
    # Relationships
    members = db.relationship('User', back_populates='team', lazy='dynamic')
    tickets = db.relationship('Ticket', back_populates='team', lazy='dynamic')
    routing_rules = db.relationship('RoutingRule', back_populates='target_team', lazy='dynamic')

    @property
    def team_admin(self):
        """Returns the assigned team admin/supervisor for this team."""
        return self.members.filter(User.role.in_(['team_admin', 'supervisor'])).first()

    def __repr__(self):
        return f'<Team {self.name}>'


class SLAPolicy(db.Model):
    __tablename__ = 'sla_policies'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    priority = db.Column(db.String(20), unique=True, nullable=False)  # P1, P2, P3, P4
    response_time_hours = db.Column(db.Float, nullable=False)  # e.g., 0.5 for 30 mins
    resolution_time_hours = db.Column(db.Float, nullable=False) # e.g., 4.0 for 4 hours
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    
    tickets = db.relationship('Ticket', back_populates='sla_policy', lazy='dynamic')

    def __repr__(self):
        return f'<SLAPolicy {self.priority} - Resp: {self.response_time_hours}h, Resol: {self.resolution_time_hours}h>'


class Ticket(db.Model):
    __tablename__ = 'tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), nullable=False, default='General IT')
    ticket_type = db.Column(db.String(30), nullable=False, default='incident')  # incident, service_request, bug, inquiry
    
    # Urgency & Impact calculate Priority
    urgency = db.Column(db.String(20), default='medium')   # low, medium, high
    impact = db.Column(db.String(20), default='medium')    # low, medium, high
    priority = db.Column(db.String(20), default='P3', index=True)  # P1, P2, P3, P4
    
    # State Machine
    # new -> assigned -> in_progress -> pending_user -> resolved -> closed (or reopened)
    status = db.Column(db.String(30), default='new', index=True)
    
    # Foreign Keys
    requester_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_agent_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    sla_policy_id = db.Column(db.Integer, db.ForeignKey('sla_policies.id'), nullable=True)
    
    # Timestamps & SLA Tracking
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    first_response_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    is_sla_breached = db.Column(db.Boolean, default=False)
    
    # SLA Clock Pausing (e.g. while pending user)
    paused_at = db.Column(db.DateTime, nullable=True)
    total_paused_seconds = db.Column(db.Integer, default=0)
    
    # CSAT Feedback
    csat_rating = db.Column(db.Integer, nullable=True)  # 1 to 5 stars
    csat_feedback = db.Column(db.Text, nullable=True)
    
    # Relationships
    requester = db.relationship('User', foreign_keys=[requester_id], back_populates='requested_tickets')
    assigned_agent = db.relationship('User', foreign_keys=[assigned_agent_id], back_populates='assigned_tickets')
    team = db.relationship('Team', back_populates='tickets')
    sla_policy = db.relationship('SLAPolicy', back_populates='tickets')
    
    comments = db.relationship('TicketComment', back_populates='ticket', cascade='all, delete-orphan', order_by='TicketComment.created_at.asc()')
    history = db.relationship('TicketHistory', back_populates='ticket', cascade='all, delete-orphan', order_by='TicketHistory.timestamp.desc()')

    def __repr__(self):
        return f'<Ticket {self.ticket_number} - {self.priority} - {self.status}>'


class TicketComment(db.Model):
    __tablename__ = 'ticket_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False)  # True = visible only to agents/admins
    attachment_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    
    ticket = db.relationship('Ticket', back_populates='comments')
    author = db.relationship('User', back_populates='comments')


class TicketHistory(db.Model):
    __tablename__ = 'ticket_history'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(80), nullable=False)  # e.g., 'created', 'status_changed', 'reassigned'
    old_value = db.Column(db.String(255), nullable=True)
    new_value = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=utcnow)
    
    ticket = db.relationship('Ticket', back_populates='history')
    user = db.relationship('User')


class RoutingRule(db.Model):
    __tablename__ = 'routing_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    rule_name = db.Column(db.String(100), nullable=False)
    keyword_pattern = db.Column(db.String(255), nullable=False) # comma-separated keywords e.g. "vpn,wifi,network,router"
    match_field = db.Column(db.String(30), default='both')      # 'title', 'description', or 'both'
    target_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    target_priority = db.Column(db.String(20), nullable=True)   # optional override e.g. 'P1'
    priority_order = db.Column(db.Integer, default=10)          # lower number = evaluated first
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    
    target_team = db.relationship('Team', back_populates='routing_rules')

    def __repr__(self):
        return f'<RoutingRule {self.rule_name} -> Team {self.target_team_id}>'


class KnowledgeBase(db.Model):
    __tablename__ = 'knowledge_base'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), nullable=False)
    tags = db.Column(db.String(255), nullable=True) # comma-separated tags e.g. "network, vpn, cisco"
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    
    author = db.relationship('User')

    def __repr__(self):
        return f'<KB {self.title}>'
