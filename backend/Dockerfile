# Image for AgentCore Runtime (arm64). Built by CDK from this folder.
FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.19

COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --group runtime --no-emit-project -o requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

COPY src ./src
ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1

RUN useradd -m -u 1000 agent
USER agent
EXPOSE 8080

# opentelemetry-instrument sends traces to AgentCore Observability (CloudWatch).
CMD ["opentelemetry-instrument", "python", "-m", "onboarding_demo.agent.app"]
