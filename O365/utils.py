import inspect
import logging
from functools import wraps
import os

log = logging.getLogger(__name__)


def deprecated(*replacement):
    """ Decorator to mark a specified function as deprecated

    :param replacement: replacement function to use
    :param removed: whether the function is removed completely
    """
    outer = inspect.getouterframes(inspect.currentframe())
    for i, temp in enumerate(outer):
        if temp[3] == 'run':
            break
    frame = outer[i - 1]

    def deprecated_wrapper(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            log_message = ("'{}' is deprecated, Use {} instead"
                           "".format(_get_func_data(func),
                                     ', '.join(
                                         ["'{}'".format(_get_func_data(x))
                                          for x in replacement])))
            log.warning(log_message)
            return func(*args, **kwargs)

        return wrapper

    return deprecated_wrapper


def _get_func_data(func):
    full_path = "{}.".format(func.__module__)
    if callable(func):
        try:
            temp = func.im_class
            full_path += "{}.".format(temp.__name__)
        except AttributeError as _:
            pass
    full_path += func.__name__
    return full_path
