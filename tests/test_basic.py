import pytest
from app import create_app
from app.models import db, User, Ticket, Team

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        client.get('/auth/logout')
        yield client

def test_login_page_renders(client):
    res = client.get('/auth/login')
    assert res.status_code == 200
    assert b"Sign In to TicketFlow" in res.data

def test_kb_page_renders(client):
    res = client.get('/kb/')
    assert res.status_code == 200
    assert b"Knowledge Base" in res.data

def test_auth_login_and_ticket_access(client):
    # Log in as admin
    res = client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    assert res.status_code == 200
    assert b"Operational Intelligence Dashboard" in res.data or b"Tickets" in res.data

def test_api_metrics_endpoint(client):
    client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    res = client.get('/api/metrics/overview')
    assert res.status_code == 200
    json_data = res.get_json()
    assert 'total' in json_data
    assert json_data['total'] >= 3

def test_agent_login_and_tickets_page(client):
    client.get('/auth/logout')
    res = client.post('/auth/login', data={'username': 'agent_it', 'password': 'agent123'}, follow_redirects=True)
    assert res.status_code == 200
    assert b"Support Tickets" in res.data

def test_requester_login_and_tickets_page(client):
    client.get('/auth/logout')
    res = client.post('/auth/login', data={'username': 'john_user', 'password': 'user123'}, follow_redirects=True)
    assert res.status_code == 200
    assert b"Support Tickets" in res.data

def test_ticket_detail_view(client):
    client.get('/auth/logout')
    client.post('/auth/login', data={'username': 'agent_net', 'password': 'agent123'}, follow_redirects=True)
    res = client.get('/tickets/INC-20261120-0001')
    assert res.status_code == 200
    assert b"AI Resolution Assistant" in res.data
    # Agent CAN see SLA
    assert b"SLA Compliance" in res.data

def test_sla_hidden_from_requester(client):
    client.get('/auth/logout')
    client.post('/auth/login', data={'username': 'john_user', 'password': 'user123'}, follow_redirects=True)
    
    # Check ticket list: SLA Status column must NOT be shown to requester
    res_list = client.get('/tickets/')
    assert res_list.status_code == 200
    assert b"SLA Status" not in res_list.data
    
    # Check ticket detail: SLA Compliance card must NOT be shown to requester
    res_detail = client.get('/tickets/INC-20261120-0001')
    assert res_detail.status_code == 200
    assert b"SLA Compliance" not in res_detail.data

def test_team_admin_access_and_scoping(client):
    client.get('/auth/logout')
    res_login = client.post('/auth/login', data={'username': 'agent_net', 'password': 'agent123'}, follow_redirects=True)
    assert res_login.status_code == 200
    assert b"Team Admin Console" in res_login.data
    
    # Team dashboard
    res_dash = client.get('/team/dashboard')
    assert res_dash.status_code == 200
    assert b"Network &amp; Infrastructure" in res_dash.data or b"Network & Infrastructure" in res_dash.data
    
    # Team agents
    res_agents = client.get('/team/agents')
    assert res_agents.status_code == 200
    assert b"Department Agents" in res_agents.data
    
    # Team routing rules
    res_rules = client.get('/team/routing-rules')
    assert res_rules.status_code == 200
    assert b"Department Routing Rules" in res_rules.data

def test_admin_team_edit_and_delete(client):
    # Log in as global admin
    client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    
    # Create new team
    res_create = client.post('/admin/teams', data={'name': 'Temp Operations', 'description': 'To be deleted'}, follow_redirects=True)
    assert res_create.status_code == 200
    assert b"Temp Operations" in res_create.data
    
    with client.application.app_context():
        created_team = Team.query.filter_by(name='Temp Operations').first()
        team_id = created_team.id

    # Edit team
    res_edit = client.post(f'/admin/teams/{team_id}/edit', data={'name': 'Temp Operations Renamed', 'description': 'Updated', 'team_admin_id': 'none'}, follow_redirects=True)
    assert res_edit.status_code == 200
    assert b"Temp Operations Renamed" in res_edit.data
    
    # Delete team
    res_del = client.post(f'/admin/teams/{team_id}/delete', follow_redirects=True)
    assert res_del.status_code == 200
    assert b"deleted successfully" in res_del.data

def test_universal_search_box(client):
    client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    
    # Exact match redirect
    res_exact = client.get('/tickets/search?q=INC-20261120-0001', follow_redirects=True)
    assert res_exact.status_code == 200
    assert b"VPN connection drops every 5 minutes" in res_exact.data
    
    # Partial number match redirect (e.g. searching '0001')
    res_partial = client.get('/tickets/search?q=0001', follow_redirects=True)
    assert res_partial.status_code == 200
    assert b"INC-20261120-0001" in res_partial.data

def test_reassign_ticket_flow(client):
    client.post('/auth/login', data={'username': 'agent_net', 'password': 'agent123'}, follow_redirects=True)
    
    with client.application.app_context():
        target_team = Team.query.filter_by(name="Cloud & DevOps").first()
        target_agent = User.query.filter_by(username="liam_cloud").first()
        
    res = client.post('/tickets/INC-20261120-0001/reassign', data={
        'team_id': target_team.id,
        'agent_id': target_agent.id
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Ticket reassigned" in res.data
    assert b"Liam Gallagher" in res.data or b"Cloud &amp; DevOps" in res.data
