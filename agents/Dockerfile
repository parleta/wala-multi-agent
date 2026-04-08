FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
COPY vendor/aztmnative ./vendor/aztmnative
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "agent_server.py"]
