FROM python:3.9.16-bullseye
ADD . /app
WORKDIR /app
USER root
RUN pip install -r requirements.txt
CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]
