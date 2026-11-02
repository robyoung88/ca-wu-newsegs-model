FROM continuumio/miniconda3:latest

# Install curl for Docker healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY conda-environment.yml requirements-pip.txt requirements-docs.txt ./

RUN conda env create -f conda-environment.yml && \
    conda run -n ca-wu-newsegs-mod pip install -r requirements-pip.txt -r requirements-docs.txt && \
    conda clean -afy

# Copy application source
COPY . .

# Build the documentation served by the app at /documentation/.
# This is outside /app because docker-compose mounts the working copy over /app.
ENV DYNACONF_DOCS_PATH=/opt/newsegs-docs
RUN conda run -n ca-wu-newsegs-mod mkdocs build --site-dir /opt/newsegs-docs

# Create SQLite database directory for named volume target
RUN mkdir -p /var/lib/sqlite_data

EXPOSE 8050

# Ensure subsequent CMD runs within the Conda environment
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "ca-wu-newsegs-mod"]

# Default command (overridden by docker-compose for other services)
CMD ["python", "src/app.py"]
