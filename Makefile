DEV := docker compose -f docker-compose.dev.yml
PROD := docker compose -f docker-compose.prod.yml
DEV_TEST := $(DEV) --profile test
DEV_NGROK := $(DEV) --profile ngrok
PROD_NGROK := $(PROD) --profile ngrok

# Which checkout to copy development data between; see dev-clone-data.
FROM_PROJECT ?= social-network
TO_PROJECT ?= social-network-w2

.DEFAULT_GOAL := help

# Naming: <env>-<action>. A bare env starts it, -build only builds, -build-up
# does both. The help below is generated from the ## comments, so it cannot
# drift away from the targets themselves.
help: ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} \
		/^##@/ { printf "\n%s\n", substr($$0, 5); next } \
		/^[a-zA-Z0-9_-]+:.*?## / { printf "  %-22s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

##@ Dev
dev: ## Start the dev stack
	$(DEV) up

dev-build: ## Build the dev images
	$(DEV) build

dev-build-up: ## Build the dev images, then start
	$(DEV) up --build

dev-down: ## Stop and remove the dev containers
	$(DEV) down

# Restarts the processes; down + up would throw the containers away and build
# new ones, which is a different thing and much slower.
dev-restart: ## Restart the running dev containers
	$(DEV) restart

dev-logs: ## Follow the dev logs
	$(DEV) logs -f

dev-worker-logs: ## Follow the dev Celery worker logs
	$(DEV) logs -f worker

dev-ps: ## Show the dev services
	$(DEV) ps

dev-shell: ## Open a shell in the dev web container
	$(DEV) exec web sh

dev-migrate: ## Apply migrations (they also run on every start)
	$(DEV) run --rm web python app/manage.py migrate

dev-makemigrations: ## Create new migrations
	$(DEV) run --rm web python app/manage.py makemigrations

dev-superuser: ## Create a Django superuser in dev
	$(DEV) run --rm web python app/manage.py createsuperuser

# The public address is only reachable through the tunnel's own dashboard, so
# it is fished out of there rather than printed by the container.
dev-ngrok: ## Expose the dev site over https, print the address
	$(DEV_NGROK) up -d ngrok
	@sleep 4
	@echo "Dashboard: http://localhost:4040"
	@curl -s http://localhost:4040/api/tunnels | grep -o 'https://[^"]*ngrok[^"]*' | head -1

dev-ngrok-down: ## Close the dev tunnel
	$(DEV_NGROK) rm -sf ngrok

# Two checkouts that set PROJECT_NAME get separate databases; this fills the
# second one from the first instead of doing it by hand. Both stacks have to be
# up. Override FROM_PROJECT and TO_PROJECT to copy the other way.
dev-clone-data: ## Copy database and uploads to a second checkout
	docker compose -p $(FROM_PROJECT) -f docker-compose.dev.yml exec -T db \
		sh -c 'pg_dump -U $$POSTGRES_USER -c $$POSTGRES_DB' \
		| docker compose -p $(TO_PROJECT) -f docker-compose.dev.yml exec -T db \
		sh -c 'psql -q -U $$POSTGRES_USER $$POSTGRES_DB'
	docker run --rm \
		-v $(FROM_PROJECT)_media:/from -v $(TO_PROJECT)_media:/to \
		alpine sh -c 'cp -a /from/. /to/'

##@ Prod
prod: ## Start the prod stack in the background
	$(PROD) up -d

prod-build: ## Build the prod images without touching what is running
	$(PROD) build

prod-build-up: ## Build the prod images, then start in the background
	$(PROD) up -d --build

# The whole deploy in one command, in the order the steps depend on each other.
#
# Static files go up from the freshly built image before anything starts, not
# after: they are served from the bucket, and the pages of the new release name
# them by the hash of their contents. A site started ahead of that upload would
# be asking for files nobody has put there yet.
#
# nginx is restarted last: it looks up the web container's address once, at its
# own start, and a rebuilt web container may come back on a different one -
# after which nginx answers 502 until it is restarted. See nginx/nginx.conf.
prod-deploy: ## Build, upload the static files, start and restart nginx
	$(PROD) build
	$(PROD) run --rm --no-deps web python app/manage.py collectstatic --noinput --ignore=input.css
	$(PROD) up -d
	$(PROD) restart nginx
	$(PROD) ps

prod-down: ## Stop and remove the prod containers
	$(PROD) down

prod-restart: ## Restart the running prod containers
	$(PROD) restart

prod-logs: ## Follow the prod logs
	$(PROD) logs -f

prod-ps: ## Show the prod services
	$(PROD) ps

prod-shell: ## Open a shell in the prod web container
	$(PROD) exec web sh

prod-migrate: ## Apply migrations against the prod database
	$(PROD) run --rm web python app/manage.py migrate --noinput

prod-superuser: ## Create a Django superuser in prod
	$(PROD) run --rm web python app/manage.py createsuperuser

# input.css is the source Tailwind builds from, never served. It is skipped
# because its font paths are written relative to the built file in css/dist,
# and the storage that rewrites those paths would look for them one directory
# too high and refuse to collect anything at all.
prod-collectstatic: ## Upload the static files to R2 (run once on deploy)
	$(PROD) run --rm web python app/manage.py collectstatic --noinput --ignore=input.css

prod-ngrok: ## Expose the prod site over https, print the address
	$(PROD_NGROK) up -d ngrok
	@sleep 4
	@echo "Dashboard: http://localhost:4040"
	@curl -s http://localhost:4040/api/tunnels | grep -o 'https://[^"]*ngrok[^"]*' | head -1

prod-ngrok-down: ## Close the prod tunnel
	$(PROD_NGROK) rm -sf ngrok

##@ Frontend
vendor: ## Install npm deps and copy the vendor assets
	npm install
	npm run copy:vendor

# On the host, not in a container: a watcher inside one never learns that a
# file changed, because change notifications do not cross the boundary between
# Windows and the Linux virtual machine docker runs in.
watch-css: ## Rebuild the styles on every change (runs on the host)
	npm run watch:css

build-css: ## Build the styles once, minified
	npm run build:css

##@ Tests
test: ## Run the test suite
	$(DEV_TEST) run --rm test

build-test: ## Rebuild the test image
	$(DEV_TEST) build test

check-migrations: ## Check that the models match the migrations
	$(DEV_TEST) run --rm test python app/manage.py makemigrations --check --dry-run

##@ Lint
# --no-deps: linting needs no database and no queue, only the image.
lint: ## Check formatting and lint rules
	$(DEV_TEST) run --rm --no-deps test sh -c 'ruff check . && ruff format --check .'

format: ## Reformat the code in place
	$(DEV_TEST) run --rm --no-deps test ruff format .

# Django's own audit of production settings. Reads the production settings, so
# it wants the same variables a real start does.
check-deploy: ## Run Django's production checklist
	$(PROD) run --rm --no-deps web python app/manage.py check --deploy

.PHONY: help \
        dev dev-build dev-build-up dev-down dev-restart dev-logs dev-worker-logs dev-ps dev-shell \
        dev-migrate dev-makemigrations dev-superuser dev-ngrok dev-ngrok-down dev-clone-data \
        prod prod-build prod-build-up prod-deploy prod-down prod-restart prod-logs prod-ps \
        prod-shell prod-migrate prod-superuser prod-collectstatic prod-ngrok prod-ngrok-down \
        vendor watch-css build-css \
        test build-test check-migrations lint format check-deploy
