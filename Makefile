DEV := docker compose -f docker-compose.dev.yml
PROD := docker compose -f docker-compose.prod.yml
DEV_TEST := $(DEV) --profile test
DEV_NGROK := $(DEV) --profile ngrok
PROD_NGROK := $(PROD) --profile ngrok

# Which checkout to copy development data between; see clone-dev-data.
FROM_PROJECT ?= social-network
TO_PROJECT ?= social-network-w2

.PHONY: help up up-build build down restart logs ps shell migrate makemigrations test build-test superuser \
        worker-logs ngrok ngrok-down clone-dev-data lint format check-deploy \
        prod-up prod-up-build prod-down prod-restart prod-logs prod-ps prod-shell prod-migrate \
        prod-collectstatic prod-ngrok prod-ngrok-down vendor watch-css build-css

help:
	@echo "Dev:"
	@echo "  make up              Start dev containers"
	@echo "  make up-build        Start dev containers with image build"
	@echo "  make build           Build dev images"
	@echo "  make down            Stop and remove dev containers"
	@echo "  make restart         Restart dev containers"
	@echo "  make logs            Show dev logs (follow)"
	@echo "  make ps              Show running dev services"
	@echo "  make shell           Open shell in web container"
	@echo "  make ngrok           Expose the dev site over https, print the URL"
	@echo "  make ngrok-down      Close the dev tunnel"
	@echo "  make clone-dev-data  Copy database and uploads to a second checkout"
	@echo ""
	@echo "Prod:"
	@echo "  make prod-up         Start prod containers"
	@echo "  make prod-up-build   Start prod containers with image build"
	@echo "  make prod-down       Stop and remove prod containers"
	@echo "  make prod-restart    Restart prod containers"
	@echo "  make prod-logs       Show prod logs (follow)"
	@echo "  make prod-ps             Show running prod services"
	@echo "  make prod-shell          Open shell in prod web container"
	@echo "  make prod-migrate        Apply migrations against the prod database"
	@echo "  make prod-collectstatic  Upload static files to R2 (run once on deploy)"
	@echo "  make prod-ngrok          Expose the prod site over https, print the URL"
	@echo "  make prod-ngrok-down     Close the prod tunnel"
	@echo ""
	@echo "Frontend:"
	@echo "  make vendor          Install npm deps and copy vendor assets"
	@echo "  make watch-css       Rebuild styles on every change (runs on the host)"
	@echo "  make build-css       Build the styles once, minified"
	@echo ""
	@echo "Django:"
	@echo "  make migrate         Apply migrations"
	@echo "  make makemigrations  Create migrations"
	@echo "  make superuser       Create Django superuser"
	@echo "  make worker-logs     Show Celery worker logs"
	@echo ""
	@echo "Quality:"
	@echo "  make test            Run tests"
	@echo "  make build-test      Rebuild test image"
	@echo "  make lint            Check formatting and lint rules"
	@echo "  make format          Reformat the code"
	@echo "  make check-deploy    Run Django's production checklist"

up:
	$(DEV) up

up-build:
	$(DEV) up --build

build:
	$(DEV) build

down:
	$(DEV) down

# Restarts the processes; down + up would throw the containers away and build
# new ones, which is a different thing and much slower.
restart:
	$(DEV) restart

logs:
	$(DEV) logs -f

ps:
	$(DEV) ps

shell:
	$(DEV) exec web sh

migrate:
	$(DEV) run --rm web python app/manage.py migrate

makemigrations:
	$(DEV) run --rm web python app/manage.py makemigrations

superuser:
	$(DEV) run --rm web python app/manage.py createsuperuser

worker-logs:
	$(DEV) logs -f worker

# The public address is only reachable through the tunnel's own dashboard, so
# it is fished out of there rather than printed by the container.
ngrok:
	$(DEV_NGROK) up -d ngrok
	@sleep 4
	@echo "Dashboard: http://localhost:4040"
	@curl -s http://localhost:4040/api/tunnels | grep -o 'https://[^"]*ngrok[^"]*' | head -1

ngrok-down:
	$(DEV_NGROK) rm -sf ngrok

# Two checkouts that set PROJECT_NAME get separate databases; this fills the
# second one from the first instead of doing it by hand. Both stacks have to be
# up. Override FROM_PROJECT and TO_PROJECT to copy the other way.
clone-dev-data:
	docker compose -p $(FROM_PROJECT) -f docker-compose.dev.yml exec -T db \
		sh -c 'pg_dump -U $$POSTGRES_USER -c $$POSTGRES_DB' \
		| docker compose -p $(TO_PROJECT) -f docker-compose.dev.yml exec -T db \
		sh -c 'psql -q -U $$POSTGRES_USER $$POSTGRES_DB'
	docker run --rm \
		-v $(FROM_PROJECT)_media:/from -v $(TO_PROJECT)_media:/to \
		alpine sh -c 'cp -a /from/. /to/'

test:
	$(DEV_TEST) run --rm test

build-test:
	$(DEV_TEST) build test

# --no-deps: linting needs no database and no queue, only the image.
lint:
	$(DEV_TEST) run --rm --no-deps test sh -c 'ruff check . && ruff format --check .'

format:
	$(DEV_TEST) run --rm --no-deps test ruff format .

# Django's own audit of production settings. Reads the production settings, so
# it wants the same variables a real start does.
check-deploy:
	$(PROD) run --rm --no-deps web python app/manage.py check --deploy

vendor:
	npm install
	npm run copy:vendor

# On the host, not in a container: a watcher inside one never learns that a
# file changed, because change notifications do not cross the boundary between
# Windows and the Linux virtual machine docker runs in.
watch-css:
	npm run watch:css

build-css:
	npm run build:css

prod-up:
	$(PROD) up

prod-up-build:
	$(PROD) up --build

prod-down:
	$(PROD) down

prod-restart:
	$(PROD) restart

prod-logs:
	$(PROD) logs -f

prod-ps:
	$(PROD) ps

prod-shell:
	$(PROD) exec web sh

prod-migrate:
	$(PROD) run --rm web python app/manage.py migrate --noinput

prod-collectstatic:
	$(PROD) run --rm web python app/manage.py collectstatic --noinput

prod-ngrok:
	$(PROD_NGROK) up -d ngrok
	@sleep 4
	@echo "Dashboard: http://localhost:4040"
	@curl -s http://localhost:4040/api/tunnels | grep -o 'https://[^"]*ngrok[^"]*' | head -1

prod-ngrok-down:
	$(PROD_NGROK) rm -sf ngrok
