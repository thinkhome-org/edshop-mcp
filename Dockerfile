FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home app
USER 10001
EXPOSE 8000
ENTRYPOINT ["edshop-mcp"]
CMD ["--transport", "http", "--host", "0.0.0.0"]
