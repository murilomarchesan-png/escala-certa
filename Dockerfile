FROM python:3.12-slim
WORKDIR /app
COPY apps apps
ENV ESCALA_BIND=0.0.0.0
USER 65534:65534
CMD ["python", "apps/api/server.py"]
