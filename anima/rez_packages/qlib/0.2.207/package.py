# -*- coding: utf-8 -*-

name = "qlib"

version = "0.2.207"

author = [
    "Erkan Ozgur Yilmaz",
]

uuid = "742b691df8324d9a90b072da4cc8d8f0"

description = "qLib Package"

build_command = "python {root}/../build.py {install}"


def commands():
    env.QLIB = "${HOME}/Documents/development/qLib"
    env.QOTL = "${QLIB}/otls"
    env.HOUDINI_PATH.append("${QLIB}")
    if "&" not in env.HOUDINI_PATH.value():
        env.HOUDINI_PATH.append("&")
