SHELL := /bin/bash
.PHONY: install backend frontend dev docker-dev stop test test-coverage full-test mongo

NVM := . $(HOME)/.config/nvm/nvm.sh &&

install:
	cd backend && pip3 install --break-system-packages -r requirements.txt
	$(NVM) cd frontend && npm install

mongo:
	@if docker ps --format '{{.Names}}' | grep -q '^vinyl-recko-mongo$$'; then \
		echo "MongoDB already running"; \
	else \
		echo "Starting MongoDB..."; \
		docker start vinyl-recko-mongo 2>/dev/null || \
		docker run -d --name vinyl-recko-mongo -p 27017:27017 -v vinyl_recko_mongo_data:/data/db mongo:7 > /dev/null; \
	fi

backend:
	cd backend && DEV_MODE=true python3 -m uvicorn main:app --reload --port 8000

frontend:
	$(NVM) cd frontend && npm run dev

dev:
	@$(MAKE) mongo
	@trap 'kill 0' EXIT; \
	$(MAKE) backend & \
	$(MAKE) frontend & \
	for pid in $$(jobs -p); do wait $$pid || exit $$?; done

docker-dev:
	docker compose up --build

test:
	cd backend && python3 -m pytest tests/ -v

test-coverage:
	cd backend && python3 -m pytest tests/ -v --cov=services --cov=repository --cov=routes --cov-report=term-missing --cov-report=json --cov-fail-under=80
	cd backend && python3 scripts/check_coverage.py --min 80 --report coverage.json

full-test:
	$(MAKE) test-coverage

stop:
	@lsof -ti:8000 | xargs kill 2>/dev/null; true
	@lsof -ti:5173 | xargs kill 2>/dev/null; true
	@docker stop vinyl-recko-mongo 2>/dev/null; true
	@echo "Stopped"
