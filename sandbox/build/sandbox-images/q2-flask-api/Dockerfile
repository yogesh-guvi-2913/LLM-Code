# Sandbox image for question q2 (Flask Todo API).
# Same contract as q1: toolbox baked in, deps baked in, /app/src is the only
# candidate-editable path. The toolbox runs DEV_CMD ("python server.py").
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Deps baked in.
COPY template/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Fixed scaffolding + candidate-editable starter code.
COPY template/server.py ./server.py
COPY template/src ./src

# Preserve clean starter for reset-on-claim.
RUN cp -r /app/src /template-src

# Toolbox control-plane binary (static, linux).
COPY toolbox /usr/local/bin/toolbox
RUN chmod +x /usr/local/bin/toolbox

# Scoring harness.
COPY harness /harness
RUN chmod +x /harness/run-tests.sh

# Non-root for defence in depth.
RUN useradd -m -u 1000 app && chown -R app:app /app /template-src
USER app

EXPOSE 3000 49983

CMD ["/usr/local/bin/toolbox"]
