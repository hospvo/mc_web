# routes_notices.py
from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime
from models import db, Server, PlayerNotice

notices_api = Blueprint('notices_api', __name__)

@notices_api.route('/api/notices')
@login_required
def get_notices():
    """Získá oznámení pro daný server"""
    server_id = request.args.get('server_id', type=int)
    if not server_id:
        return jsonify({'error': 'Chybí server_id'}), 400
    
    server = Server.query.get_or_404(server_id)
    
    # Ověření přístupu k serveru
    if server.owner_id != current_user.id and current_user not in server.admins:
        # Hráči vidí pouze aktivní oznámení
        notices = PlayerNotice.query.filter_by(
            server_id=server_id, 
            is_active=True
        ).order_by(
            PlayerNotice.is_pinned.desc(),
            PlayerNotice.created_at.desc()
        ).all()
    else:
        # Admini vidí všechna oznámení
        notices = PlayerNotice.query.filter_by(
            server_id=server_id
        ).order_by(
            PlayerNotice.is_pinned.desc(),
            PlayerNotice.created_at.desc()
        ).all()
    
    return jsonify([{
        'id': notice.id,
        'title': notice.title,
        'content': notice.content,
        'type': notice.notice_type,
        'is_pinned': notice.is_pinned,
        'is_active': notice.is_active,
        'author': notice.author.username,
        'created_at': notice.created_at.strftime('%d.%m.%Y %H:%M'),
        'updated_at': notice.updated_at.strftime('%d.%m.%Y %H:%M') if notice.updated_at else None,
        'can_edit': server.owner_id == current_user.id or current_user in server.admins
    } for notice in notices])

@notices_api.route('/api/notices/create', methods=['POST'])
@login_required
def create_notice():
    """Vytvoří nové oznámení"""
    data = request.get_json()
    server_id = data.get('server_id')
    title = data.get('title')
    content = data.get('content')
    notice_type = data.get('type', 'info')
    is_pinned = data.get('is_pinned', False)
    
    if not server_id or not title or not content:
        return jsonify({'success': False, 'error': 'Chybí povinné údaje'}), 400
    
    server = Server.query.get_or_404(server_id)
    
    # Pouze admini mohou vytvářet oznámení
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
    try:
        notice = PlayerNotice(
            server_id=server_id,
            author_id=current_user.id,
            title=title,
            content=content,
            notice_type=notice_type,
            is_pinned=is_pinned,
            created_at=datetime.utcnow()
        )
        
        db.session.add(notice)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Oznámení bylo vytvořeno',
            'notice_id': notice.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@notices_api.route('/api/notices/update/<int:notice_id>', methods=['PUT'])
@login_required
def update_notice(notice_id):
    """Aktualizuje existující oznámení"""
    notice = PlayerNotice.query.get_or_404(notice_id)
    server = notice.server
    
    # Pouze admini mohou upravovat oznámení
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
    data = request.get_json()
    
    try:
        if 'title' in data:
            notice.title = data['title']
        if 'content' in data:
            notice.content = data['content']
        if 'type' in data:
            notice.notice_type = data['type']
        if 'is_pinned' in data:
            notice.is_pinned = data['is_pinned']
        if 'is_active' in data:
            notice.is_active = data['is_active']
        
        notice.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Oznámení bylo aktualizováno'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@notices_api.route('/api/notices/delete/<int:notice_id>', methods=['DELETE'])
@login_required
def delete_notice(notice_id):
    """Smaže oznámení"""
    notice = PlayerNotice.query.get_or_404(notice_id)
    server = notice.server
    
    # Pouze admini mohou mazat oznámení
    if server.owner_id != current_user.id and current_user not in server.admins:
        abort(403)
    
    try:
        db.session.delete(notice)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Oznámení bylo smazáno'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500