FROM python:3.12-slim AS builder

#RUN sed -i 's/http:\/\/archive.ubuntu.com/http:\/\/mirrors.tuna.tsinghua.edu.cn\/ubuntu/g' /etc/apt/sources.list
# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ musl-dev curl libffi-dev gfortran libopenblas-dev \
    poppler-utils \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

# Add Rust to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Create the /app/py directory
RUN mkdir -p /app/py
WORKDIR /app/py
COPY pyproject.toml ./

RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set install.trusted-host mirrors.aliyun.com

RUN pip install -e ".[core]" && \
    pip install gunicorn uvicorn pydantic transformers anytree llama_index langchain langchain_community langchain_openai BCEmbedding torch sentence_transformers elasticsearch langchain_elasticsearch json_repair xinference lark peft langchain_huggingface jieba -i https://mirrors.aliyun.com/pypi/simple/

# Optionally, if you want gunicorn and uvicorn explicitly installed, you can
# either list them under [project] in `pyproject.toml` or install them here:
RUN pip install --no-cache-dir gunicorn uvicorn

# Create the final image
FROM python:3.12-slim

# Minimal runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl poppler-utils \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy the built environment from builder to final image
# (If you want a fully self-contained environment, copy /usr/local)
COPY --from=builder /usr/local /usr/local

WORKDIR /app

# Copy the rest of your source code
COPY . /app

# Expose environment variables and port
ARG R2R_PORT=8000 R2R_HOST=0.0.0.0
ENV R2R_PORT=$R2R_PORT R2R_HOST=$R2R_HOST
ENV R2R_POSTGRES_USER=langchain
ENV R2R_POSTGRES_DBNAME=postgres
ENV R2R_POSTGRES_PASSWORD=langchain
ENV R2R_POSTGRES_HOST=10.1.150.105
ENV R2R_POSTGRES_PORT=6000
ENV R2R_PROJECT_NAME=jq_new_project


EXPOSE $R2R_PORT

# Launch the app
CMD ["sh", "-c", "uvicorn core.main.app_entry:app --host $R2R_HOST --port $R2R_PORT"]
