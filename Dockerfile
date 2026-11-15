FROM python:3.12-slim

# uv comes from its own image; this pin matches the version the lock file was written with.
COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /usr/local/bin/uv

# UV_NO_DEV keeps the test and notebook tooling (Jupyter, pyright and so on) out of
# the image. UV_NO_CACHE stops uv from keeping a second copy of every wheel.
ENV UV_LINK_MODE=copy \
    UV_FROZEN=1 \
    UV_NO_DEV=1 \
    UV_NO_CACHE=1

# Create the user first and install as that user, so no later chown has to
# copy the whole environment into a new layer.
RUN useradd --create-home appuser && mkdir /app && chown appuser /app
USER appuser
WORKDIR /app

# Install the dependencies before copying the source, so this layer is rebuilt
# only when pyproject.toml or uv.lock change. README.md is needed because
# pyproject.toml names it as the package readme.
COPY --chown=appuser pyproject.toml uv.lock README.md ./
RUN uv sync --group app --no-install-project

COPY --chown=appuser src ./src
COPY --chown=appuser configs ./configs
COPY --chown=appuser data ./data
COPY --chown=appuser app ./app
RUN uv sync --group app

EXPOSE 8501
CMD ["uv", "run", "streamlit", "run", "app/streamlit_app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--browser.gatherUsageStats=false"]
