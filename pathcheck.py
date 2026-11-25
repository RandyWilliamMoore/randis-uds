# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import os

_LONG = "\\\\?\\"
_LONG_UNC = "\\\\?\\UNC\\"


def real(p):
    r = os.path.realpath(p)
    if os.name == "nt" and r.startswith(_LONG):
        r = "\\\\" + r[len(_LONG_UNC):] if r.startswith(_LONG_UNC) else r[len(_LONG):]
    return r


def canon(p):
    return os.path.normcase(real(p))


def within(root, path, allow_root=False):
    r, f = canon(root), canon(path)
    if f == r:
        return allow_root
    return f.startswith(r if r.endswith(os.sep) else r + os.sep)
