"""Offline deterministic rerun from saved raw artifacts. Downloads are explicit."""
import _bootstrap
from src.dataset_builder import build
from src.dataset_builder.model import train
from validate_sources import main as validate
from generate_report import main as report
if __name__=='__main__':
    build(_bootstrap.ROOT)
    validate()
    train(_bootstrap.ROOT)
    report()
