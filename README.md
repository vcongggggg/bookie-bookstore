# Bookie

Bookie is a Django bookstore project. The active application lives in `Project/`.

## Run Locally

```powershell
cd Project
copy .env.example .env
python manage.py migrate
python manage.py seed_books --limit 50
python manage.py runserver
```

From the repository root, these commands also work:

```powershell
python Project\manage.py check
python Project\manage.py test books
python Project\manage.py runserver
```

## Repository Layout

- `Project/books/`: main Django app
- `Project/bookstore/`: Django settings and URL configuration
- `Project/templates/`: HTML templates
- `Project/static/`: CSS, JavaScript, and images
- `Project/.env.example`: safe local configuration template
- `potential_upgrades.md`: upgrade ideas and roadmap notes
- `CODEBASE_CONTEXT.md`: current codebase notes for maintainers

The old root-level Django tree was removed to avoid import conflicts. Treat `Project/` as the single source of truth.
