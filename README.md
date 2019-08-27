# LibreSSL automirror

A script to keep an up-to-date mirror of LibreSSL releases over git.

It is used to automatically update [EtchDroid/LibreSSL](https://github.com/EtchDroid/LibreSSL)

## Usage

- Create a virtualenv and install the dependencies

```
source venv/bin/activate

export LSSLM_GIT_REPO=/path/to/LibreSSL/repo
python libressl_automirror.py
```
