from datetime import timedelta
from app import create_app
from app.models import db, User, Team, SLAPolicy, RoutingRule, KnowledgeBase, Ticket, TicketComment, TicketHistory, utcnow
from app.services.sla_service import apply_sla_to_ticket, handle_status_sla_clock

def seed_database():
    app = create_app()
    with app.app_context():
        # Drop and recreate tables for a fresh clean state
        db.drop_all()
        db.create_all()
        print("Database schema created cleanly via PySQLite.")

        # 1. Create 7 Support Teams / Departments
        team_net = Team(name="Network & Infrastructure", description="Handles VPN, Wi-Fi, routers, switches, firewalls, and office connectivity")
        team_soft = Team(name="Software & Applications", description="Handles ERP systems, internal web tools, bugs, databases, and application errors")
        team_hard = Team(name="Hardware & Peripherals", description="Handles laptops, workstations, monitors, docks, and network printers")
        team_cloud = Team(name="Cloud & DevOps", description="Handles AWS/Azure infrastructure, container deployments, and CI/CD pipelines")
        team_sec = Team(name="Cybersecurity & Identity (IAM)", description="Handles SSO, 2FA/MFA, access permissions, credential resets, and security incident response")
        team_hr = Team(name="HR & Payroll Operations", description="Handles employee onboarding, payroll queries, leave policies, and benefits")
        team_fin = Team(name="Billing & Finance Operations", description="Handles vendor invoices, travel reimbursements, and payment clearances")
        
        teams = [team_net, team_soft, team_hard, team_cloud, team_sec, team_hr, team_fin]
        db.session.add_all(teams)
        db.session.commit()
        print(f"Created {len(teams)} teams.")

        # 2. Create SLA Policies (P1..P4)
        sla_p1 = SLAPolicy(name="Critical SLA", priority="P1", response_time_hours=0.5, resolution_time_hours=4.0)
        sla_p2 = SLAPolicy(name="High SLA", priority="P2", response_time_hours=1.0, resolution_time_hours=8.0)
        sla_p3 = SLAPolicy(name="Medium SLA", priority="P3", response_time_hours=4.0, resolution_time_hours=24.0)
        sla_p4 = SLAPolicy(name="Low SLA", priority="P4", response_time_hours=8.0, resolution_time_hours=48.0)
        
        db.session.add_all([sla_p1, sla_p2, sla_p3, sla_p4])
        db.session.commit()
        print("Created SLA policies (P1..P4).")

        # 3. Create Global Admin & Requesters
        admin = User(username="admin", email="admin@ticketflow.org", full_name="System Administrator", role="admin")
        admin.set_password("admin123")

        user_john = User(username="john_user", email="john.doe@company.org", full_name="John Doe", role="requester")
        user_john.set_password("user123")

        user_sarah = User(username="sarah_user", email="sarah.jenkins@company.org", full_name="Sarah Jenkins", role="requester")
        user_sarah.set_password("user123")

        db.session.add_all([admin, user_john, user_sarah])

        # 4. Create 1 Team Lead and 3 Working Members under EACH Team
        team_roster_data = [
            # Team 1: Network & Infrastructure
            {
                "team": team_net,
                "lead": ("agent_net", "alex.net@ticketflow.org", "Alex Rivera (Network Lead)"),
                "members": [
                    ("ben_net", "ben.net@ticketflow.org", "Ben Taylor (Network Eng)"),
                    ("chris_net", "chris.net@ticketflow.org", "Chris Evans (Sysadmin)"),
                    ("dana_net", "dana.net@ticketflow.org", "Dana White (Network Analyst)")
                ]
            },
            # Team 2: Software & Applications
            {
                "team": team_soft,
                "lead": ("sam_dev", "sam.dev@ticketflow.org", "Samantha Chen (Dev Lead)"),
                "members": [
                    ("agent_it", "david.soft@ticketflow.org", "David Kim (App Dev)"),
                    ("emma_soft", "emma.soft@ticketflow.org", "Emma Watson (QA Engineer)"),
                    ("frank_soft", "frank.soft@ticketflow.org", "Frank Miller (Backend Dev)")
                ]
            },
            # Team 3: Hardware & Peripherals
            {
                "team": team_hard,
                "lead": ("agent_hw", "marcus.hw@ticketflow.org", "Marcus Vance (Hardware Lead)"),
                "members": [
                    ("grace_hw", "grace.hw@ticketflow.org", "Grace Hopper (Desktop Tech)"),
                    ("henry_hw", "henry.hw@ticketflow.org", "Henry Ford (Peripherals Eng)"),
                    ("ivy_hw", "ivy.hw@ticketflow.org", "Ivy Clark (Assets Tech)")
                ]
            },
            # Team 4: Cloud & DevOps
            {
                "team": team_cloud,
                "lead": ("liam_cloud", "liam.cloud@ticketflow.org", "Liam Gallagher (Cloud Architect)"),
                "members": [
                    ("jack_cloud", "jack.cloud@ticketflow.org", "Jack Ryan (SRE Specialist)"),
                    ("karen_cloud", "karen.cloud@ticketflow.org", "Karen Gillan (DevOps Eng)"),
                    ("leo_cloud", "leo.cloud@ticketflow.org", "Leo Messi (Platform Eng)")
                ]
            },
            # Team 5: Cybersecurity & Identity (IAM)
            {
                "team": team_sec,
                "lead": ("sophia_sec", "sophia.sec@ticketflow.org", "Sophia Zhang (Security Lead)"),
                "members": [
                    ("mike_sec", "mike.sec@ticketflow.org", "Mike Ross (IAM Analyst)"),
                    ("nina_sec", "nina.sec@ticketflow.org", "Nina Patel (SOC Analyst)"),
                    ("oscar_sec", "oscar.sec@ticketflow.org", "Oscar Wilde (Security Auditor)")
                ]
            },
            # Team 6: HR & Payroll Operations
            {
                "team": team_hr,
                "lead": ("rachel_hr", "rachel.hr@ticketflow.org", "Rachel Green (HR Ops Lead)"),
                "members": [
                    ("paul_hr", "paul.hr@ticketflow.org", "Paul Rudd (Payroll Specialist)"),
                    ("quinn_hr", "quinn.hr@ticketflow.org", "Quinn Fabray (Benefits Coordinator)"),
                    ("ross_hr", "ross.hr@ticketflow.org", "Ross Geller (HR Specialist)")
                ]
            },
            # Team 7: Billing & Finance Operations
            {
                "team": team_fin,
                "lead": ("monica_fin", "monica.fin@ticketflow.org", "Monica Geller (Finance Lead)"),
                "members": [
                    ("steve_fin", "steve.fin@ticketflow.org", "Steve Carell (Accounts Payable)"),
                    ("tina_fin", "tina.fin@ticketflow.org", "Tina Fey (Invoicing Analyst)"),
                    ("uma_fin", "uma.fin@ticketflow.org", "Uma Thurman (Expense Auditor)")
                ]
            }
        ]

        all_agents = []
        lead_users = {}
        for entry in team_roster_data:
            target_team = entry["team"]
            # Create Lead
            l_username, l_email, l_name = entry["lead"]
            lead_user = User(
                username=l_username,
                email=l_email,
                full_name=l_name,
                role="team_admin",
                team_id=target_team.id,
                is_active=True
            )
            lead_user.set_password("agent123")
            db.session.add(lead_user)
            all_agents.append(lead_user)
            lead_users[target_team.name] = lead_user

            # Create 3 Working Members
            for m_username, m_email, m_name in entry["members"]:
                m_user = User(
                    username=m_username,
                    email=m_email,
                    full_name=m_name,
                    role="agent",
                    team_id=target_team.id,
                    is_active=True
                )
                m_user.set_password("agent123")
                db.session.add(m_user)
                all_agents.append(m_user)

        db.session.commit()
        print(f"Created 7 Team Leads and 21 Working Members (total {len(all_agents)} staff).")

        # 5. Create Configurable Routing Rules for all 7 teams
        rules = [
            RoutingRule(rule_name="VPN & Network Infrastructure Rule", keyword_pattern="vpn, wifi, router, network, ip address, subnet, gateway, firewall", match_field="both", target_team_id=team_net.id, priority_order=1),
            RoutingRule(rule_name="Software & Database Bug Rule", keyword_pattern="crash, exception, bug, database, sql error, erp, 500 error, api failure", match_field="both", target_team_id=team_soft.id, priority_order=2),
            RoutingRule(rule_name="Hardware & Device Peripherals Rule", keyword_pattern="laptop, monitor, screen, keyboard, mouse, printer, docking station, battery", match_field="both", target_team_id=team_hard.id, priority_order=3),
            RoutingRule(rule_name="Cloud & DevOps Pipeline Rule", keyword_pattern="aws, azure, gcp, docker, kubernetes, deployment, pipeline, terraform, ci/cd", match_field="both", target_team_id=team_cloud.id, priority_order=4),
            RoutingRule(rule_name="Cybersecurity & Access IAM Rule", keyword_pattern="security, access, sso, mfa, 2fa, permission, phishing, password reset, breach, credential", match_field="both", target_team_id=team_sec.id, priority_order=5),
            RoutingRule(rule_name="Payroll & HR Inquiries Rule", keyword_pattern="salary, payroll, leave, bonus, tax form, payslip, benefits, health insurance", match_field="both", target_team_id=team_hr.id, priority_order=6),
            RoutingRule(rule_name="Billing & Reimbursement Claims Rule", keyword_pattern="reimbursement, invoice, expense claim, billing, receipt, vendor payment", match_field="both", target_team_id=team_fin.id, priority_order=7),
        ]
        db.session.add_all(rules)
        db.session.commit()
        print("Created 7 automated routing rules.")

        # 6. Create Knowledge Base Articles
        kb1 = KnowledgeBase(
            title="Troubleshooting Cisco AnyConnect & GlobalProtect VPN Timeouts",
            category="Network & Infrastructure",
            tags="vpn, network, cisco, anyconnect, timeout",
            author_id=lead_users["Network & Infrastructure"].id,
            view_count=42,
            content="""1. Verify your local internet connectivity by opening a browser and pinging 8.8.8.8.
2. Ensure your computer's date and time are synchronized automatically via NTP. Desynchronized clocks prevent SSL handshake.
3. If receiving 'Gateway connection timeout', flush DNS cache by running: ipconfig /flushdns in Command Prompt.
4. Restart the Cisco AnyConnect / GlobalProtect daemon service in services.msc.
5. If two-factor authentication prompt does not appear, ensure notifications are enabled on your authenticator app."""
        )

        kb2 = KnowledgeBase(
            title="Resolving Outlook Cache Corruption and Search Failures",
            category="Software & Applications",
            tags="outlook, email, cache, ost, search",
            author_id=lead_users["Software & Applications"].id,
            view_count=28,
            content="""1. Close Outlook completely. Open Windows Run (Win + R) and type: outlook.exe /safe.
2. If search returns zero results, rebuild the Windows Search Index:
   - Go to Control Panel > Indexing Options > Advanced > Rebuild.
3. For persistent crashing, recreate the Outlook offline profile (.ost file):
   - Navigate to %localappdata%\\Microsoft\\Outlook.
   - Rename user@company.ost to user@company.ost.old.
   - Restart Outlook to rebuild a fresh local cache from Exchange server."""
        )

        kb3 = KnowledgeBase(
            title="Connecting to Shared Office Ricoh Network Printers",
            category="Hardware & Peripherals",
            tags="printer, hardware, network, driver, ricoh",
            author_id=lead_users["Hardware & Peripherals"].id,
            view_count=19,
            content="""1. Ensure you are connected to the corporate office Wi-Fi or wired Ethernet (guest Wi-Fi cannot route to printers).
2. Open Windows Run (Win + R) and type: \\\\printserver.corp\\printers.
3. Double-click your floor printer (e.g., 'Floor2-Color-Ricoh').
4. The print queue will automatically install verified drivers without needing local admin rights."""
        )

        db.session.add_all([kb1, kb2, kb3])
        db.session.commit()
        print("Created Knowledge Base articles.")

        # 7. Seed Sample Tickets with Audit History & Conversations
        now = utcnow()
        
        # Ticket 1: VPN issue (Assigned to Alex Rivera / Network Lead)
        t1 = Ticket(
            ticket_number="INC-20261120-0001",
            title="VPN connection drops every 5 minutes during remote work",
            description="Since yesterday morning, my VPN client disconnects repeatedly every 5 to 10 minutes. I have to keep re-authenticating with 2FA, which disrupts my video meetings.",
            category="Network & Infrastructure",
            ticket_type="incident",
            urgency="high",
            impact="medium",
            priority="P2",
            status="in_progress",
            requester_id=user_john.id,
            assigned_agent_id=lead_users["Network & Infrastructure"].id,
            team_id=team_net.id,
            sla_policy_id=sla_p2.id,
            created_at=now - timedelta(hours=3),
            first_response_at=now - timedelta(hours=2, minutes=30),
            due_date=now - timedelta(hours=3) + timedelta(hours=8.0)
        )
        db.session.add(t1)
        db.session.commit()

        c1_1 = TicketComment(ticket_id=t1.id, user_id=lead_users["Network & Infrastructure"].id, body="Hi John, I am looking into this. Could you let me know if your home router has MTU size set to default (1500)? Also please try running 'ipconfig /flushdns'.", is_internal=False, created_at=now - timedelta(hours=2, minutes=30))
        c1_2 = TicketComment(ticket_id=t1.id, user_id=lead_users["Network & Infrastructure"].id, body="Internal Note: Checked the corporate gateway firewall logs; session timeout spikes correlate with recent ISP firmware push in the north region.", is_internal=True, created_at=now - timedelta(hours=2))
        c1_3 = TicketComment(ticket_id=t1.id, user_id=user_john.id, body="Thanks Alex! I flushed DNS and also restarted my router. It seems more stable now, testing for the next hour.", is_internal=False, created_at=now - timedelta(hours=1))
        db.session.add_all([c1_1, c1_2, c1_3])

        h1_1 = TicketHistory(ticket_id=t1.id, user_id=user_john.id, action="created", new_value="Ticket created (P2)", timestamp=now - timedelta(hours=3))
        h1_2 = TicketHistory(ticket_id=t1.id, user_id=None, action="auto_routed", new_value="Matched rule 'VPN & Network Infrastructure Rule' -> Network & Infrastructure", timestamp=now - timedelta(hours=3))
        h1_3 = TicketHistory(ticket_id=t1.id, user_id=None, action="auto_assigned", new_value=f"Assigned to {lead_users['Network & Infrastructure'].full_name}", timestamp=now - timedelta(hours=3))
        h1_4 = TicketHistory(ticket_id=t1.id, user_id=lead_users["Network & Infrastructure"].id, action="status_changed", old_value="assigned", new_value="in_progress", timestamp=now - timedelta(hours=2, minutes=30))
        db.session.add_all([h1_1, h1_2, h1_3, h1_4])

        # Ticket 2: Resolved ERP Ticket with 5-star CSAT
        agent_david = User.query.filter_by(username="agent_it").first()
        t2 = Ticket(
            ticket_number="INC-20261119-0002",
            title="Database error 500 when generating monthly payroll report in ERP",
            description="Whenever I try to export the monthly department payroll statement to Excel, the ERP application crashes with an unhandled SQL timeout error.",
            category="Software & Applications",
            ticket_type="bug",
            urgency="high",
            impact="high",
            priority="P1",
            status="resolved",
            requester_id=user_sarah.id,
            assigned_agent_id=agent_david.id,
            team_id=team_soft.id,
            sla_policy_id=sla_p1.id,
            created_at=now - timedelta(days=1, hours=4),
            first_response_at=now - timedelta(days=1, hours=3, minutes=45),
            resolved_at=now - timedelta(days=1, hours=1),
            due_date=now - timedelta(days=1, hours=4) + timedelta(hours=4.0),
            csat_rating=5,
            csat_feedback="David quickly identified the indexing issue on the database. Excellent and prompt resolution!"
        )
        db.session.add(t2)
        db.session.commit()

        c2_1 = TicketComment(ticket_id=t2.id, user_id=agent_david.id, body="Hello Sarah, we discovered a missing index on the payroll transaction table that was causing query execution to exceed the 30-second timeout. We applied the patch on the database cluster, and report generation is working now. Please verify.", is_internal=False, created_at=now - timedelta(days=1, hours=1))
        db.session.add(c2_1)

        h2_1 = TicketHistory(ticket_id=t2.id, user_id=user_sarah.id, action="created", new_value="Ticket created (P1)", timestamp=now - timedelta(days=1, hours=4))
        h2_2 = TicketHistory(ticket_id=t2.id, user_id=agent_david.id, action="status_changed", old_value="in_progress", new_value="resolved", timestamp=now - timedelta(days=1, hours=1))
        db.session.add_all([h2_1, h2_2])

        # Ticket 3: Hardware Monitor Ticket
        lead_hw = lead_users["Hardware & Peripherals"]
        t3 = Ticket(
            ticket_number="INC-20261122-0003",
            title="Second monitor flickering and going black periodically",
            description="The external Dell monitor connected via HDMI flickers violently and shuts off every few minutes. I tested with another HDMI cable and the issue persists.",
            category="Hardware & Peripherals",
            ticket_type="incident",
            urgency="medium",
            impact="low",
            priority="P4",
            status="assigned",
            requester_id=user_john.id,
            assigned_agent_id=lead_hw.id,
            team_id=team_hard.id,
            sla_policy_id=sla_p4.id,
            created_at=now - timedelta(minutes=45),
            due_date=now + timedelta(hours=47)
        )
        db.session.add(t3)
        db.session.commit()

        h3_1 = TicketHistory(ticket_id=t3.id, user_id=user_john.id, action="created", new_value="Ticket created (P4)", timestamp=now - timedelta(minutes=45))
        h3_2 = TicketHistory(ticket_id=t3.id, user_id=None, action="auto_routed", new_value="Matched rule 'Hardware & Device Peripherals Rule' -> Hardware & Peripherals", timestamp=now - timedelta(minutes=45))
        h3_3 = TicketHistory(ticket_id=t3.id, user_id=None, action="auto_assigned", new_value=f"Assigned to {lead_hw.full_name}", timestamp=now - timedelta(minutes=45))
        db.session.add_all([h3_1, h3_2, h3_3])

        # Ticket 4: Cloud pipeline issue
        lead_cloud = lead_users["Cloud & DevOps"]
        t4 = Ticket(
            ticket_number="INC-20261122-0004",
            title="Docker container deployment crashing on Kubernetes staging cluster",
            description="The CI/CD pipeline failed during staging rollout with CrashLoopBackOff on pod payments-service-prod.",
            category="Cloud & DevOps",
            ticket_type="bug",
            urgency="high",
            impact="medium",
            priority="P2",
            status="assigned",
            requester_id=user_sarah.id,
            assigned_agent_id=lead_cloud.id,
            team_id=team_cloud.id,
            sla_policy_id=sla_p2.id,
            created_at=now - timedelta(minutes=20),
            due_date=now + timedelta(hours=7, minutes=40)
        )
        db.session.add(t4)
        db.session.commit()

        h4_1 = TicketHistory(ticket_id=t4.id, user_id=user_sarah.id, action="created", new_value="Ticket created (P2)", timestamp=now - timedelta(minutes=20))
        h4_2 = TicketHistory(ticket_id=t4.id, user_id=None, action="auto_routed", new_value="Matched rule 'Cloud & DevOps Pipeline Rule' -> Cloud & DevOps", timestamp=now - timedelta(minutes=20))
        h4_3 = TicketHistory(ticket_id=t4.id, user_id=None, action="auto_assigned", new_value=f"Assigned to {lead_cloud.full_name}", timestamp=now - timedelta(minutes=20))
        db.session.add_all([h4_1, h4_2, h4_3])

        db.session.commit()
        print("Created sample tickets with full audit trails and conversation histories.")

if __name__ == '__main__':
    seed_database()
    print("Database seeding completed successfully!")
