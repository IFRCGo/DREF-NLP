FROM python:3.7

WORKDIR /app

RUN pip install fastapi uvicorn spacy

#RUN apt update && apt upgrade -y

#RUN apt install -y -q build-essential python3-pip python3-dev
#RUN pip3 install -U pip setuptools wheel
#RUN pip3 install gunicorn uvloop httptools

COPY requirements.txt ./requirements.txt

RUN pip3 install -r ./requirements.txt

RUN python -m spacy download en_core_web_md

COPY dref_tagging ./dref_tagging
COPY setup.cfg setup.py ./
RUN python -m pip install -e . --no-cache-dir --disable-pip-version-check

EXPOSE 8000


CMD ["uvicorn", "dref_tagging.main:app", "--host", "0.0.0.0", "--port", "8000","--workers", "1"]