"""
app.py — Flask Backend for eBay Dropship Bot
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Connects ebay_bot.py → Vue frontend (Search.vue)

SETUP:
  pip install flask flask-cors flask-jwt-extended bcrypt

RUN:
  python app.py
  # or production:
  gunicorn -w 2 -b 0.0.0.0:5000 app:app

ENDPOINTS:
  POST /auth/login              → { token, email, role, userId }
  POST /auth/register           → { token, email, role, userId }
  POST /product/search          → [ { productName, ebay, aliexpress, analysis }, ... ]
  GET  /admin/stats             → { totalUsers, todaySearches }
  GET  /admin/users             → [ { userId, email, role, plan, ... } ]
  POST /admin/add-user
  POST /admin/update-user
  DELETE /admin/users/<id>
  GET  /admin/keywords          → [ { id, keywordText, searchCount } ]
  POST /admin/keywords
  PUT  /admin/keywords/<id>
  DELETE /admin/keywords/<id>
  GET  /admin/threshold         → { minWeeklySales, minProfitPercent }
  POST /admin/threshold
  POST /admin/update-search-count
"""

import os
import json
import uuid
import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, request, jsonify, g
from flask_cors import CORS

# ── optional JWT (falls back to simple token if not installed) ──
try:
    from flask_jwt_extended import (
        JWTManager, create_access_token,
        jwt_required, get_jwt_identity,
        get_jwt,
    )
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    print("[WARN] flask-jwt-extended not installed. Using simple token auth.")

# ── bot import ──────────────────────────────────────────────────
from ebay_bot import run_search


app = Flask(__name__)
CORS(app, supports_credentials=True)

# ── Config ──────────────────────────────────────────────────────
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-production-please")
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "change-me-jwt-secret")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=24)
app.config["DATABASE"] = os.getenv("DATABASE", "dropship.db")

if JWT_AVAILABLE:
    jwt = JWTManager(app)


# ─────────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────────

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config["DATABASE"])
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            email       TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'User',
            plan        TEXT NOT NULL DEFAULT 'Basic',
            searchLimit INTEGER NOT NULL DEFAULT 10,
            usedSearches INTEGER NOT NULL DEFAULT 0,
            createdAt   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS keywords (
            id          TEXT PRIMARY KEY,
            keywordText TEXT NOT NULL,
            searchCount INTEGER NOT NULL DEFAULT 0,
            createdAt   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS searches (
            id        TEXT PRIMARY KEY,
            userId    TEXT NOT NULL,
            keyword   TEXT NOT NULL,
            country   TEXT NOT NULL,
            createdAt TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        INSERT OR IGNORE INTO settings (key, value) VALUES ('minWeeklySales',  '10');
        INSERT OR IGNORE INTO settings (key, value) VALUES ('minProfitPercent','20');
    """)
    # Create default admin if none exists
    admin = db.execute("SELECT id FROM users WHERE role = 'Admin' LIMIT 1").fetchone()
    if not admin:
        admin_id = str(uuid.uuid4())
        pw_hash  = hash_password("admin123")
        db.execute(
            "INSERT INTO users (id, email, password, role, plan, searchLimit, usedSearches, createdAt) "
            "VALUES (?, ?, ?, 'Admin', 'Pro', -1, 0, ?)",
            (admin_id, "admin@dropship.ai", pw_hash, datetime.utcnow().isoformat()),
        )
        print("[DB] Created default admin: admin@dropship.ai / admin123")
    db.commit()
    db.close()


# ─────────────────────────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────────────────────────

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def make_token(user_id: str, email: str, role: str) -> str:
    if JWT_AVAILABLE:
        return create_access_token(
            identity=user_id,
            additional_claims={"email": email, "role": role},
        )
    # Fallback: simple token (not secure, just for dev)
    import base64, time
    payload = f"{user_id}:{email}:{role}:{int(time.time()) + 86400}"
    return base64.b64encode(payload.encode()).decode()


def decode_token_simple(token: str) -> dict | None:
    try:
        import base64
        payload = base64.b64decode(token.encode()).decode()
        parts   = payload.split(":")
        uid, email, role, exp = parts[0], parts[1], parts[2], int(parts[3])
        import time
        if time.time() > exp:
            return None
        return {"sub": uid, "email": email, "role": role}
    except Exception:
        return None


def require_auth(fn):
    """Works with both JWT and simple token."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip()
        if not token:
            return jsonify({"error": "Missing token"}), 401

        if JWT_AVAILABLE:
            # Let flask-jwt-extended handle it via @jwt_required decorator
            pass
        else:
            claims = decode_token_simple(token)
            if not claims:
                return jsonify({"error": "Invalid or expired token"}), 401
            request.auth_user_id   = claims["sub"]
            request.auth_user_email = claims["email"]
            request.auth_user_role  = claims["role"]

        return fn(*args, **kwargs)
    return wrapper


def get_current_user_id():
    if JWT_AVAILABLE:
        return get_jwt_identity()
    return getattr(request, "auth_user_id", None)


def get_current_role():
    if JWT_AVAILABLE:
        return get_jwt().get("role", "User")
    return getattr(request, "auth_user_role", "User")


def auth_required(admin=False):
    """Decorator factory."""
    def decorator(fn):
        if JWT_AVAILABLE:
            fn = jwt_required()(fn)

        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not JWT_AVAILABLE:
                auth = request.headers.get("Authorization", "")
                token = auth.replace("Bearer ", "").strip()
                claims = decode_token_simple(token)
                if not claims:
                    return jsonify({"error": "Unauthorized"}), 401
                request.auth_user_id    = claims["sub"]
                request.auth_user_email = claims["email"]
                request.auth_user_role  = claims["role"]
                if admin and claims["role"] != "Admin":
                    return jsonify({"error": "Forbidden"}), 403
            else:
                if admin and get_current_role() != "Admin":
                    return jsonify({"error": "Forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────────────────────────

@app.post("/auth/login")
def login():
    body  = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    pw    = body.get("password") or ""

    if not email or not pw:
        return jsonify({"error": "Email and password required"}), 400

    db   = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE LOWER(email) = ?", (email,)
    ).fetchone()

    if not user or user["password"] != hash_password(pw):
        return jsonify({"error": "Invalid email or password"}), 401

    token = make_token(user["id"], user["email"], user["role"])
    return jsonify({
        "token":  token,
        "email":  user["email"],
        "role":   user["role"],
        "userId": user["id"],
    })


@app.post("/auth/register")
def register():
    body  = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    pw    = body.get("password") or ""

    if not email or not pw:
        return jsonify({"error": "Email and password required"}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,)).fetchone()
    if existing:
        return jsonify({"error": "Email already registered"}), 409

    # Check threshold for default search limit
    limit_row = db.execute("SELECT value FROM settings WHERE key = 'defaultSearchLimit'").fetchone()
    default_limit = int(limit_row["value"]) if limit_row else 10

    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, email, password, role, plan, searchLimit, usedSearches, createdAt) "
        "VALUES (?, ?, ?, 'User', 'Basic', ?, 0, ?)",
        (user_id, email, hash_password(pw), default_limit, datetime.utcnow().isoformat()),
    )
    db.commit()

    token = make_token(user_id, email, "User")
    return jsonify({
        "token":  token,
        "email":  email,
        "role":   "User",
        "userId": user_id,
    }), 201


