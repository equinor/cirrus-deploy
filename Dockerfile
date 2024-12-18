# This Dockerfile initiates a working environment that can be used to run deploy script
# After 

FROM rockylinux:8

RUN dnf -y groupinstall "Development Tools"
RUN dnf -y install which
RUN dnf -y install python3.11
RUN dnf -y install gcc-gfortran
RUN dnf -y install git

RUN python3.11 -m venv /tmp/deploy_env

WORKDIR /work

COPY ./src ./src
COPY ./poetry.lock ./poetry.lock
COPY ./pyproject.toml ./pyproject.toml
COPY ./config.yaml ./config.yaml
# Poetry requires readme to exist
RUN touch ./README.md

RUN mkdir -p /root/.ssh/
RUN ssh-keyscan github.com >> /root/.ssh/known_hosts
RUN chmod 0700 /root/.ssh

RUN /tmp/deploy_env/bin/pip install .
RUN --mount=type=ssh /tmp/deploy_env/bin/deploy build
RUN /tmp/deploy_env/bin/deploy links

ENTRYPOINT ["/bin/bash","-c", "source /tmp/deploy_env/bin/activate; bash"]
