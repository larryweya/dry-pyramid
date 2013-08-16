from passlib.context import CryptContext
from pyramid.security import has_permission


pwd_context = CryptContext()


def permission_check_func(context, request):
    """ Attach a function for has_permission checks within templates.

    For example:

    .. code-block:: python

        @subscriber(BeforeRender)
        def attach_has_permission_callback(event):
        if event['view']:
            event['has_permission'] = permission_check_func(
                event['context'], event['request'])
    """
    def inner(permission):
        return has_permission(permission, context, request)
    return inner
