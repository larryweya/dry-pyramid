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


def model_create(model, schema, post_save_response_callback,
                 pre_save_callback=None):
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
                if pre_save_callback:
                    pre_save_callback(request, record, values)
                record.save()
                #try:
                SASession.flush()
                #except IntegrityError:
                #    request.session.flash("A duplicate record exists", "error")
                #else:
                request.session.flash(
                    u"Your changes have been saved.", "success")
                return post_save_response_callback(request, record)
        return {'form': form}
    return create


def model_update(model, schema, post_save_response_callback,
                 pre_save_callback=None):
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
                if pre_save_callback:
                    pre_save_callback(request, record, values)
                record.save()
                request.session.flash(
                    u"Your changes have been saved.", "success")
                return post_save_response_callback(request, record)
        return {'form': form}
    return update


def model_delete(post_delete_response_callback):
    def delete(context, request):
        record = context
        record.delete()
        request.session.flash(
            u"The record has been deleted.", "success")
        return post_delete_response_callback(request, record)
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

    route_name_override = None
    base_url_override = None

    list_view_renderer = 'templates/{route_name}_list.pt'
    list_view_permission = 'list'

    create_view_renderer = 'templates/{route_name}_create.pt'
    create_view_permission = 'create'

    show_view_renderer = 'templates/{route_name}_show.pt'
    show_view_permission = 'view'

    update_view_renderer = 'templates/{route_name}_update.pt'
    update_view_permission = 'update'

    delete_view_permission = 'delete'

    @classmethod
    def get_route_name(cls):
        return cls.route_name_override if\
            cls.route_name_override is not None else\
            cls.ModelFactoryClass.ModelClass.__tablename__

    @classmethod
    def get_base_url(cls):
        return cls.base_url_override if\
            cls.base_url_override is not None else\
            cls.ModelFactoryClass.ModelClass.__tablename__

    @classmethod
    def include(cls, config):
        ModelClass = cls.ModelFactoryClass.ModelClass
        route_name = cls.get_route_name()
        base_url = cls.get_base_url()
        cls.ModelFactoryClass.__route_name__ = route_name

        config.add_route('{0}'.format(route_name),
                         '/{0}/*traverse'.format(base_url),
                         factory=cls.ModelFactoryClass)

        if 'list' in cls.enabled_views:
            config.add_view(model_list(ModelClass),
                            context=cls.ModelFactoryClass,
                            route_name=route_name,
                            renderer=cls.list_view_renderer.format(
                                route_name=route_name),
                            permission=cls.list_view_permission)

        if 'create' in cls.enabled_views:
            config.add_view(model_create(ModelClass, cls.ModelFormClass,
                                         cls.post_create_response_callback),
                            context=cls.ModelFactoryClass,
                            route_name=route_name, name='add',
                            renderer=cls.create_view_renderer.format(
                                route_name=route_name),
                            permission=cls.create_view_permission)

        if 'show' in cls.enabled_views:
            config.add_view(model_show(ModelClass),
                            context=ModelClass,
                            route_name=route_name,
                            renderer=cls.show_view_renderer.format(
                                route_name=route_name),
                            permission=cls.show_view_permission)

        if 'update' in cls.enabled_views:
            config.add_view(model_update(ModelClass, cls.ModelUpdateFormClass
                            if cls.ModelUpdateFormClass
                            else cls.ModelFormClass,
                                         cls.post_update_response_callback),
                            context=ModelClass, route_name=route_name,
                            name='edit',
                            renderer=cls.update_view_renderer.format(
                                route_name=route_name),
                            permission=cls.update_view_permission)

        if 'delete' in cls.enabled_views:
            config.add_view(model_delete(cls.post_delete_response_callback),
                            context=ModelClass, route_name=route_name,
                            name='delete',
                            permission=cls.delete_view_permission,
                            request_method='POST', check_csrf=True)

    @classmethod
    def post_save_response(cls, request, record):
        return HTTPFound(request.route_url(cls.get_route_name(),
                                           traverse=(record.id, 'edit')))

    @classmethod
    def post_delete_response(cls, request, record):
        return HTTPFound(request.route_url(cls.get_route_name(),
                                           traverse=()))

    post_create_response_callback = post_save_response
    post_update_response_callback = post_save_response
    post_delete_response_callback = post_delete_response


@check_post_csrf
def user_login(context, request):
    login_url = request.route_url('login')
    referrer = request.url
    if referrer == login_url:
        # never use the login form itself as came_from
        referrer = request.route_url('root', traverse=())
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
