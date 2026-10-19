import importlib.machinery
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


def script(plugin, rel):
    return os.path.join(ROOT, "plugins", plugin, rel)


def load(plugin, rel):
    p = script(plugin, rel)
    name = os.path.basename(p).replace("-", "_")
    loader = importlib.machinery.SourceFileLoader(name, p)
    spec = importlib.util.spec_from_loader(name, loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m
