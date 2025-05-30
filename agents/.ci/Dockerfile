FROM ubuntu:20.04

RUN apt-get update && \
    apt-get install -y \
    build-essential \
    wget \
    zlib1g-dev \
    libncurses5-dev \
    libgdbm-dev \
    libnss3-dev \
    libssl-dev \
    libreadline-dev \
    libffi-dev \
    libsqlite3-dev

RUN if ! /opt/python2.6/bin/python2.6 --version > /dev/null 2>&1; then \
      wget https://www.python.org/ftp/python/2.6.9/Python-2.6.9.tgz && \
      tar xzf Python-2.6.9.tgz && \
      # Instaling zlib
      cd Python-2.6.9/Modules && \
      cp Setup.dist Setup && \
      sed -i '/zlibmodule\.c/ s/^# *//' Setup && \
      cd .. && \
      ./configure --prefix=/opt/python2.6 && \
      make && \
      make install && \
      cd .. && \
      rm -rf Python-2.6.9 Python-2.6.9.tgz; \
    fi

ENV PATH='/opt/python2.6/bin:${PATH}'

CMD ["python2.6", "--version"]
