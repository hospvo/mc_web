from flask import Blueprint, jsonify
from sync_folia import run_sync

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/sync_folia", methods=["POST"])
def sync_folia():
    result = run_sync()
    return jsonify(result)