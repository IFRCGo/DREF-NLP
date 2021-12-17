# *****************************
# Dockerfile for PARSE+TAG API
# *****************************


# *****************************
# Install Python & Java

# We need to use both Python & Java, because of tika
# There exist several methods

# Method 1, suggested by GA
# NB: apt-get is a Linux program, to play with it under Windows one can use WSL,
# but building docker in a Windows terminal also works ok since python:3.8-slim-buster image is based on Linux

FROM python:3.8-slim-buster
ENV DEBIAN_FRONTEND=noninteractive
RUN mkdir -p /usr/share/man/man1 /usr/share/man/man2
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-11-jre && apt-get clean
# Prints installed java version, just for checking
RUN java --version

# Method 2, using a custom docker that has Python & Java (older versions)
# FROM rappdw/docker-java-python:openjdk1.8.0_171-python3.6.6


# *****************************
# Rest of Dockerfile
 

# Should we use pip or pip3?
# It is not really critical here, but a good practice is to use 'python -m pip'
# see e.g. https://stackoverflow.com/questions/61664673/should-i-use-pip-or-pip3
# and upgrade pip first
RUN python -m pip install --upgrade pip

# Create working directory
#WORKDIR /app

# Install Python dependencies with pip & download a spacy model
COPY requirements.txt ./
COPY main.py ./ 
RUN python -m pip install -r requirements.txt --no-cache-dir --disable-pip-version-check
RUN python -m spacy download en_core_web_md

# Install two dref packages
COPY dref_parsing ./dref_parsing
COPY dref_tagging ./dref_tagging

RUN python -m pip install -e ./dref_parsing/ --no-cache-dir --disable-pip-version-check
RUN python -m pip install -e ./dref_tagging/ --no-cache-dir --disable-pip-version-check

# The EXPOSE line can probably be skipped:
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000","--workers", "1"]
#EXPOSE 5000
#CMD ["uvicorn", "dref_parsing.main:app", "--host", "0.0.0.0", "--port", "5000","--workers", "1"]

