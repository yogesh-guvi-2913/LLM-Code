# Define variables
DOCKER_COMPOSE_STAG=docker compose -f "deployment/stagging/docker-compose-stag.yml"
DOCKER_COMPOSE_PROD=docker compose -f docker-compose-prod.yml
DOCKER_COMPOSE_LOCAL=docker compose -f "deployment/development/docker-compose.yml"

# LIVE Commands
.PHONY: stop
stop:
	sudo $(DOCKER_COMPOSE_PROD) down

.PHONY: live
live:
	sudo $(DOCKER_COMPOSE_PROD) up -d --build


# STAGING Commands
.PHONY: stop-stag
stop-stag:
	sudo $(DOCKER_COMPOSE_STAG) down

.PHONY: live-stag
live-stag:
	sudo $(DOCKER_COMPOSE_STAG) up -d --build


# LOCAL Commands
.PHONY: stop-local
stop-local:
	$(DOCKER_COMPOSE_LOCAL) down

.PHONY: start-local
start-local:
	$(DOCKER_COMPOSE_LOCAL) up --build

.PHONY: connect-local-frontend
connect-local-frontend:
	docker exec -it hackathon-local-frontend-container sh

.PHONY: connect-local-backend
connect-local-backend:
	docker exec -it hackathon-local-backend-container sh

.PHONY: log-local-backend
log-local-backend:
	docker logs -f --tail 100 hackathon-local-backend-container

.PHONY: log-local-frontend
log-local-frontend:
	docker logs -f --tail 100 hackathon-local-frontend-container

## Installation commands
# pip install <package_name> && pip freeze > requirements.txt

# Check backup script logs in /var/backup/cron_log_file.log (Crontab configured to run every day at 2am)
.PHONY: backup-mongo
backup-mongo:
	export HP_BASE_ENV_PATH="/home/ubuntu/hackathon-platform/" && . /home/ubuntu/hackathon-platform/venv/bin/activate && python /home/ubuntu/hackathon-platform/mongo_backup.py >> /var/backup/cron_log_file.log 2>&1
