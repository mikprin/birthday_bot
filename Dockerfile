FROM python:3.9-slim

LABEL name="Birthday bot container" \
      version="1.0" \
      maintainer="Mikhail Solovyanov <" \
      description="This is the Dockerfile for the Birthday bot container"

WORKDIR /

RUN apt-get update && apt-get install -y \
    build-essential \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/* &&\
    apt-get clean
# Copy the requirements.txt file to the container before copying the rest of the code
COPY requirements.txt /app

RUN pip3 install -r requirements.txt

COPY birthday_bot /birthday_bot

CMD ["python3", "birthday_bot/bot.py"]