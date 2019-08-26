#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import ftplib
import random
import re
import shutil
import subprocess
from ftplib import FTP
from typing import Mapping, Optional, Generator, Union, Dict

import git
import packaging
from packaging.version import Version

LIBRESSL_FTP_MIRRORS = [
    {"host": "mirror.internode.on.net", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "mirrors.unb.br", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "mirror.csclub.uwaterloo.ca", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "ftp.eenet.ee", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "ftp2.fr.openbsd.org", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "ftp.spline.de", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "mirror.hs-esslingen.de", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "ftp.bytemine.net", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "ftp.cc.uoc.gr", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "ftp.fsn.hu", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "ftp.heanet.ie", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "ftp.riken.jp", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "ftp.bit.nl", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "ftp.uio.no", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "ftp.eu.openbsd.org", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "ftp.man.poznan.pl", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "ftp.obsd.si", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "ftp.yzu.edu.tw", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "ftp.mirrorservice.org", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "mirror.bytemark.co.uk", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "mirror.ox.ac.uk", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "mirror.exonetric.net", "path": "/pub/OpenBSD/LibreSSL/"},
    {"host": "ftp5.usa.openbsd.org", "path": "/pub/OpenBSD/LibreSSL/"},
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
    ftp = FTP(mirror['host'])
    ftp.login(user=mirror.get('user', ''), passwd=mirror.get('passwd', ''), acct=mirror.get('acct', ''))
    ftp.cwd(mirror['path'])

    for filename, attrs in ftp.mlsd():
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

    wget = subprocess.Popen(
        ["wget", "-O", "-", f"ftp://{fileinfo['host']}/{fileinfo['path']}/{fileinfo['filename']}"],
        stdout=subprocess.PIPE
    )
    tar = subprocess.Popen(
        ["tar", "-xz", "--strip-components", "1"],
        stdin=wget.stdout, cwd=repo_dir
    )

    if tar.wait() != 0:
        raise RuntimeError("tar exited with non-zero status code {}".format(tar.poll()))
    if wget.wait() != 0:
        raise RuntimeError("wget exited with non-zero status code {}".format(wget.poll()))

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

    print("Using git repo:", repo)

    gitlatest = get_git_latest_version()

    print("Latest version in git:", gitlatest)

    while True:
        try:
            mirror = random.choice(LIBRESSL_FTP_MIRRORS)
            LIBRESSL_FTP_MIRRORS.remove(mirror)
            versions_above = find_versions_above(mirror=mirror, target_version=gitlatest)

            count = 0
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
