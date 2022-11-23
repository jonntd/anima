# -*- coding: utf-8 -*-

name = "fusion"

version = "18.0.0"

author = [
    "Erkan Ozgur Yilmaz"
]

uuid = "59a8d4cd31414e888b4f859ef14b0fb7"

description = "Fusion package"

requires = [
    "python"
]

variants = [
    ["python-2"],
    ["python-3"]
]

build_command = "python3 {root}/../build.py {install}"


def commands():
    # env.PYTHONPATH.append("{root}/python")
    # env.PATH.append("{root}/bin")
    env.PATH.append(
        "/opt/BlackmagicDesign/Fusion{}/".format(env.REZ_FUSION_MAJOR_VERSION)
    )
    env.PATH.append(
        "/opt/BlackmagicDesign/FusionRenderNode{}/".format(env.REZ_FUSION_MAJOR_VERSION)
    )
    env.PYTHONPATH.append(
        "/opt/BlackmagicDesign/Fusion{}/".format(env.REZ_FUSION_MAJOR_VERSION)
    )