# ─────────────────────────────────────────────────────────────────
# PRODUCT SEARCH — main bot integration
# ─────────────────────────────────────────────────────────────────

@app.post("/product/search")
@auth_required()
def product_search():
    db      = get_db()
    user_id = get_current_user_id()
    body    = request.get_json(silent=True) or {}
    keyword = (body.get("keyword") or "").strip()
    country = (body.get("country") or "UK").strip()

    if not keyword:
        return jsonify({"error": "keyword is required"}), 400

    # ── Search limit check ────────────────────────────────────────
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user["searchLimit"] != -1 and user["usedSearches"] >= user["searchLimit"]:
        return jsonify({
            "error": f"Search limit reached ({user['searchLimit']}). "
                     "Contact admin to increase your limit."
        }), 429

    # ── Load thresholds ───────────────────────────────────────────
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    settings = {r["key"]: r["value"] for r in rows}
    # (thresholds are used by the bot via config constants;
    #  for dynamic overrides you could pass them into run_search)

    # ── Run the bot ───────────────────────────────────────────────
    try:
        products = run_search(keyword, country)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        app.logger.exception("Bot error")
        return jsonify({"error": f"Search failed: {str(e)}"}), 500

    # ── Record search in DB ───────────────────────────────────────
    search_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO searches (id, userId, keyword, country, createdAt) VALUES (?, ?, ?, ?, ?)",
        (search_id, user_id, keyword, country, datetime.utcnow().isoformat()),
    )
    # Increment used searches
    db.execute(
        "UPDATE users SET usedSearches = usedSearches + 1 WHERE id = ?", (user_id,)
    )
    # Bump keyword search count
    kw_row = db.execute(
        "SELECT id FROM keywords WHERE LOWER(keywordText) = ?", (keyword.lower(),)
    ).fetchone()
    if kw_row:
        db.execute(
            "UPDATE keywords SET searchCount = searchCount + 1 WHERE id = ?", (kw_row["id"],)
        )
    db.commit()

    return jsonify(products)


# ─────────────────────────────────────────────────────────────────
# ADMIN ROUTES
# ─────────────────────────────────────────────────────────────────

@app.get("/admin/stats")
@auth_required(admin=True)
def admin_stats():
    db       = get_db()
    total    = db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    today    = datetime.utcnow().strftime("%Y-%m-%d")
    searches = db.execute(
        "SELECT COUNT(*) AS n FROM searches WHERE createdAt LIKE ?", (f"{today}%",)
    ).fetchone()["n"]
    return jsonify({"totalUsers": total, "todaySearches": searches})


