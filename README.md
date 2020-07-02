# LibreSSL automirror

![.github/workflows/automirror.yml](https://github.com/EtchDroid/libressl-automirror/workflows/.github/workflows/automirror.yml/badge.svg?branch=master)

A script to keep an up-to-date mirror of LibreSSL releases over git.

It is used to automatically update [EtchDroid/LibreSSL](https://github.com/EtchDroid/LibreSSL)

Releases are taken from the official mirrors:
https://github.com/EtchDroid/libressl-automirror/blob/master/libressl_automirror.py#L18-L29

## Usage

- Create a virtualenv and install the dependencies

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export LSSLM_GIT_REPO=/path/to/LibreSSL/repo
python libressl_automirror.py
```
