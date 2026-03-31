# Flask guide

- Use application factories (`create_app`) for tests and multiple configs.
- Register blueprints for URL organization; keep views thin and delegate to services.
- Validate input with Pydantic or marshmallow before business logic.
- Run behind Gunicorn/uWSGI in production; disable debug mode.
