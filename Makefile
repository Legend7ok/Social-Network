DEV := docker compose -f docker-compose.dev.yml
PROD := docker compose -f docker-compose.prod.yml
DEV_TEST := $(DEV) --profile test

.PHONY: help up up-build build down restart logs ps shell migrate makemigrations test build-test superuser \
        worker-logs prod-up prod-up-build prod-down prod-restart prod-logs prod-ps vendor

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
	@echo ""
	@echo "Prod:"
	@echo "  make prod-up         Start prod containers"
	@echo "  make prod-up-build   Start prod containers with image build"
	@echo "  make prod-down       Stop and remove prod containers"
	@echo "  make prod-restart    Restart prod containers"
	@echo "  make prod-logs       Show prod logs (follow)"
	@echo "  make prod-ps         Show running prod services"
	@echo ""
	@echo "Frontend:"
	@echo "  make vendor          Install npm deps and copy vendor assets"
	@echo ""
	@echo "Django:"
	@echo "  make migrate         Apply migrations"
	@echo "  make makemigrations  Create migrations"
	@echo "  make superuser       Create Django superuser"
	@echo "  make test            Run tests"
	@echo "  make worker-logs     Show Celery worker logs"
	@echo "  make build-test      Rebuild test image"

up:
	$(DEV) up

up-build:
	$(DEV) up --build

build:
	$(DEV) build

down:
	$(DEV) down

restart: down up

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

test:
	$(DEV_TEST) run --rm test

build-test:
	$(DEV_TEST) build test

vendor:
	npm install
	npm run copy:vendor

prod-up:
	$(PROD) up

prod-up-build:
	$(PROD) up --build

prod-down:
	$(PROD) down

prod-restart: prod-down prod-up

prod-logs:
	$(PROD) logs -f

prod-ps:
	$(PROD) ps
