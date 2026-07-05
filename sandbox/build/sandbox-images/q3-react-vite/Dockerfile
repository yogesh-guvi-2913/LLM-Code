# Sandbox image for question q3 (React + Vite Todo frontend).
# The toolbox binary is compiled separately and placed at ./toolbox before build
# (see scripts/build-image.sh). Deps are baked in — never installed at runtime.
FROM node:20-slim

WORKDIR /app

# Deps baked in (includes devDeps: vite + the test toolchain used by the harness).
COPY template/package.json ./
RUN npm install && npm cache clean --force

# Fixed scaffolding (not editable / not reset on claim).
COPY template/index.html ./index.html
COPY template/vite.config.cjs ./vite.config.cjs
COPY template/tsconfig.json ./tsconfig.json

# Candidate-editable starter code.
COPY template/src ./src

# Preserve clean starter for reset-on-claim.
RUN cp -r /app/src /template-src

# Toolbox control-plane binary (static, linux).
COPY toolbox /usr/local/bin/toolbox
RUN chmod +x /usr/local/bin/toolbox

# Scoring harness.
COPY harness /harness
RUN chmod +x /harness/run-tests.sh

# Run as non-root for a little defence in depth (node image ships a 'node' user).
RUN chown -R node:node /app /template-src
USER node

EXPOSE 3000 49983

CMD ["/usr/local/bin/toolbox"]
