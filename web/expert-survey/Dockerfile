FROM python:3.12-alpine
WORKDIR /app
COPY survey_server.py ./
COPY site ./site
ENV SURVEY_SITE=/app/site SURVEY_DATA=/data SURVEY_HOST=0.0.0.0 SURVEY_PORT=8080 PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "survey_server.py"]
