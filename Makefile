.PHONY: install backend frontend dev docker-dev stop test

install:
	cd backend && pip3 install --break-system-packages -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && python3 -m uvicorn main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

dev:
	@trap 'kill 0' EXIT; \
	$(MAKE) backend & \
	$(MAKE) frontend & \
	for pid in $$(jobs -p); do wait $$pid || exit $$?; done

docker-dev:
	docker compose up --build

test:
	cd backend && python3 -m pytest tests/ -v

stop:
	@lsof -ti:8000 | xargs kill 2>/dev/null; true
	@lsof -ti:5173 | xargs kill 2>/dev/null; true
	@echo "Stopped"
