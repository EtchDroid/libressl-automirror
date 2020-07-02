#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import ftplib
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from ftplib import FTP, FTP_TLS
from typing import Mapping, Optional, Generator, Union, Dict

import git
import packaging
from packaging.version import Version

LIBRESSL_FTP_MIRRORS = [
    {'host': 'mirror.internode.on.net', 'path': '/pub/OpenBSD/LibreSSL/', 'tls': False},
    {'host': 'mirror.csclub.uwaterloo.ca', 'path': '/pub/OpenBSD/LibreSSL/', 'tls': False},
    {'host': 'ftp2.fr.openbsd.org', 'path': '/pub/OpenBSD/LibreSSL/', 'tls': False},
    {'host': 'ftp.fsn.hu', 'path': '/pub/OpenBSD/LibreSSL/', 'tls': False},
    {'host': 'ftp.heanet.ie', 'path': '/pub/OpenBSD/LibreSSL/', 'tls': False},
    {'host': 'ftp.riken.jp', 'path': '/pub/OpenBSD/LibreSSL/', 'tls': False},
    {'host': 'ftp.bit.nl', 'path': '/pub/OpenBSD/LibreSSL/', 'tls': False},
    {'host': 'ftp.man.poznan.pl', 'path': '/pub/OpenBSD/LibreSSL/', 'tls': True},
    {'host': 'mirror.bytemark.co.uk', 'path': '/pub/OpenBSD/LibreSSL/', 'tls': False},
    {'host': 'ftp5.usa.openbsd.org', 'path': '/pub/OpenBSD/LibreSSL/', 'tls': False}
]

PKGNAME_RE = re.compile(r'libressl-(?P<version>(?:\d+.)+\d+).tar.gz')
GIT_TAG_RE = re.compile(r'v(?P<version>(?:\d+.)+\d+)')

_cfg = None


def get_config_env() -> Mapping[str, str]:
    global _cfg

    if not _cfg:
        _cfg = {}

        for key, value in os.environ.items():
            if key.startswith("LSSLM_"):
                _cfg[key[len("LSSLM_"):]] = value

    return _cfg


def get_use_tls() -> bool:
    cfg = get_config_env()
    return cfg.get("TLS_ONLY", "0") == "1"


def get_git_latest_version() -> Version:
    cfg = get_config_env()

    repo = git.Repo(cfg["GIT_REPO"])

    return max(
        map(
            lambda tag: packaging.version.parse(
                GIT_TAG_RE.search(tag.name).groupdict()["version"]
            ),
            repo.tags
        )
    )


def get_package_version(filename: str) -> Optional[Version]:
    match = PKGNAME_RE.search(filename)

    if not match:
        return

    return packaging.version.parse(match.groupdict()["version"])


def find_versions_above(mirror: Dict[str, str], target_version: Version) -> Generator[
    Mapping[str, Union[str, Version]], None, None]:
    print("Using mirror:", mirror['host'])
    tls = get_use_tls()

    if tls:
        ftp = FTP_TLS(mirror['host'])
    else:
        ftp = FTP(mirror['host'])

    ftp.login(user=mirror.get('user', None), passwd=mirror.get('passwd', ''), acct=mirror.get('acct', ''))
    ftp.cwd(mirror['path'])

    for filename, attrs in sorted(ftp.mlsd(), key=lambda tup: tup[0]):
        if not attrs["type"] == "file":
            continue
        if not filename.endswith(".tar.gz"):
            continue

        pkgver = get_package_version(filename)

        if not pkgver:
            continue

        if pkgver > target_version:
            fileinfo = mirror.copy()
            fileinfo["filename"] = filename
            fileinfo["version"] = pkgver
            fileinfo["tls"] = tls
            yield fileinfo


def clear_git_repo():
    cfg = get_config_env()
    repo = cfg["GIT_REPO"]

    for item in os.listdir(repo):
        if item == ".git":
            continue

        path = os.path.join(repo, item)
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.unlink(path)

