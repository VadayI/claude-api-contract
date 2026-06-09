FROM node:22-alpine

LABEL org.opencontainers.image.description="Prism static mock server for the claude-api-contract OpenAPI contract"

ENV PRISM_PORT=4010

# Install Prism globally — pinned for reproducibility
RUN npm install -g @stoplight/prism-cli@5.12.0

WORKDIR /app

# Only the canonical bundled contract is needed at runtime;
# Prism is installed globally (not from node_modules)
COPY openapi.yml .

EXPOSE 4010

# -h 0.0.0.0 is CRITICAL: without it Prism binds to loopback only
# and the mock is unreachable from outside the container
CMD ["sh", "-c", "prism mock openapi.yml -h 0.0.0.0 -p ${PRISM_PORT}"]
