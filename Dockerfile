FROM python:3.9.16-bullseye
RUN groupadd -r flask && useradd --no-log-init -r -g flask flask
USER flask
ADD . /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]
