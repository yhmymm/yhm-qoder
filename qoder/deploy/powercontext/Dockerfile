FROM python:3.12-slim

RUN pip install --no-cache-dir "powercontext[cli,server]==1.4.1"

RUN mkdir -p /data

EXPOSE 8000

CMD ["powercontext", "server", "run", "--host", "0.0.0.0", "--port", "8000", "--role", "all", "--data-dir", "/data"]
