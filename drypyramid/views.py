from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPFound,
)
from pyramid.security import (
    remember,
    forget,
)
from deform import Form, ValidationFailure, Button
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
from .models import SASession, BaseUser
from .forms import UserLoginForm


def check_post_csrf(func):
    def inner(context, request):
        if request.method == "POST" and not(
                request.session.get_csrf_token() ==
                request.POST.get('csrf_token')):
            return HTTPBadRequest("Your session seems to have timed out.")
        else:
            return func.__call__(context, request)
    return inner


def model_list(model):
    def list(request):
        # todo: paginate
        records = model.query().all()
        return {'records': records}
    return list


def model_show(model):
    def show(context, request):
        return {'record': context}
    return show


def model_create(model, schema, after_create_url_callback):
    def create(context, request):
        form = Form(schema.__call__().bind(), buttons=(
            "save", Button('reset', "Reset", 'reset')))
        if request.method == 'POST':
            data = request.POST.items()
            try:
                values = form.validate(data)
            except ValidationFailure:
                request.session.flash(
                    u"Please fix the errors indicated below.", "error")
            else:
                record = model.create_from_dict(dict(values))
                record.save()
                #try:
                SASession.flush()
                #except IntegrityError:
                #    request.session.flash("A duplicate record exists", "error")
                #else:
                request.session.flash(
                    u"Your changes have been saved.", "success")
                url = after_create_url_callback(request, record)
                return HTTPFound(url)
        csrf_token = request.session.get_csrf_token()
        return {'csrf_token': csrf_token, 'form': form}
    return create


def model_update(model, schema, after_update_url_callback):
    def update(context, request):
        record = context
        form = Form(schema.__call__().bind(pk=record.id),
                    buttons=("save", Button('reset', "Reset", 'reset')),
                    appstruct=record.to_dict())
        if request.method == 'POST':
            data = request.POST.items()
            try:
                values = form.validate(data)
            except ValidationFailure:
                request.session.flash(
                    u"Please fix the errors indicated below.", "error")
            else:
                record.update_from_dict(dict(values))
                record.save()
                request.session.flash(
                    u"Your changes have been saved.", "success")
                url = after_update_url_callback(request, record)
                return HTTPFound(url)
        csrf_token = request.session.get_csrf_token()
        return {'csrf_token': csrf_token, 'form': form}
    return update


def model_delete(after_delete_url_callback):
    def delete(context, request):
        record = context
        record.delete()
        request.session.flash(
            u"The record has been deleted.", "success")
        url = after_delete_url_callback(request)
        return HTTPFound(url)
    return delete


class ModelView(object):
    LIST = 'list'
    CREATE = 'create'
    SHOW = 'show'
    UPDATE = 'update'
    DELETE = 'delete'

    enabled_views = (LIST, CREATE, SHOW, UPDATE, DELETE)

    ModelFactoryClass = None
    ModelFormClass = None
    ModelUpdateFormClass = None

    base_name_override = None

    list_view_renderer = 'templates/{base_name}_list.pt'
    list_view_permission = 'list'

    create_view_renderer = 'templates/{base_name}_create.pt'
    create_view_permission = 'create'

    show_view_renderer = 'templates/{base_name}_show.pt'
    show_view_permission = 'view'

    update_view_renderer = 'templates/{base_name}_update.pt'
    update_view_permission = 'update'

    delete_view_permission = 'delete'

    @classmethod
    def get_base_name(cls):
        return cls.base_name_override if\
            cls.base_name_override is not None else\
            cls.ModelFactoryClass.ModelClass.__tablename__

    @classmethod
    def include(cls, config, **kwargs):
        ModelClass = cls.ModelFactoryClass.ModelClass
        base_name = cls.base_name_override if\
            cls.base_name_override is not None else\
            ModelClass.__tablename__
        cls.ModelFactoryClass.__base_name__ = base_name

        config.add_route('{0}'.format(base_name),
                         '/{0}/*traverse'.format(base_name),
                         factory=cls.ModelFactoryClass)

        if 'list' in cls.enabled_views:
            config.add_view(model_list(ModelClass),
                            context=cls.ModelFactoryClass,
                            route_name=base_name,
                            renderer=cls.list_view_renderer.format(
                                base_name=base_name),
                            permission=cls.list_view_permission)

        if 'create' in cls.enabled_views:
            config.add_view(model_create(ModelClass, cls.ModelFormClass,
                                         cls.after_create_redirect_url),
                            context=cls.ModelFactoryClass,
                            route_name=base_name, name='add',
                            renderer=cls.create_view_renderer.format(
                                base_name=base_name),
                            permission=cls.create_view_permission)

        if 'show' in cls.enabled_views:
            config.add_view(model_show(ModelClass),
                            context=ModelClass,
                            route_name=base_name,
                            renderer=cls.show_view_renderer.format(
                                base_name=base_name),
                            permission=cls.show_view_permission)

        if 'update' in cls.enabled_views:
            config.add_view(model_update(ModelClass, cls.ModelUpdateFormClass
                            if cls.ModelUpdateFormClass
                            else cls.ModelFormClass,
                                         cls.after_update_redirect_url),
                            context=ModelClass, route_name=base_name,
                            name='edit',
                            renderer=cls.update_view_renderer.format(
                                base_name=base_name),
                            permission=cls.update_view_permission)

        if 'delete' in cls.enabled_views:
            config.add_view(model_delete(cls.after_delete_redirect_url),
                            context=ModelClass, route_name=base_name,
                            name='delete',
                            permission=cls.delete_view_permission,
                            request_method='POST', check_csrf=True)

    @classmethod
    def after_create_redirect_url(cls, request, record):
        return request.route_url(cls.ModelFactoryClass.__base_name__,
                                 traverse=(record.id,))

    @classmethod
    def after_update_redirect_url(cls, request, record):
        return request.route_url(cls.ModelFactoryClass.__base_name__,
                                 traverse=(record.id, 'edit'))

    @classmethod
    def after_delete_redirect_url(cls, request):
        return request.route_url(cls.ModelFactoryClass.__base_name__,
                                 traverse=())


@check_post_csrf
def user_login(context, request):
    login_url = request.route_url('login')
    referrer = request.url
    if referrer == login_url:
        # never use the login form itself as came_from
        referrer = request.route_url('site', traverse=())
    else:
        request.response.status_code = 403
    came_from = request.session.get('came_from', referrer)
    form = Form(UserLoginForm(),
                action=request.route_url('login'), buttons=('login',))
    if request.method == 'POST':
        data = request.POST.items()
        try:
            values = form.validate(data)
        except ValidationFailure:
            request.session.flash(
                u"Please fix the errors indicated below.", "error")
        else:
            account_id = values['account_id']
            password = values['password']
            try:
                user = BaseUser.query().filter(
                    BaseUser.account_id == account_id).one()
            except NoResultFound:
                request.session.flash(
                    u"Invalid username or password.", "error")
            else:
                if user.check_password(password):
                    if 'came_from' in request.session:
                        del request.session['came_from']
                    headers = remember(request, user.id)
                    return HTTPFound(came_from, headers=headers)
                else:
                    request.session.flash(
                        u"Invalid username or password.", "error")

    request.session['came_from'] = referrer
    csrf_token = request.session.get_csrf_token()
    return {'csrf_token': csrf_token, 'form': form}


def user_logout(request):
    headers = forget(request)
    return HTTPFound(
        location=request.route_url('login'), headers=headers)
