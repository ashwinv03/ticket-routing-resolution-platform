import os
from flask import current_app
from app.models import KnowledgeBase

def get_gemini_model():
    """Initializes Google Gemini model if API key is configured."""
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        # Using lightweight, fast gemini-1.5-flash
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"Failed to initialize Gemini API: {e}")
        return None

def find_relevant_kb_articles(ticket, limit=3):
    """Finds top matching KB articles using SQLite keyword matching."""
    search_terms = ticket.title.split() + ticket.category.split()
    query = KnowledgeBase.query
    
    # Simple keyword match across title, content, or tags
    filters = []
    for term in search_terms[:5]:
        if len(term) > 3:
            term_wildcard = f"%{term}%"
            filters.append(KnowledgeBase.title.ilike(term_wildcard))
            filters.append(KnowledgeBase.tags.ilike(term_wildcard))
            
    if filters:
        from sqlalchemy import or_
        articles = query.filter(or_(*filters)).limit(limit).all()
    else:
        articles = query.limit(limit).all()
        
    return articles

def summarize_ticket(ticket):
    """Generates a concise 3-bullet executive summary of the ticket history and current state."""
    model = get_gemini_model()
    
    # Build conversation context
    comments_text = "\n".join([
        f"[{c.author.full_name} ({'Internal' if c.is_internal else 'Public'})]: {c.body}"
        for c in ticket.comments
    ])
    
    prompt = f"""
You are an AI assistant in an enterprise IT support ticketing system.
Summarize the following support ticket in exactly 3 concise bullet points:
1. Core Issue Reported
2. Troubleshooting actions taken so far
3. Next step or pending blocker

Ticket Number: {ticket.ticket_number}
Title: {ticket.title}
Category: {ticket.category}
Priority: {ticket.priority}
Status: {ticket.status}
Description: {ticket.description}

Conversation Thread:
{comments_text if comments_text else 'No conversation updates yet.'}
"""
    if model:
        try:
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            print(f"Gemini API error during summarization: {e}")

    # Fallback / Offline Mock Generation
    return (
        f"• **Core Issue**: Requester reports '{ticket.title}' under category '{ticket.category}' with priority {ticket.priority}.\n"
        f"• **Current Progress**: Ticket is currently in '{ticket.status.upper()}' status with {len(ticket.comments)} updates recorded.\n"
        f"• **Action Required**: Needs investigation from {ticket.team.name if ticket.team else 'assigned team'} to meet the SLA target ({ticket.due_date.strftime('%Y-%m-%d %H:%M UTC') if ticket.due_date else 'Pending'})."
    )

def suggest_resolution(ticket):
    """Suggests concrete troubleshooting and resolution steps using ticket details and relevant KB articles."""
    model = get_gemini_model()
    kb_articles = find_relevant_kb_articles(ticket)
    
    kb_context = "\n\n".join([
        f"Article Title: {kb.title}\nCategory: {kb.category}\nContent: {kb.content[:400]}..."
        for kb in kb_articles
    ])
    
    prompt = f"""
You are an expert IT support engineer assistant.
Provide 3 to 4 recommended troubleshooting and resolution steps for the ticket below.
Make use of the provided Knowledge Base articles if relevant.

Ticket: {ticket.ticket_number} - {ticket.title}
Category: {ticket.category}
Description: {ticket.description}

Relevant Knowledge Base Articles:
{kb_context if kb_context else 'No specific KB articles found.'}

Format response with clear numbered steps and actionable advice for the support agent.
"""
    if model:
        try:
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            print(f"Gemini API error during resolution suggestion: {e}")

    # Fallback / Offline Mock Generation
    kb_tips = f" (Refer to KB: '{kb_articles[0].title}')" if kb_articles else ""
    return (
        f"**Recommended Diagnostic Steps:**\n\n"
        f"1. **Initial Verification**: Verify user credentials, network connection, or permissions for '{ticket.category}'.{kb_tips}\n"
        f"2. **Log Inspection**: Inspect error logs or request screenshots from the requester.\n"
        f"3. **Standard Remediation**: Apply the standard resolution playbook for {ticket.category} issues.\n"
        f"4. **Verification & Sign-off**: Test functionality with the user before transitioning status to Resolved."
    )

def generate_draft_response(ticket, agent_name="Support Agent"):
    """Drafts a polite, professional reply to the requester explaining progress or requesting details."""
    model = get_gemini_model()
    
    prompt = f"""
You are {agent_name}, a customer support agent.
Draft a friendly, professional response email to requester {ticket.requester.full_name} regarding ticket {ticket.ticket_number} ("{ticket.title}").
Explain that we are actively addressing the issue and provide either a status update or instructions on what information is needed.
Keep it under 150 words.
"""
    if model:
        try:
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            print(f"Gemini API error during draft generation: {e}")

    # Fallback / Offline Mock Generation
    return (
        f"Dear {ticket.requester.full_name},\n\n"
        f"Thank you for contacting support regarding \"{ticket.title}\" (Ticket #{ticket.ticket_number}).\n\n"
        f"I am actively investigating your request. To help us resolve this promptly within our SLA target, "
        f"could you please confirm if this issue occurs consistently or intermittently? Any screenshots or recent error messages would also be greatly appreciated.\n\n"
        f"We will keep you updated as we make progress.\n\n"
        f"Best regards,\n"
        f"{agent_name}\n"
        f"{ticket.team.name if ticket.team else 'Support Team'}"
    )
