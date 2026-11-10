"""Carga módulos de un servicio por ruta, con nombre único, para que los tests de distintos
servicios (que tienen archivos con el mismo nombre: main.py, repository.py) no se pisen."""
import importlib.util
import os
import sys
import types
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def load(service_dir, filename, alias, fakes):
    """Importa <service_dir>/<filename> como `alias`, con `fakes` {nombre: módulo} en sys.modules."""
    path = os.path.join(ROOT, service_dir, filename)
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, fakes):
        spec.loader.exec_module(module)
    return module


def fake_module(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    return m
