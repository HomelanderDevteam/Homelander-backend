# HomeLander Backend

Django + Django REST Framework + PostgreSQL, built as a **modular monolith**: one project, one database, one app per feature.

**Built so far:** authentication (register, login, logout, token refresh, profile, change password).
**Next:** KYC, owner/agent applications, properties, verification, chat, payments, commissions, audit log.

---

## 1. Run it on your computer

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env
python manage.py migrate
python manage.py createsuperuser     # asks for phone number, first name, last name, password
python manage.py runserver 0.0.0.0:8000
```

- API docs for the frontend (Swagger, try requests in the browser): http://localhost:8000/api/docs/
- Staff admin: http://localhost:8000/admin/  (log in with the phone number or email)
- Health check: http://localhost:8000/api/health/
- Run the tests: `python manage.py test apps`

With no `DATABASE_URL` it uses a local SQLite file. Set `DATABASE_URL` to use PostgreSQL (the tests also pass on PostgreSQL).

**Connecting a Flutter app:** Android emulator uses `http://10.0.2.2:8000`; a real phone on the same Wi-Fi uses your computer's IP (for example `http://192.168.1.20:8000`); iOS simulator uses `http://localhost:8000`.

---

## 2. Folder structure

```
homelander_backend/
├── manage.py
├── requirements.txt
├── .env.example              copy to .env (never commit .env)
├── render.yaml, Procfile     hosting files
├── config/                   project settings, not a feature
│   ├── settings/
│   │   ├── base.py           shared settings
│   │   ├── dev.py            local development
│   │   └── prod.py           hosted / production
│   └── urls.py               one include() line per feature app
├── common/                   small helpers shared by all features
│   ├── models.py             BaseModel: UUID id + created_at + updated_at
│   ├── phone.py              phone number cleaning (+234 format)
│   └── views.py              /api/health/
└── apps/                     ONE FOLDER PER FEATURE
    └── accounts/             authentication (first feature)
        ├── models.py         the tables
        ├── managers.py       how users are created
        ├── selectors.py      read-only queries ("find a user by phone or email")
        ├── services.py       the business actions (register_user, login_user, ...)
        ├── serializers.py    check incoming data, shape outgoing data
        ├── views.py          thin: receive request, call service, return response
        ├── urls.py           the feature's web addresses
        ├── admin.py          staff admin screens
        ├── backends.py       lets Django log in with phone OR email
        ├── exceptions.py     clear error types
        ├── tests/            automated tests
        └── migrations/       database change history
```

**How one request flows:** `urls.py` -> `views.py` -> `serializers.py` (validate) -> `services.py` (rules and work) -> `models.py` (database) -> `serializers.py` (shape the answer).

**Rules that keep it a modular monolith**
1. Every feature is its own app under `apps/`. Its tables, rules and URLs stay inside it.
2. Rules live in `services.py`, never in views or serializers.
3. Another app may use a feature through its `services.py` / `selectors.py`, not by reaching into its views or serializers.
4. Cross-app database links (ForeignKey) are fine; do not import another app's views.

### Adding the next feature (example: `kyc`)
1. `mkdir apps/kyc && python manage.py startapp kyc apps/kyc`
2. In `apps/kyc/apps.py` set `name = "apps.kyc"` and `label = "kyc"`.
3. Add `"apps.kyc"` to `LOCAL_APPS` in `config/settings/base.py`.
4. Models inherit `common.models.BaseModel`. Add `services.py`, `selectors.py`, `serializers.py`, `views.py`, `urls.py`, `tests/`.
5. Add `path("api/v1/kyc/", include("apps.kyc.urls"))` to `config/urls.py`.
6. `python manage.py makemigrations kyc && python manage.py migrate`

---

## 3. Authentication API (for the frontend)

Base path: `/api/v1/auth/`. Send JSON. Protected endpoints need the header `Authorization: Bearer <access token>`.

