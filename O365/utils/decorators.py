import logging
from functools import wraps

log = logging.getLogger(__name__)


def deprecated(version, *replacement):
    """ Decorator to mark a specified function as deprecated

    :param version: version in which it is deprecated
    :param replacement: replacement functions to use
    """

    def deprecated_wrapper(func):
        replacement_message = 'Use {} instead'.format(', '.join(
            ["'{}'".format(_get_func_fq_name(x))
             for x in replacement]))
        log_message = ("'{}' is deprecated, {}"
                       "".format(_get_func_fq_name(func), replacement_message))
        # func.__doc__ = replacement[0].__doc__

        func_path = _get_func_path(func)
        doc_replacement = []
        for x in replacement:
            if func_path == _get_func_path(x):
                doc_replacement.append(':func:`{}`'.format(_func_name(x)))
            else:
                doc_replacement.append(
                    ':func:`{}`'.format(_get_func_fq_name(x)))

        func.__doc__ = """
            .. deprecated:: {}
               Use {} instead
               
               {} 
            """.format(version,
                       ', '.join(doc_replacement),
                       func.__doc__ if func.__doc__ else '')

        @wraps(func)
        def wrapper(*args, **kwargs):
            log.warning(log_message)
            return func(*args, **kwargs)

        return wrapper

    return deprecated_wrapper


def _func_name(func):
    if isinstance(func, property):
        func = func.fget
    return func.__name__


def _get_func_path(func):
    if isinstance(func, property):
        func = func.fget
    full_path = "{}.".format(func.__module__)
    if callable(func):
        try:
            temp = func.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0]
            full_path += "{}.".format(temp)
        except AttributeError as _:
            try:
                # noinspection PyUnresolvedReferences
                temp = func.im_class
                full_path += "{}.".format(temp)
            except AttributeError as _:
                pass

    return full_path


def _get_func_fq_name(func):
    if isinstance(func, property):
        func = func.fget
    full_path = _get_func_path(func)
    full_path += func.__name__
    return full_path


def fluent(func):
    func.__doc__ = """{}
        .. note:: This method is part of fluent api and can be chained
    """.format(func.__doc__ if func.__doc__ else '')

    @wraps(func)
    def inner(self, *args, **kwargs):
        return func(self, *args, **kwargs)

    return inner


def action(func):
    func.__doc__ = """{}
        .. note:: The success/failure of this action can be obtained 
         from **success** and **error_message** attributes after 
         executing this function
         
         Example:
            .. code-block:: python
                
                my_obj.one().two().finish()
                if not my_obj.is_success:
                    print(my_obj.error_message) 
                    
            this will return success/failure of **finish** action
    """.format(func.__doc__ if func.__doc__ else '')

    @wraps(func)
    def inner(self, *args, **kwargs):
        obj = self.__class__.__new__(self.__class__)
        obj.__dict__ = self.__dict__.copy()
        func(obj, *args, **kwargs)
        return obj

    return inner
