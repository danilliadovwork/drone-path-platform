# ==============================================================================
# Variables
# ==============================================================================
# Define the compose files
COMPOSE_CPU = docker compose -f docker-compose.yml
COMPOSE_GPU = docker compose -f docker-compose.gpu.yml

# ==============================================================================
# Default / Help
# ==============================================================================
.PHONY: help
help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "CPU Commands:"
	@echo "  up             Start the CPU stack in the background"
	@echo "  build          Build the CPU stack images"
	@echo "  down           Stop and remove the CPU stack"
	@echo ""
	@echo "GPU Commands:"
	@echo "  up-gpu         Start the GPU stack in the background"
	@echo "  build-gpu      Build the GPU stack images"
	@echo "  down-gpu       Stop and remove the GPU stack"
	@echo ""
	@echo "Utility Commands:"
	@echo "  logs           Tail logs for all services"
	@echo "  logs-worker    Tail logs specifically for the Celery worker"
	@echo "  logs-backend   Tail logs specifically for the FastAPI backend"
	@echo "  clean          Stop containers and remove volumes (WIPES DATABASE)"
	@echo ""
	@echo "Development Shortcuts:"
	@echo "  shell-backend  Open a bash shell inside the backend container"
	@echo "  shell-worker   Open a bash shell inside the worker container"
	@echo "  db-shell       Open psql directly in the database container"
	@echo "  migrate        Run Alembic database migrations"

# ==============================================================================
# CPU Targets
# ==============================================================================
.PHONY: up build down

up: ## Start the standard CPU stack
	$(COMPOSE_CPU) up -d

build: ## Build the CPU stack
	$(COMPOSE_CPU) build

down: ## Stop the CPU stack
	$(COMPOSE_CPU) down

# ==============================================================================
# GPU Targets
# ==============================================================================
.PHONY: up-gpu build-gpu down-gpu

up-gpu: ## Start the GPU accelerated stack
	$(COMPOSE_GPU) up -d

build-gpu: ## Build the GPU stack
	$(COMPOSE_GPU) build

down-gpu: ## Stop the GPU stack
	$(COMPOSE_GPU) down

# ==============================================================================
# Utilities & Logs
# ==============================================================================
.PHONY: logs logs-worker logs-backend clean

logs: ## Tail all logs
	$(COMPOSE_CPU) logs -f

logs-worker: ## Tail Celery worker logs
	$(COMPOSE_CPU) logs -f worker

logs-backend: ## Tail FastAPI backend logs
	$(COMPOSE_CPU) logs -f backend

clean: ## Remove containers, networks, and persistent volumes (WARNING: Data loss)
	$(COMPOSE_CPU) down -v
	$(COMPOSE_GPU) down -v

# ==============================================================================
# Shell & Development
# ==============================================================================
.PHONY: shell-backend shell-worker db-shell migrate makemigrations

shell-backend: ## Access the backend container
	$(COMPOSE_CPU) exec backend bash

shell-worker: ## Access the worker container
	$(COMPOSE_CPU) exec worker bash

db-shell: ## Access the PostgreSQL database
	$(COMPOSE_CPU) exec db psql -U user -d drone_db

migrate: ## Run Alembic migrations
	$(COMPOSE_CPU) exec backend alembic upgrade head

# Usage: make makemigrations m="Added flight path column"
makemigrations: ## Autogenerate a new Alembic migration
	$(COMPOSE_CPU) exec backend alembic revision --autogenerate -m "$(m)"