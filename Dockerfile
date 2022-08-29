FROM python:3

WORKDIR /usr/src/mail-reader

COPY python-requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r python-requirements.txt

COPY . .

CMD ["python3", "src/main.py"]