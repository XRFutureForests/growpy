FROM quay.io/jupyter/base-notebook:latest

USER root
RUN apt update && \
    apt install --no-install-recommends --yes \
      build-essential \
      git \
      libgl1 \
      libegl1 \
      libxkbcommon0 && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*
USER ${NB_USER}

# Pull in the Conda environment first to avoid unnecessary rebuilds
COPY --chown=${NB_UID} environment.yml ${HOME}/

# Install packages into the conda environment
RUN mamba env update -n base --file ${HOME}/environment.yml && \
    mamba clean -a -q -y && \
    rm ${HOME}/environment.yml

# Copy the rest of the files
COPY --chown=${NB_UID} . ${HOME}/growpy

# Install the growpy package
RUN conda run -n base python -m pip install -v ${HOME}/growpy

# Set PYTHONPATH for the_grove_22 modules
ENV PYTHONPATH="${HOME}/growpy/src:${HOME}/growpy/src/the_grove_22/modules"