@app.get("/admin/users")
@auth_required(admin=True)
def admin_users():
    db    = get_db()
    rows  = db.execute("SELECT * FROM users ORDER BY createdAt DESC").fetchall()
    users = []
    for r in rows:
        lim  = r["searchLimit"]
        used = r["usedSearches"]
        users.append({
            "userId":       r["id"],
            "email":        r["email"],
            "role":         r["role"],
            "plan":         r["plan"],
            "searchLimit":  lim,
            "usedSearches": used,
            "remaining":    -1 if lim == -1 else max(0, lim - used),
        })
    return jsonify(users)


@app.post("/admin/add-user")
@auth_required(admin=True)
def admin_add_user():
    body  = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    pw    = body.get("password") or ""
    role  = body.get("role", "User")
    plan  = body.get("plan", "Basic")
    limit = int(body.get("searchLimit", 10))

    if not email or not pw:
        return jsonify({"error": "email and password required"}), 400

    db = get_db()
    if db.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,)).fetchone():
        return jsonify({"error": "Email already exists"}), 409

    uid = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, email, password, role, plan, searchLimit, usedSearches, createdAt) "
        "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
        (uid, email, hash_password(pw), role, plan, limit, datetime.utcnow().isoformat()),
    )
    db.commit()
    return jsonify({"userId": uid}), 201


@app.post("/admin/update-user")
@auth_required(admin=True)
def admin_update_user():
    body    = request.get_json(silent=True) or {}
    user_id = body.get("userId")
    if not user_id:
        return jsonify({"error": "userId required"}), 400

    db = get_db()
    db.execute(
        "UPDATE users SET email=?, role=?, plan=?, searchLimit=? WHERE id=?",
        (
            body.get("email", ""),
            body.get("role", "User"),
            body.get("plan", "Basic"),
            int(body.get("searchLimit", 10)),
            user_id,
        ),
    )
    db.commit()
    return jsonify({"ok": True})


@app.delete("/admin/users/<user_id>")
@auth_required(admin=True)
def admin_delete_user(user_id):
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    return jsonify({"ok": True})


@app.post("/admin/update-search-count")
@auth_required(admin=True)
def admin_update_search_count():
    body    = request.get_json(silent=True) or {}
    user_id = body.get("userId")
    delta   = int(body.get("delta", 0))
    db = get_db()
    db.execute(
        "UPDATE users SET usedSearches = MAX(0, usedSearches + ?) WHERE id = ?",
        (delta, user_id),
    )
    db.commit()
    return jsonify({"ok": True})


# ─── Keywords ────────────────────────────────────────────────────

@app.get("/admin/keywords")
@auth_required(admin=True)
def admin_get_keywords():
    db   = get_db()
    rows = db.execute("SELECT * FROM keywords ORDER BY searchCount DESC").fetchall()
    return jsonify([{
        "id":          r["id"],
        "keywordText": r["keywordText"],
        "searchCount": r["searchCount"],
    } for r in rows])


@app.post("/admin/keywords")
@auth_required(admin=True)
def admin_add_keyword():
    body = request.get_json(silent=True) or {}
    kw   = (body.get("keyword") or "").strip()
    if not kw:
        return jsonify({"error": "keyword required"}), 400

    db  = get_db()
    kid = str(uuid.uuid4())
    db.execute(
        "INSERT OR IGNORE INTO keywords (id, keywordText, searchCount, createdAt) VALUES (?, ?, 0, ?)",
        (kid, kw, datetime.utcnow().isoformat()),
    )
    db.commit()
    return jsonify({"id": kid}), 201


@app.put("/admin/keywords/<kid>")
@auth_required(admin=True)
def admin_update_keyword(kid):
    body = request.get_json(silent=True) or {}
    kw   = (body.get("keyword") or "").strip()
    if not kw:
        return jsonify({"error": "keyword required"}), 400

    db = get_db()
    db.execute("UPDATE keywords SET keywordText = ? WHERE id = ?", (kw, kid))
    db.commit()
    return jsonify({"ok": True})


@app.delete("/admin/keywords/<kid>")
@auth_required(admin=True)
def admin_delete_keyword(kid):
    db = get_db()
    db.execute("DELETE FROM keywords WHERE id = ?", (kid,))
    db.commit()
    return jsonify({"ok": True})


# ─── Thresholds ──────────────────────────────────────────────────

@app.get("/admin/threshold")
@auth_required(admin=True)
def admin_get_threshold():
    db   = get_db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    s    = {r["key"]: r["value"] for r in rows}
    return jsonify({
        "minWeeklySales":  int(s.get("minWeeklySales", 10)),
        "minProfitPercent": float(s.get("minProfitPercent", 20)),
    })


@app.post("/admin/threshold")
@auth_required(admin=True)
def admin_save_threshold():
    body = request.get_json(silent=True) or {}
    db   = get_db()
    if "minWeeklySales" in body:
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('minWeeklySales', ?)",
            (str(int(body["minWeeklySales"])),),
        )
    if "minProfitPercent" in body:
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('minProfitPercent', ?)",
            (str(float(body["minProfitPercent"])),),
        )
    db.commit()
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    with app.app_context():
        init_db()
    print("\n[APP] DropShip Bot Backend running on http://localhost:5000")
    print("[APP] Default admin: admin@dropship.ai / admin123\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
