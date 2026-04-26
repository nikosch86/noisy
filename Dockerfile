FROM python:3.12-alpine
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml README.md noisy.py ./
COPY config.json ./
RUN pip install --no-cache-dir --no-deps .
ENTRYPOINT ["noisy"]
CMD ["--config", "config.json"]
