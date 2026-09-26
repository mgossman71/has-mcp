FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e .

# Copy config (will be used if HA_ALLOWED_ENTITIES env is not set)
COPY config.yaml .

# Run the MCP server with HTTP transport
EXPOSE 8765

CMD ["python", "-m", "homeassistant_mcp.server", "--http", "--port", "8765"]