| Method | Path | Needs login | What it does |
|---|---|---|---|
| POST | `register/` | no | Create account and log in. Returns `201` |
| POST | `login/` | no | Log in with phone number or email |
| POST | `token/refresh/` | no | Exchange refresh token for new tokens |
| POST | `logout/` | no | Blacklist the refresh token |
| GET | `me/` | yes | My profile |
| PATCH | `me/` | yes | Update first name, last name, email |
| POST | `password/change/` | yes | Change password, log out other devices |

### Register
```json
POST /api/v1/auth/register/
{ "first_name": "Ada", "last_name": "Obi", "phone_number": "08012345678",
  "email": "ada@example.com",            // optional
  "password": "Sup3r-Secret-Pass", "password_confirm": "Sup3r-Secret-Pass" }
```
Response `201`:
```json
{ "user": { "id": "uuid", "first_name": "Ada", "last_name": "Obi", "full_name": "Ada Obi",
            "phone_number": "+2348012345678", "email": "ada@example.com",
            "is_staff": false, "date_joined": "..." },
  "access": "<short-lived token>", "refresh": "<longer-lived token>" }
```
Phone numbers can be typed as `08012345678`, `+2348012345678`, `0801 234 5678` and are stored as `+2348012345678`.

### Login
```json
POST /api/v1/auth/login/
{ "identifier": "08012345678", "password": "Sup3r-Secret-Pass" }
```
`identifier` is a phone number **or** an email. Response `200` has the same shape as register.

### Refresh, logout
```json
POST /api/v1/auth/token/refresh/   { "refresh": "<refresh token>" }   ->  { "access": "...", "refresh": "..." }
POST /api/v1/auth/logout/          { "refresh": "<refresh token>" }   ->  { "detail": "Logged out." }
```
The refresh token **rotates**: each refresh returns a new one and the old one stops working. Always store the newest.

### Errors
| Status | Meaning | Body |
|---|---|---|
| 400 | Invalid data | `{ "phone_number": ["..."], "password": ["..."] }` (field name -> messages) |
| 401 | Not logged in, bad token, wrong login | `{ "detail": "..." }` |
| 403 | Account deactivated | `{ "detail": "..." }` |
| 409 | Duplicate account (race) | `{ "detail": "..." }` |
| 429 | Too many attempts, slow down | `{ "detail": "..." }` |

### What the frontend should do
1. After login/register, store `access` and `refresh` in secure storage (Flutter: `flutter_secure_storage`).
2. Send `Authorization: Bearer <access>` on every protected request.
3. On a `401` from a protected endpoint: call `token/refresh/` once, save the new tokens, repeat the request. If refresh also returns `401`, send the user to the login screen.
4. On logout: call `logout/` with the refresh token, then delete both tokens locally.
5. Token lifetimes: access 30 minutes, refresh 7 days (set in `.env`).

---

## 4. Put it online for development

**Fastest (no deploy):** run `python manage.py runserver 0.0.0.0:8000` and share it through a tunnel such as ngrok (`ngrok http 8000`) or a Cloudflare quick tunnel. The URL works until you stop the tunnel.

**Stable URL: Render** (free web service, cold starts after inactivity, free database is time-limited; check render.com for current limits):
1. Push this folder to a GitHub repository.
2. Render dashboard -> New -> Blueprint -> choose the repo (it reads `render.yaml`).
3. When asked, enter `ADMIN_PHONE_NUMBER` and `ADMIN_PASSWORD` (creates your first admin automatically).
4. Open `https://<your-service>.onrender.com/api/docs/`.

Other hosts (Railway, Fly.io, a VPS) work too: set `DJANGO_SETTINGS_MODULE=config.settings.prod`, `SECRET_KEY`, `DATABASE_URL`, and use the `Procfile` command.

---

## 5. Decisions made for tonight (change them in one place)

| Decision | Chosen for now | Where to change |
|---|---|---|
| Login ID | Phone number **or** email | `accounts/selectors.py` |
| Phone verification (SMS code) | Not yet (needs an SMS provider) | next step |
| Token lifetimes | 30 min / 7 days | `.env` |
| Guest browsing | Every endpoint needs login unless marked public | `REST_FRAMEWORK` in `base.py` |
| Roles | No role field; roles come from approvals (KYC feature) | by design |
