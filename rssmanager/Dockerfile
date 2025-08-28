FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY run.sh main.py ./
RUN chmod +x run.sh

COPY ui/ ui/

CMD [ "./run.sh" ]
