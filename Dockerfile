FROM python:3.12-alpine
WORKDIR /app
COPY pyproject.toml README.md noisy.py ./
COPY config.json ./
RUN pip install --no-cache-dir .
ENTRYPOINT ["noisy"]
CMD ["--config", "config.json"]
