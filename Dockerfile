# CLUTCHIQ dashboard container. Build:  docker build -t clutchiq .   Run:  docker run -p 8501:8501 clutchiq
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 clutchiq
COPY --chown=clutchiq:clutchiq . .
USER clutchiq
EXPOSE 8501
# Inside a container the app must listen on all interfaces; protect it with the password (see SECURITY.md).
CMD ["streamlit", "run", "dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
