FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py index.html dispatch.html style.css robots.txt ./
RUN groupadd -g 10001 ctf && useradd -m -u 10001 -g 10001 ctf
USER 10001:10001
EXPOSE 5000
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]
