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
            return HTTPBadRequest()
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


def model_create(model, schema):
    # todo: perhaps get the schema associated with this model here then
    # instantiate whenever the view is called
    #schema = model.get_schema()

    def create(context, request):
        form = Form(schema.__call__(), buttons=(
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
                return HTTPFound(record.show_url(request))
        csrf_token = request.session.get_csrf_token()
        return {'csrf_token': csrf_token, 'form': form}
    return create


def model_update(model, schema):
    def update(context, request):
        record = context
        form = Form(schema.__call__().bind(),
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
                return HTTPFound(record.show_url(request))
        csrf_token = request.session.get_csrf_token()
        return {'csrf_token': csrf_token, 'form': form}
    return update


@check_post_csrf
def user_login(context, request):
    login_url = request.route_url('login')
    referrer = request.url
    if referrer == login_url:
        # never use the login form itself as came_from
        referrer = request.route_url('default')
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
            try:
                user = BaseUser.query().filter(
                    BaseUser.account_id == account_id).one()
                # todo: check password
            except NoResultFound:
                request.session.flash(
                    u"Invalid username or password.", "error")
            else:
                if 'came_from' in request.session:
                    del request.session['came_from']
                headers = remember(request, user.id)
                return HTTPFound(came_from, headers=headers)

    request.session['came_from'] = referrer
    csrf_token = request.session.get_csrf_token()
    return {'csrf_token': csrf_token, 'form': form}


def user_logout(request):
    headers = forget(request)
    return HTTPFound(
        location=request.route_url('login'), headers=headers)
