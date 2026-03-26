# This Dockerfile initiates a working environment that can be used to run deploy script

FROM python:3.11-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf \
    automake \
    build-essential \
    cmake \
    gfortran \
    git \
    libhdf5-dev \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /tmp/deploy_env
ENV PATH="/tmp/deploy_env/bin:$PATH"
ENV VIRTUAL_ENV="/tmp/deploy_env"
ENV UV_PROJECT_ENVIRONMENT="/tmp/deploy_env"

WORKDIR /work

COPY ./src ./src
COPY ./uv.lock ./uv.lock
COPY ./pyproject.toml ./pyproject.toml
# Poetry requires readme to exist
RUN touch ./README.md

RUN mkdir -p /root/.ssh/
RUN ssh-keyscan github.com >> /root/.ssh/known_hosts
RUN chmod 0700 /root/.ssh

RUN pip install --upgrade pip
RUN pip install uv
RUN uv sync

ENTRYPOINT ["/bin/bash","-c", "source /tmp/deploy_env/bin/activate; bash"]
