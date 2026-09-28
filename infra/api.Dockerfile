FROM python:3.13-slim
WORKDIR /srv
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend /srv/backend
COPY frontend /srv/frontend
COPY docs /srv/docs
ENV PYTHONPATH=/srv/backend TRAFFICTWIN_ROOT=/srv
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
