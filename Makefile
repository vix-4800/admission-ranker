APP_NAME=udk_app
PYTHON=python3

run:
	$(PYTHON) main.py

freeze:
	pip freeze > requirements.txt

install-dev:
	pip install -r requirements-dev.txt

build:
	pyinstaller --noconfirm --onefile --paths . --name $(APP_NAME) main.py

clean:
	rm -rf build dist __pycache__ *.spec
	find . -type d -name "__pycache__" -exec rm -rf {} +

test:
	pytest -q

lint:
	isort .
	black .