def download_package_to_repo(fileinfo: Mapping[str, Union[str, Version]]):
    cfg = get_config_env()
    repo_dir = cfg["GIT_REPO"]
    repo = git.Repo(repo_dir)
    filename = fileinfo['filename']
    proto = "ftps" if fileinfo['tls'] else 'ftp'
    tmpfile = os.path.join(tempfile.gettempdir(), filename)

    try:
        wget = subprocess.Popen(
            ["wget", "-O", tmpfile, f"{proto}://{fileinfo['host']}/{fileinfo['path']}/{filename}"])
        if wget.wait() != 0:
            raise RuntimeError("wget exited with non-zero status code {}".format(wget.poll()))

        wget = subprocess.Popen(
            ["wget", "-O", f"{tmpfile}.asc", f"{proto}://{fileinfo['host']}/{fileinfo['path']}/{filename}.asc"])
        if wget.wait() != 0:
            raise RuntimeError("wget exited with non-zero status code {}".format(wget.poll()))

        gpg = subprocess.Popen(
            ["gpgv", "--keyring", "./libressl.gpg", f"{tmpfile}.asc", tmpfile], stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
        stdout, _ = gpg.communicate()
        stdout = stdout.decode()

        print(stdout)

        # We expect the main public key to be in the keyring so gpg prints "Good signature"
        if "Signature made" in stdout \
           and "Good signature" in stdout \
           and "Can't check signature: No public key" not in stdout \
           and gpg.poll() == 0:
            print("Signature verified")
        else:
            raise RuntimeException(f"Unable to verify GPG signature for '{filename}'!")

        tar = subprocess.Popen(
            ["tar", "-xz", "--strip-components", "1", "-f", tmpfile], cwd=repo_dir
        )
        if tar.wait() != 0:
            raise RuntimeError("tar exited with non-zero status code {}".format(tar.poll()))

    finally:
        os.remove(tmpfile)
        os.remove(tmpfile + ".asc")

    git_sp = subprocess.Popen(
        "git add *", shell=True, cwd=repo_dir
    )
    if git_sp.wait() != 0:
        raise RuntimeError("git exited with non-zero status code {}".format(git_sp.poll()))

    verstring = "v{}".format(str(fileinfo["version"]))
    repo.index.commit("LibreSSL {}".format(verstring))
    repo.create_tag(verstring, message="Version {}".format(verstring))


def main():
    cfg = get_config_env()
    repo = cfg["GIT_REPO"]
    tls = get_use_tls()

    mirrors = LIBRESSL_FTP_MIRRORS
    if tls:
        print("Using TLS mirrors only")
        mirrors = list(
            filter(
                lambda x: x["tls"],
                LIBRESSL_FTP_MIRRORS
            )
        )

    print("Using git repo:", repo)

    gitlatest = get_git_latest_version()

    print("Latest version in git:", gitlatest)

    count = 0
    while True:
        try:
            mirror = random.choice(mirrors)
            mirrors.remove(mirror)
            versions_above = find_versions_above(mirror=mirror, target_version=gitlatest)

            for fileinfo in versions_above:
                print("Downloading version", fileinfo["version"], "from", fileinfo["host"])

                clear_git_repo()
                download_package_to_repo(fileinfo)
                count += 1

        except ftplib.error_perm as e:
            print(f"Mirror returned error: {e}")
            continue
        except ConnectionRefusedError:
            print("Connection refused")
            continue
        except TimeoutError:
            print("Connection timed out")
            continue
        except OSError:
            print(
                "The world hates us and an unknown error occurred. But we're strong and independent, so we'll skip it.")
            traceback.print_exc()
            continue
        break

    if count > 0:
        print("Pushing to remote repository")
        git_sp = subprocess.Popen(
            ["git", "push", "origin", "master", "--tags"],
            cwd=repo
        )
        git_sp.wait()
    else:
        print("No new version found")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        os.environ["LSSLM_GIT_REPO"] = sys.argv[1]
    main()
