FROM python:3.4-alpine
ADD . /app
WORKDIR /app
USER root
RUN pip install -r requirements.txt
CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]
