#!/bin/bash

gpg --import ./libressl.pub
gpg --export > libressl.gpg
