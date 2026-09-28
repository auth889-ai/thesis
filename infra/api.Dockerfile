FROM python:3.13-slim
WORKDIR /srv
COPY requirements.txt packages/traffictwin/pyproject.toml ./
COPY packages/traffictwin /srv/packages/traffictwin
COPY apps/api /srv/apps/api
COPY apps/web /srv/apps/web
COPY docs /srv/docs
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -e packages/traffictwin
ENV PYTHONPATH=/srv/apps/api TRAFFICTWIN_ROOT=/srv
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "apps/api", "--host", "0.0.0.0", "--port", "8000"]
