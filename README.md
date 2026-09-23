# TakaPay

TakaPay is a learning-focused waste-to-value platform for Zanzibar. Citizens will be able to report recyclable waste, connect with approved collectors, earn TakaPay Tokens, and later redeem rewards or request money. Verified materials will also be available through a public marketplace for recycling buyers.

This repository contains the first project foundation only. The customer dashboard, collector workflow, authentication screens, wallet ledger, and marketplace submission workflow will be built in later tasks.

## Technology stack

- Python 3.14+
- Django 5.2
- Django REST Framework
- PostgreSQL
- Django Templates, HTML, CSS, and vanilla JavaScript
- Web App Manifest and a small service worker for the PWA foundation

## Project structure

```text
manage.py                 Django command-line entry point
config/                   Project settings, URLs, views, and API health endpoint
apps/accounts/            Custom User model and admin configuration
apps/waste/               WasteCategory model
apps/collections/         Reserved for collection workflow models
apps/wallet/              Basic Wallet relationship
apps/rewards/             Reward model
apps/marketplace/         MarketplaceMaterial and BuyerRequest models
templates/                Django templates
static/css/               Site styles
static/js/                PWA and install-button JavaScript
static/manifest.json      PWA manifest
requirements.txt          Python dependencies
.env.example              Environment variable template
```

## Local setup

### 1. Create and activate a virtual environment

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install requirements

```bash
python -m pip install -r requirements.txt
```

### 3. Configure PostgreSQL

Create a PostgreSQL database and user. For example, from `psql` as a PostgreSQL administrator:

```sql
CREATE USER takapay_user WITH PASSWORD 'choose-a-local-password';
CREATE DATABASE takapay OWNER takapay_user;
```

Do not commit the password or any other secret.

### 4. Create the environment file

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set `SECRET_KEY`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` to match your local PostgreSQL setup. `DB_HOST=localhost` and `DB_PORT=5432` are the usual local values.

### 5. Create and apply migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

The initial migrations are included in the repository. Running `makemigrations` again should report no changes unless you edit a model.

### 6. Create an admin user

```bash
python manage.py createsuperuser
```

### 7. Start the development server

```bash
python manage.py runserver
```

Open the website at <http://127.0.0.1:8000/>. The Django admin is at <http://127.0.0.1:8000/admin/>.

## API health check

With the development server running, open <http://127.0.0.1:8000/api/health/> or run:

```bash
curl http://127.0.0.1:8000/api/health/
```

Expected response:

```json
{"status":"ok","service":"TakaPay API"}
```

## Authentication

Public registration creates customer accounts only. Collector applications use `/register/collector/` and create a pending `CollectorProfile`. Admin accounts are created with `python manage.py createsuperuser`; they can review collector profiles in Django admin and change their verification status to approved or rejected.

Authentication routes:

- `/register/` customer registration
- `/register/collector/` collector application
- `/login/` username or email login
- `/logout/` secure POST logout
- `/dashboard/` role-based placeholder dashboard
- `/collector/jobs/` approved-collector-only placeholder

Run the auth tests with:

```bash
python manage.py test apps.accounts
```

## How the foundation works

- `accounts.User` extends Django's `AbstractUser` and adds `role`, `phone_number`, and collector verification status. Buyers are not represented as users.
- `wallet.Wallet` is a one-to-one relationship with a user. It intentionally does not contain a token balance; a transaction ledger will be added later as the source of truth.
- PostgreSQL is configured in `config/settings.py` using values loaded from `.env` with `python-dotenv`.
- Django templates render the single website. The same pages serve the PWA; there is no separate frontend application.
- `static/manifest.json` describes the installable app, while `/service-worker.js` caches the home page shell. The install button uses the browser install prompt when supported.
- Django REST Framework provides `GET /api/health/` as a simple service check.

## Next task

Build the first real domain workflow: customer registration/login foundation and the waste reporting model/form, including a browser geolocation capture field. Keep collector approval and token transactions as separate, later steps.
