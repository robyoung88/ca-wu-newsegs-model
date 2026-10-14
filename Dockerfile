FROM continuumio/miniconda3:latest

# Install curl for Docker healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY conda_environment.yml requirements-pip.txt ./

RUN conda env create -f conda_environment.yml && \
    conda run -n ca-wu-newsegs-mod pip install -r requirements-pip.txt && \
    conda clean -afy

# Copy application source
COPY . .

# Create SQLite database directory for named volume target
RUN mkdir -p /var/lib/sqlite_data

EXPOSE 8050

# Ensure subsequent CMD runs within the Conda environment
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "ca-wu-newsegs-mod"]

# Default command (overridden by docker-compose for other services)
CMD ["python", "src/app.py"]
