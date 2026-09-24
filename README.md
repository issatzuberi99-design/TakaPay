# TakaPay

TakaPay is a Django-based circular-economy platform for Zanzibar and Tanzania. Customers report recyclable waste, approved collectors complete verified collections, customers earn TakaPay Tokens, collectors earn TZS, and verified materials can be prepared for a public marketplace.

The project is a single Django website and PWA foundation. It uses Django templates and vanilla JavaScript; there is no separate React, Vue, or mobile frontend.

## Product workflows

### Customer

```text
Register -> Report waste and location -> Collection -> Verified quantity
-> Earn TakaPay Tokens -> Rewards Store or Cash Out
```

### Collector

```text
Apply -> Admin approval -> Accept collection -> Verify actual quantity
-> Complete collection -> Earn TZS -> Request payout
```

### Buyer

```text
Public marketplace -> Select material -> Request quantity
-> Provide contact details -> Submit buyer request
```

### Admin

The custom TakaPay Admin Dashboard is the primary operational control center. Django `/admin/` remains available as the technical fallback.

## Technology stack

- Python 3.14+
- Django 5.2
- Django REST Framework
- PostgreSQL
- Django Templates, HTML, CSS, and vanilla JavaScript
- Web App Manifest and service worker for PWA support
- Pillow for uploaded images
- `python-dotenv` for local environment configuration

## Project structure

```text
manage.py
config/
  settings.py          Django settings
  urls.py              Project and operational routes
  views.py             Home, logout, service-worker views
  api_views.py         API health endpoint
apps/
  accounts/            Users, roles, authentication, analytics, custom admin dashboard
  waste/               Waste categories, reports, location and quantities
  collections/         Collector jobs, acceptance and verified completion
  wallet/              Customer token wallet ledger
  economics/           Policies, material rates, collector wallets, bonuses, settlements and payouts
  rewards/              Rewards Store and redemptions
  marketplace/         Materials, preparation workflow and buyer requests
  cashout/              Customer token cash-out workflow
templates/
  base.html             Shared page shell
  components/           Shared navigation, messages and reusable template fragments
  accounts/             Customer, collector and admin pages
  collections/          Collection workflow pages
  economics/            Collector payout page
  marketplace/          Public marketplace and buyer request pages
  rewards/              Rewards Store pages
  wallet/               Customer wallet pages
  waste/                Waste reporting pages
static/
  css/tokens.css        Canonical TakaPay design tokens
  css/base.css          Global element defaults
  css/components.css    Shared buttons, cards, forms, badges, alerts and tables
  css/layouts.css       Shared containers and layout primitives
  css/site.css          Legacy compatibility and page-specific styles still in use
  css/pages/landing.css Landing-only composition and imagery
  js/                   PWA, landing navigation and waste-report behavior
  images/               Icons and landing-page imagery
  manifest.json         PWA manifest
  service-worker.js     PWA cache and offline shell behavior
requirements.txt
.env.example
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

### 2. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 3. Configure PostgreSQL

Create a PostgreSQL database and user, for example:

```sql
CREATE USER takapay_user WITH PASSWORD 'choose-a-local-password';
CREATE DATABASE takapay OWNER takapay_user;
```

Do not commit passwords or other secrets.

### 4. Configure environment variables

```bash
cp .env.example .env
```

Set `SECRET_KEY`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` in `.env`. Typical local values are:

```dotenv
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_HOST=localhost
DB_PORT=5432
```

`.env` is ignored by Git. `.env.example` is safe to commit because it contains placeholders only.

### 5. Apply migrations

```bash
python manage.py migrate
```

The repository includes migrations. Use `makemigrations` only after changing models:

```bash
python manage.py makemigrations
python manage.py makemigrations --check
```

### 6. Create an admin user

```bash
python manage.py createsuperuser
```

The custom dashboard is available at `/admin/dashboard/`. The technical Django admin is available at `/admin/`.

### 7. Start the development server

