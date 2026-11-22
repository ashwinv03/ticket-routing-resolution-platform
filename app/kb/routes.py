from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.models import db, KnowledgeBase

kb_bp = Blueprint('kb', __name__)

@kb_bp.route('/')
def list_articles():
    query_str = request.args.get('q', '').strip()
    category_filter = request.args.get('category')
    
    query = KnowledgeBase.query
    if category_filter:
        query = query.filter_by(category=category_filter)
        
    if query_str:
        wildcard = f"%{query_str}%"
        query = query.filter(
            (KnowledgeBase.title.ilike(wildcard)) |
            (KnowledgeBase.content.ilike(wildcard)) |
            (KnowledgeBase.tags.ilike(wildcard))
        )
        
    articles = query.order_by(KnowledgeBase.view_count.desc()).all()
    categories = [c[0] for c in db.session.query(KnowledgeBase.category).distinct().all()]
    
    return render_template('kb/list.html', articles=articles, categories=categories, query_str=query_str)

@kb_bp.route('/<int:article_id>')
def view_article(article_id):
    article = KnowledgeBase.query.get_or_404(article_id)
    article.view_count = (article.view_count or 0) + 1
    db.session.commit()
    return render_template('kb/view.html', article=article)

@kb_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_article():
    if current_user.role not in ['agent', 'supervisor', 'team_admin', 'admin']:
        abort(403)
        
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '').strip()
        tags = request.form.get('tags', '').strip()
        content = request.form.get('content', '').strip()
        
        if not title or not content:
            flash('Title and content are required.', 'danger')
            return render_template('kb/create.html')
            
        article = KnowledgeBase(
            title=title,
            category=category or 'General',
            tags=tags,
            content=content,
            author_id=current_user.id
        )
        db.session.add(article)
        db.session.commit()
        
        flash(f'Knowledge Base article "{article.title}" published successfully!', 'success')
        return redirect(url_for('kb.view_article', article_id=article.id))
        
    return render_template('kb/create.html')
