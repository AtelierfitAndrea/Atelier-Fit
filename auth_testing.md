# Auth testing (Emergent Google Auth)
- Create test user + session in mongo (DB from backend/.env DB_NAME): users {user_id,email,name,created_at}, user_sessions {user_id, session_token, expires_at (+7d), created_at}
- Use cookie session_token or header Authorization: Bearer <token>
- Single-session rule: server._enforce_session_limit(user_id) runs after POST /api/auth/session; keeps newest 1 session (FAMILY plan: 4); revoked tokens go to revoked_sessions and get 401 detail "session_revoked_other_device"

## Founder admin (single password)
- POST /api/admin/login {"password":"AtelierFondatore2026!"} -> sets admin_token cookie (path /api/admin). Wrong -> 401; 5 wrong per IP -> 429 for 15 min (db.admin_login_attempts)
- GET /api/admin/stats requires the cookie (401 otherwise); data is DEMO (demo: true)
- Clean up: db.admin_login_attempts.deleteMany({}) after lockout tests
