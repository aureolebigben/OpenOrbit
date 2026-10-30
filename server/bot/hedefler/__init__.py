"""Hedef modülleri: her dosya bir ya da birkaç @beyin.hedef sınıfı tanımlar. Yeni davranış için buraya bir modül eklemek yeter."""
import importlib, os, pkgutil


def yukle():
    for m in pkgutil.iter_modules([os.path.dirname(os.path.abspath(__file__))]):
        importlib.import_module(__name__ + '.' + m.name)
