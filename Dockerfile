FROM node:22-alpine

LABEL org.opencontainers.image.description="Prism static mock server for the claude-api-contract OpenAPI contract"

ENV PRISM_PORT=4010

# Install Prism globally — pinned for reproducibility
RUN npm install -g @stoplight/prism-cli@5.12.0 && npm cache clean --force

WORKDIR /app

# Only the canonical bundled contract is needed at runtime;
# Prism is installed globally (not from node_modules)
COPY openapi.yml .

USER node

# EXPOSE reflects the default PRISM_PORT (4010). If you override PRISM_PORT at runtime,
# also update -p accordingly: docker run -e PRISM_PORT=5000 -p 5000:5000 <image>
EXPOSE 4010

# -h 0.0.0.0 is CRITICAL: without it Prism binds to loopback only
# and the mock is unreachable from outside the container.
# -m false (single-process) is REQUIRED inside Docker: prism 5's default
# multiprocess mode reads cluster.isPrimary, which is undefined in a container
# and crashes at startup with "Cannot read properties of undefined (reading 'isPrimary')".
# Local `npm run mock` is unaffected (it runs Prism directly via Node, not multiprocess).
CMD ["sh", "-c", "prism mock openapi.yml -h 0.0.0.0 -p ${PRISM_PORT} -m false"]
