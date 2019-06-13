from pkg_resources import get_distribution, DistributionNotFound

try:
    __version__ = get_distribution(__name__.split('.')[0]).version
except DistributionNotFound:
    # Package is not installed.
    __version__ = None
