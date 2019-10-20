# -*- coding: utf-8 -*-
# Copyright (c) 2012-2019, Anima Istanbul
#
# This module is part of anima and is released under the MIT
# License: http://www.opensource.org/licenses/MIT


def extends(cls):
    """A decorator for extending classes with other class methods or functions.

    :param cls: The class object that will be extended.
    """
    def wrapper(f):
        if isinstance(f, property):
            name = f.fget.__name__
        else:
            name = f.__name__
        if isinstance(cls, type):
            setattr(cls, name, f)
        elif isinstance(cls, list):
            for c in cls:
                setattr(c, name, f)

        def wrapped_f(*args, **kwargs):
            return f(*args, **kwargs)

        return wrapped_f
    return wrapper
