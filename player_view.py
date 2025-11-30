from flask import Blueprint, render_template, abort, request, jsonify
from flask_login import login_required, current_user
from models import Server, PlayerServerAccess, PlayerNotice, Mod
from datetime import datetime

player_api = Blueprint("player_view", __name__)

@player_api.route("/server/<int:server_id>/player")
@login_required
def player_view(server_id):
    """Zobrazení hráčského pohledu na server"""
    server = Server.query.get_or_404(server_id)

    # Ověření přístupu
    access = PlayerServerAccess.query.filter_by(
        user_id=current_user.id, server_id=server.id
    ).first()
    if not access:
        abort(403)

    return render_template("server_panel_player.html", server=server)


# -----------------------------
# API: Player Notices
# -----------------------------
@player_api.route("/api/server/player-notices")
@login_required
def get_player_notices():
    server_id = request.args.get("server_id", type=int)
    server = Server.query.get_or_404(server_id)

    access = PlayerServerAccess.query.filter_by(
        user_id=current_user.id, server_id=server.id
    ).first()
    if not access:
        abort(403)

    notices = PlayerNotice.query.filter_by(
        server_id=server_id, is_active=True
    ).order_by(PlayerNotice.created_at.desc())

    return jsonify([
        {
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "notice_type": n.notice_type,
            "created_at": n.created_at.strftime("%d.%m.%Y %H:%M"),
            "author": n.author.username
        }
        for n in notices
    ])


# -----------------------------
# API: Installed Mods (jen pro čtení)
# -----------------------------
@player_api.route("/api/server/mods/list")
@login_required
def get_installed_mods():
    server_id = request.args.get("server_id", type=int)
    server = Server.query.get_or_404(server_id)

    access = PlayerServerAccess.query.filter_by(
        user_id=current_user.id, server_id=server.id
    ).first()
    if not access:
        abort(403)

    mods = server.mods.filter_by(is_active=True).all()
    return jsonify([
        {
            "name": m.display_name or m.name,
            "version": m.version,
            "author": m.author,
            "category": m.category,
        }
        for m in mods
    ])


# -----------------------------
# API: Player Report
# -----------------------------
@player_api.route("/api/player/report", methods=["POST"])
@login_required
def player_report():
    data = request.get_json(force=True)
    server_id = data.get("server_id")
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Zpráva nesmí být prázdná."}), 400

    # Jednoduše log do konzole (do budoucna může jít do tabulky nebo Discord webhooku)
    print(f"[REPORT] Hráč {current_user.username} → Server {server_id}: {message}")

    return jsonify({"success": True, "message": "Zpráva byla odeslána adminům."})
