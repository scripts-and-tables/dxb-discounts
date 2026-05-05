# dxb-discounts

A directory of discounts available across Dubai — restaurants, attractions, hotels, retail & beauty.

**Stack:** Django 6 + Postgres (SQLite locally), Tailwind & HTMX via CDN, deployed to Railway.

## Local development

Requires Python 3.12+ (tested on 3.14).

```bash
# 1. Install dependencies
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt

# 2. Configure environment
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux
# then edit .env and set SECRET_KEY

# 3. Apply migrations and load seed data
python manage.py migrate
python manage.py seed
python manage.py createsuperuser

# 4. Run the dev server
python manage.py runserver
```

Visit http://127.0.0.1:8000/ — admin is at /admin/.

## Project layout

```
config/            # Django settings, root urls, wsgi
apps/places/       # Place model + admin
apps/discounts/    # Discount model + admin + public views
apps/pages/        # Homepage, about, healthz, sitemaps
templates/         # Server-rendered HTML (Tailwind + HTMX via CDN)
static/            # CSS overrides, favicon
```

## Deploying to Railway

1. Push this repo to GitHub.
2. In Railway, create a new project from the GitHub repo.
3. Add the **Postgres** plugin — `DATABASE_URL` is injected automatically.
4. Set environment variables in Railway:
   - `SECRET_KEY` — long random string
   - `DEBUG` — `False`
   - `ALLOWED_HOSTS` — your Railway domain (e.g. `dxb-discounts.up.railway.app`)
   - `CSRF_TRUSTED_ORIGINS` — `https://your-railway-domain`
5. Deploy. The release command runs migrations automatically.
6. From Railway shell: `python manage.py createsuperuser`, then `python manage.py seed` if you want demo data.

Healthcheck path: `/healthz/`.
