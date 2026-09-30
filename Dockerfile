FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /app
COPY requirements.txt .
# Wheels are mounted from the builder, so no wheel archives remain in image layers.
RUN --mount=type=bind,from=builder,source=/wheels,target=/wheels \
    pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt
COPY nutrition.py data_analysis.py storage_config.py lambda_function.py upload_dataset.py ./
COPY data/All_Diets.csv data/All_Diets.csv
RUN mkdir -p output simulated_nosql && chown -R 1000:1000 /app
USER 1000:1000
CMD ["python", "data_analysis.py"]