```bash
python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

If port `8000` is already in use, stop the existing Django process or choose another port:

```bash
python manage.py runserver 127.0.0.1:8001
```

## Economic engine

The `apps.economics` app keeps customer Tokens separate from collector TZS earnings.

### Settlement calculation

Settlement uses the collector-verified quantity:

```text
verified quantity x material rate = gross settlement value
```

The active economic policy then partitions the gross value:

```text
customer allocation
collector base earning
operations allocation
```

The initial pilot policy is configurable and defaults conceptually to:

```text
Customer:   30%
Collector:  30%
Operations: 40%
```

The three percentages must total exactly 100%. Material rates are separate from the economic partition. Collector bonuses are separate ledger entries and are not included in the collector base percentage.

### Historical settlement snapshots

When a collection is completed through the configured economic path, the settlement stores the policy, material rate, verified quantity, gross value, allocations, bonus, and timestamp used at that moment. Future changes to rates or percentages do not alter historical settlements.

Settlement, customer credit, collector credit, bonus, marketplace preparation, and collection completion occur atomically. A critical failure rolls the complete operation back.

### Wallets

- Customer wallet: ledger-derived TakaPay Tokens.
- Collector wallet: separate ledger-derived TZS earnings.
- Buyers do not receive wallets.
- Neither wallet stores a manually maintained balance.

### Payout and cash-out rules

- Customer cash-out minimum: **10,000 Tokens**.
- Customer conversion: **1 Token = TZS 100**.
- Therefore, 100 Tokens are worth TZS 10,000.
- Collector payout minimum: **TZS 10,000**.
- These are eligibility thresholds, not expiration rules.
- Balances remain available when they are below the threshold.
- Rejected payouts and cash-outs refund their ledger deductions once.

Economic administration is available through the custom dashboard at:

```text
/admin/operations/economics/
```

It provides controls for:

- Economic policies
- Material rates
- Collector bonuses
- Collector wallets
- Collector payouts
- Settlement history
- Customer and collector payout thresholds

## Main routes

### Public and authentication

| Route | Purpose |
|---|---|
| `/` | Public TakaPay landing page |
| `/register/` | Customer registration |
| `/register/collector/` | Collector application |
| `/login/` | Customer, collector and admin login |
| `/logout/` | Secure POST logout |
| `/dashboard/` | Role-based dashboard redirect |
| `/api/health/` | API health response |

### Customer and collector operations

| Route | Purpose |
|---|---|
| `/waste/` | Waste reports and reporting workflow |
| `/collections/` | Collector collection workflow |
| `/wallet/` | Customer Token wallet and ledger |
| `/rewards/` | Rewards Store and redemptions |
| `/cashout/` | Customer cash-out workflow |
| `/economics/payout/` | Collector TZS payout request |
| `/marketplace/` | Public recyclable-material marketplace |

### Custom admin operations

| Route | Purpose |
|---|---|
| `/admin/dashboard/` | Analytics and operational dashboard |
| `/admin/operations/collectors/` | Collector applications |
| `/admin/operations/collections/` | Collection requests |
| `/admin/operations/collection-history/` | Completed collections |
| `/admin/operations/wallet-activity/` | Customer wallet activity |
| `/admin/operations/cash-outs/` | Customer cash-out queue |
| `/admin/operations/token-rates/` | Customer reward/token rates |
| `/admin/operations/marketplace-preparation/` | Prepare collected materials |
| `/admin/operations/published-materials/` | Published marketplace materials |
| `/admin/operations/buyer-requests/` | Buyer request queue |
| `/admin/operations/rewards/` | Rewards Store management |
| `/admin/operations/redemptions/` | Reward redemption activity |
| `/admin/operations/economics/` | Economic controls and settlement history |

## Design system

The current landing page establishes the TakaPay visual language for the application:

- Warm cream page background
- Deep teal/near-black brand structure and text
- Green/teal value and success actions
- White surfaces
- Restrained coral attention accent
- Shared typography, spacing, radius, shadows and focus treatment

The shared CSS architecture is:

```text
static/css/tokens.css
        |
static/css/base.css
        |
static/css/components.css
        |
static/css/layouts.css
        |
page-specific styles
```

Change global theme values in `tokens.css` first. Use `base.css` for element defaults, `components.css` for reusable UI primitives, `layouts.css` for shared containers/layouts, and page styles only for genuinely page-specific behavior.

The service worker uses versioned caches and network-first handling for HTML, CSS, and JavaScript so local theme changes are not hidden indefinitely by stale assets. A hard refresh may still be useful during development:

```text
Ctrl+Shift+R
```

## API health check

With the server running:

```bash
curl http://127.0.0.1:8000/api/health/
```

Expected response:

```json
{"status":"ok","service":"TakaPay API"}
```

## Testing and quality checks

Run the complete serial test suite:

```bash
python manage.py test --noinput
```

Useful focused suites:

```bash
python manage.py test apps.accounts --noinput
python manage.py test apps.cashout --noinput
python manage.py test apps.economics --noinput
python manage.py test apps.wallet apps.collections --noinput
```

Before submitting changes:

```bash
python manage.py check
python manage.py makemigrations --check
git diff --check
```

## Security and deployment notes

- Never commit `.env`, passwords, API keys, or production secrets.
- `DEBUG=True` is intended only for local development.
- Configure `ALLOWED_HOSTS` for every deployed hostname.
- Use a production WSGI/ASGI server instead of `runserver` in production.
- Configure PostgreSQL credentials through environment variables.
- Review uploaded media storage and static-file serving before deployment.
- The service worker is intentionally small and should be reviewed when adding offline functionality.
