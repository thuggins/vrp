FROM python:3.9-slim-buster
RUN pip install pandas pyarrow
WORKDIR /opt/program
COPY . .
