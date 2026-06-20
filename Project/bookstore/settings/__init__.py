import os

# Select the appropriate settings module
# Default to local development, but switch to production if specified
DJANGO_ENV = os.getenv('DJANGO_ENV', 'development').lower()
DEBUG_ENV = os.getenv('DEBUG', 'True')

if DJANGO_ENV == 'production' or DEBUG_ENV == 'False':
    from .production import *
else:
    from .local import *
