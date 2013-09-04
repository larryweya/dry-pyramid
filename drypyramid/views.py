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
    def show(request):
        return {'record': request.context}
    return show


def model_create(model, schema, pre_save_callback=None,
                 post_save_response_callback=None):
    # todo: perhaps get the schema associated with this model here then
    # instantiate whenever the view is called
    #schema = model.get_schema()

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
                record = model.create_from_dict(values)
                if pre_save_callback:
                    pre_save_callback(request, record)
                record.save()
                #try:
                SASession.flush()
                #except IntegrityError:
                #    request.session.flash("A duplicate record exists", "error")
                #else:
                request.session.flash(
                    u"Your changes have been saved.", "success")
                if post_save_response_callback:
                    return post_save_response_callback(request, record)
                else:
                    return HTTPFound(record.show_url(request))
        csrf_token = request.session.get_csrf_token()
        return {'csrf_token': csrf_token, 'form': form}
    return create


def model_update(model, schema, pre_save_callback=None,
                 post_save_response_callback=None):
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
                record.update_from_dict(values)
                if pre_save_callback:
                    pre_save_callback(request, record, values)
                record.save()
                request.session.flash(
                    u"Your changes have been saved.", "success")
                if post_save_response_callback:
                    return post_save_response_callback(request, record)
                else:
                    return HTTPFound(record.show_url(request))
        csrf_token = request.session.get_csrf_token()
        return {'csrf_token': csrf_token, 'form': form, 'record': record}
    return update


def model_delete(factory):
    def delete(context, request):
        record = context
        record.delete()
        request.session.flash(
            u"The record has been deleted.", "success")
        return HTTPFound(factory(request).list_url(request))
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
    pre_create_callback = None
    post_create_response_callback = None

    show_view_renderer = 'templates/{base_name}_show.pt'
    show_view_permission = 'view'

    update_view_renderer = 'templates/{base_name}_update.pt'
    update_view_permission = 'update'
    pre_update_callback = None
    post_update_response_callback = None

    delete_view_permission = 'delete'
    post_delete_response_callback = None

    def __init__(self, config, **kwargs):
        ModelClass = self.ModelFactoryClass.ModelClass
        base_name = self.base_name_override if\
            self.base_name_override is not None else\
            ModelClass.__tablename__

        if 'list' in self.enabled_views:
            config.add_view(model_list(ModelClass),
                            context=self.ModelFactoryClass,
                            route_name='site',
                            renderer=self.list_view_renderer.format(
                                base_name=base_name),
                            permission=self.list_view_permission)

        if 'create' in self.enabled_views:
            config.add_view(model_create(ModelClass, self.ModelFormClass),
                            context=self.ModelFactoryClass,
                            route_name='site', name='add',
                            renderer=self.create_view_renderer.format(
                                base_name=base_name),
                            permission=self.create_view_permission)

        if 'show' in self.enabled_views:
            config.add_view(model_show(ModelClass),
                            context=ModelClass,
                            route_name='site',
                            renderer=self.show_view_renderer.format(
                                base_name=base_name),
                            permission=self.show_view_permission)

        if 'update' in self.enabled_views:
            config.add_view(model_update(ModelClass, self.ModelUpdateFormClass
                            if self.ModelUpdateFormClass
                            else self.ModelFormClass),
                            context=ModelClass, route_name='site', name='edit',
                            renderer=self.update_view_renderer.format(
                                base_name=base_name),
                            permission=self.update_view_permission)

        if 'delete' in self.enabled_views:
            config.add_view(model_delete(self.ModelFactoryClass),
                            context=ModelClass, route_name='site',
                            name='delete',
                            permission=self.delete_view_permission,
                            request_method='POST', check_csrf=True)

    @classmethod
    def get_model_update_form_class(cls):
        return cls.ModelUpdateFormClass if cls.ModelUpdateFormClass\
            else cls.ModelFormClass


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
