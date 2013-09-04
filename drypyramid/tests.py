import unittest
import colander

from webob.multidict import MultiDict
from webtest import TestApp
from pyramid import testing
from pyramid.httpexceptions import (
    HTTPNotFound,
    HTTPFound
)
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Table,
    ForeignKey,
)
from sqlalchemy.orm import (
    relationship,
)
from .models import (
    SASession,
    Base,
    ModelFactory,
    BaseRootFactory,
    BaseUser,
)
from .auth import pwd_context
from .views import (
    model_list,
    model_create,
    model_show,
    model_update,
    model_delete,
    ModelView,
)


person_hobby = Table(
    'person_hobby', Base.metadata,
    Column('person_id', Integer, ForeignKey('person.id')),
    Column('hobby_id', Integer, ForeignKey('hobby.id')),
)


class Person(Base):
    __tablename__ = 'person'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    age = Column(Integer, nullable=False)
    hobbies = relationship('Hobby', secondary=person_hobby, backref='people')


class Hobby(Base):
    __tablename__ = 'hobby'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)


class PersonModelFactory(ModelFactory):
    ModelClass = Person

    def post_get_item(self, item):
        self.post_get_item_called = True


class PersonForm(colander.MappingSchema):
    name = colander.SchemaNode(colander.String(encoding='utf-8'))
    age = colander.SchemaNode(colander.Integer())


class HobbiesSchema(colander.SequenceSchema):
    name = colander.SchemaNode(
        colander.String(encoding='utf-8'), title="Hobby")


class PersonUpdateForm(colander.MappingSchema):
    hobbies = HobbiesSchema(values=[
        ('su', 'Superuser'),
        ('billing', 'Billing'),
        ('customer_care', 'Customer Care')
    ])


class TestBase(unittest.TestCase):
    def _setup_db(self):
        self.engine = create_engine('sqlite:///:memory:', echo=True)
        SASession.configure(bind=self.engine)
        Base.metadata.create_all(self.engine)

    def setUp(self):
        self.config = testing.setUp()
        #self.config.add_route('login', '/login')
        #self.config.add_route('site', '/*traverse')
        self._setup_db()

    def tearDown(self):
        SASession.remove()
        testing.tearDown()


class TestBaseModel(TestBase):
    def test_create_from_dict(self):
        data = {
            'name': "Mr Smith",
            'age': 23
        }
        model = Person.create_from_dict(data)
        self.assertEqual(model.name, data['name'])
        self.assertEqual(model.age, data['age'])

    def test_to_dict(self):
        model = Person(name="Mr Smith", age=23)
        data = model.to_dict()
        expected_data = {
            'id': None,
            'name': "Mr Smith",
            'age': 23
        }
        self.assertEqual(data, expected_data)

    def test_update_from_dict(self):
        model = Person(name="Mr Smith", age=23)
        update_data = {
            'name': "Mrs Smith",
            'age': 35
        }
        model.update_from_dict(update_data)
        self.assertEqual(model.name, update_data['name'])
        self.assertEqual(model.age, update_data['age'])

    def test_to_dict_handles_relationships(self):
        pass


class TestModelFactory(TestBase):
    def setUp(self):
        super(TestModelFactory, self).setUp()
        self.request = testing.DummyRequest()
        # this is done by ModelView on include
        route_name = 'persons'
        base_url = 'people'
        PersonModelFactory.__route_name__ = route_name
        self.config.add_route(route_name, '/{0}/*traverse'.format(base_url),
                              factory=PersonModelFactory)
        self.factory = PersonModelFactory(self.request)

    def test_list_url(self):
        url = self.factory.list_url(self.request)
        expected_url = "%s/people/" % self.request.application_url
        self.assertEqual(url, expected_url)

    def test_create_url(self):
        self.factory = PersonModelFactory(self.request)
        url = self.factory.create_url(self.request)
        expected_url = "%s/people/add" % self.request.application_url
        self.assertEqual(url, expected_url)

    def test_show_url(self):
        person = Person(id=1, name="Mr Smith", age=23)
        url = self.factory.show_url(self.request, person)
        expected_url = "{0}/people/{1}".format(self.request.application_url,
                                               person.id)
        self.assertEqual(url, expected_url)

    def test_update_url(self):
        person = Person(id=1, name="Mr Smith", age=23)
        url = self.factory.update_url(self.request, person)
        expected_url = "{0}/people/{1}/edit".format(
            self.request.application_url, person.id)
        self.assertEqual(url, expected_url)

    def test_delete_url(self):
        person = Person(id=1, name="Mr Smith", age=23)
        url = self.factory.delete_url(self.request, person)
        expected_url = "{0}/people/{1}/delete".format(
            self.request.application_url, person.id)
        self.assertEqual(url, expected_url)

    def test_get_item_calls_post_get_item(self):
        self.factory = PersonModelFactory(self.request)
        # create a Person
        person = Person(name="Mr Smith", age=23)
        person.save()
        self.factory.__getitem__('1')
        self.assertTrue(self.factory.post_get_item_called)


class TestViewHelpers(TestBase):
    def setUp(self):
        super(TestViewHelpers, self).setUp()
        self.config.add_route('persons', '/persons/*traverse',
                              factory=PersonModelFactory)

    def test_model_list(self):
        person = Person(name='Mr Smith', age=23)
        person.save()
        SASession.flush()

        view = model_list(Person)
        request = testing.DummyRequest()
        response = view(request)
        self.assertIn('records', response)
        self.assertIsInstance(response['records'][0], Person)

    def test_model_create(self):
        def _post_create_response_callback(request, record):
            return HTTPFound(request.route_url('persons',
                                               traverse=(record.id,)))

        def _pre_create_callback(request, record, values):
            record.age = 25

        view = model_create(Person, PersonForm, _post_create_response_callback,
                            _pre_create_callback)
        request = testing.DummyRequest()
        request.method = 'POST'
        values = [
            ('csrf_token', request.session.get_csrf_token()),
            ('name', 'Mr Smith'),
            ('age', '22'),
        ]
        request.POST = MultiDict(values)
        context = PersonModelFactory(request)
        response = view(context, request)
        self.assertIsInstance(response, HTTPFound)
        self.assertEqual(response.location,
                         '{0}/persons/1'.format(request.application_url))
        person = Person.query().filter_by(name='Mr Smith').one()
        self.assertEqual(person.age, 25)

    def test_model_show(self):
        person = Person(name='Mr Smith', age=23)
        person.save()
        SASession.flush()

        view = model_show(Person)
        request = testing.DummyRequest()
        response = view(person, request)
        self.assertIn('record', response)
        self.assertIsInstance(response['record'], Person)

    def test_model_update(self):
        def _post_update_response_callback(request, record):
            return HTTPFound(request.route_url('persons',
                                               traverse=(record.id,)))

        person = Person(name='Not Mr Smith', age=23)
        person.save()
        SASession.flush()

        def _pre_update_callback(request, record, values):
            record.age = 28

        view = model_update(Person, PersonForm, _post_update_response_callback,
                            _pre_update_callback)
        request = testing.DummyRequest()
        request.method = 'POST'
        values = [
            ('csrf_token', request.session.get_csrf_token()),
            ('name', 'Mr Smith'),
            ('age', '22'),
        ]
        request.POST = MultiDict(values)
        response = view(person, request)
        self.assertIsInstance(response, HTTPFound)
        self.assertEqual(response.location,
                         '{0}/persons/1'.format(request.application_url))
        person = Person.query().filter_by(name='Mr Smith').one()
        self.assertEqual(person.age, 28)

    def test_model_delete(self):
        def _post_del_response_callback(request, record):
            return HTTPFound(request.route_url('persons', traverse=()))

        person = Person(name='Mr Smith', age=23)
        person.save()
        SASession.flush()
        view = model_delete(_post_del_response_callback)
        self.config.add_view(view,
                             context=PersonModelFactory,
                             route_name='persons',
                             name='delete',
                             permission='delete',
                             check_csrf=True)
        request = testing.DummyRequest()
        request.method = 'POST'
        response = view(person, request)
        self.assertIsInstance(response, HTTPFound)
        self.assertEqual(response.location,
                              '{0}/persons/'.format(request.application_url))


class TestRootFactory(BaseRootFactory):
        pass


class FunctionalTestBase(TestBase):
    application_url = 'http://localhost'

    def setUp(self):
        super(FunctionalTestBase, self).setUp()
        self.config.set_root_factory(TestRootFactory)
        session_factory = testing.DummySession
        self.config.set_session_factory(session_factory)


class TestModelView(FunctionalTestBase):
    class TestRenderer(object):
        responses = {
            'templates/person_list.pt': '{{"title": "People List"}}',
            'templates/person_create.pt': '{{"title": "People Create"}}',
            'templates/person_show.pt': '{{"title": "Person Show"}}',
            'templates/person_update.pt': '{{"title": "Person Update",'
                                          '"form_class": "{form_class}"}}',
            # custom templates
            'templates/person_custom_list.pt': '{{"title": "People Custom List"}}',
            'templates/person_custom_create.pt': '{{"title": "People Custom Create"}},'
                                                 '"form_class": "{form_class}"}}',
            'templates/person_custom_show.pt': '{{"title": "Person Custom Show"}}',
            'templates/person_custom_update.pt': '{{"title": "Person Custom Update", '
                                          '"form_class": "{form_class}"}}'
        }

        def __init__(self, info):
            pass

        def __call__(self, value, system):
            renderer = system['renderer_name']
            response = self.responses[renderer]
            if 'form' in value:
                response = response.format(
                    form_class=value['form'].schema.__class__.__name__)
            return response

    def setUp(self):
        super(TestModelView, self).setUp()
        self.config.add_renderer('.pt', self.TestRenderer)

        person = Person(name="Mr Smith", age=23)
        person.save()
        SASession.flush()

    def test_view_registration(self):
        """
        Check that all views (list, create, show, update, delete) are
        registered by default
        """
        class PersonViews(ModelView):
            ModelFactoryClass = PersonModelFactory
            ModelFormClass = PersonForm
            base_url_override = 'people'

        PersonViews.include(self.config)
        testapp = TestApp(self.config.make_wsgi_app())

        # list
        response = testapp.get('/people/')
        response.mustcontain('People List')

        # create
        response = testapp.get('/people/add')
        response.mustcontain('People Create')

        # show
        response = testapp.get('/people/1')
        response.mustcontain('Person Show')

        # update
        response = testapp.get('/people/1/edit')
        response.mustcontain('Person Update')

        # delete
        request = testing.DummyRequest()
        csrf_token = request.session.get_csrf_token()
        response = testapp.post('/people/1/delete', {'csrf_token': csrf_token})
        self.assertEqual(response.status_code, 302)

    def test_only_requested_views_are_registered(self):
        """
        Test that only views within the enabled_views list are created and
        exposed
        """
        class PersonViews(ModelView):
            ModelFactoryClass = PersonModelFactory
            ModelFormClass = PersonForm
            enabled_views = (ModelView.LIST, ModelView.CREATE, ModelView.UPDATE)
            base_url_override = 'people'

        PersonViews.include(self.config)
        testapp = TestApp(self.config.make_wsgi_app())

        # list
        response = testapp.get('/people/')
        response.mustcontain('People List')

        # create
        response = testapp.get('/people/add')
        response.mustcontain('People Create')

        # show
        self.assertRaises(HTTPNotFound, testapp.get, '/people/1')

        # update
        response = testapp.get('/people/1/edit')
        response.mustcontain('Person Update')

        # delete
        request = testing.DummyRequest()
        csrf_token = request.session.get_csrf_token()
        self.assertRaises(HTTPNotFound, testapp.post, '/people/1/delete',
                          {'csrf_token': csrf_token})

    def test_update_view_uses_update_form_override_if_specified(self):
        class PersonViews(ModelView):
            ModelFactoryClass = PersonModelFactory
            ModelFormClass = PersonForm
            ModelUpdateFormClass = PersonUpdateForm
            base_url_override = 'people'

        PersonViews.include(self.config)
        testapp = TestApp(self.config.make_wsgi_app())

        # update
        response = testapp.get('/people/1/edit')
        response.mustcontain('PersonUpdateForm')

    def test_renderer_overrides_work_on_all_views(self):
        class PersonViews(ModelView):
            ModelFactoryClass = PersonModelFactory
            ModelFormClass = PersonForm
            base_url_override = 'people'

            list_view_renderer = 'templates/person_custom_list.pt'
            create_view_renderer = 'templates/person_custom_create.pt'
            show_view_renderer = 'templates/person_custom_show.pt'
            update_view_renderer = 'templates/person_custom_update.pt'

        PersonViews.include(self.config)
        testapp = TestApp(self.config.make_wsgi_app())

        # list
        response = testapp.get('/people/')
        response.mustcontain('People Custom List')

        # create
        response = testapp.get('/people/add')
        response.mustcontain('People Custom Create')

        # show
        response = testapp.get('/people/1')
        response.mustcontain('Person Custom Show')

        # update
        response = testapp.get('/people/1/edit')
        response.mustcontain('Person Custom Update')


class TestModelViewResponseCallbacks(FunctionalTestBase):
    def test_create_view_response_override_works(self):
        class PersonViews(ModelView):
            ModelFactoryClass = PersonModelFactory
            ModelFormClass = PersonForm
            base_url_override = 'people'

            @classmethod
            def post_save_response(cls, request, record):
                return HTTPFound(request.route_url('person',
                                                   traverse=(record.id,)))
            # NOTE: just overriding the function doesnt work
            post_create_response_callback = post_save_response

        PersonViews.include(self.config)
        testapp = TestApp(self.config.make_wsgi_app())

        request = testing.DummyRequest()
        params = {
            'name': 'Mr Smith',
            'age': '22',
            'csrf_token': request.session.get_csrf_token()}
        response = testapp.post('/people/add', params)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location,
                         '{0}/people/1'.format(self.application_url))

    def test_update_view_response_override_works(self):
        class PersonViews(ModelView):
            ModelFactoryClass = PersonModelFactory
            ModelFormClass = PersonForm
            base_url_override = 'people'

            @classmethod
            def post_save_response(cls, request, record):
                return HTTPFound(request.route_url('person',
                                                   traverse=(record.id,)))
            # NOTE: just overriding the function doesnt work
            post_update_response_callback = post_save_response

        person = Person(name='Mrs Smith', age=25)
        SASession.add(person)
        SASession.flush()

        PersonViews.include(self.config)
        testapp = TestApp(self.config.make_wsgi_app())

        request = testing.DummyRequest()
        params = {
            'name': 'Mrs Jane Smith',
            'age': '22',
            'csrf_token': request.session.get_csrf_token()}
        url = '/people/{0}/edit'.format(person.id)
        response = testapp.post(url, params)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location,
                         '{0}/people/1'.format(self.application_url))

    def test_delete_view_response_override_works(self):
        class PersonViews(ModelView):
            ModelFactoryClass = PersonModelFactory
            ModelFormClass = PersonForm
            base_url_override = 'people'

            @classmethod
            def post_save_response(cls, request, record):
                return HTTPFound(request.route_url('person',
                                                   traverse=('2', 'edit')))
            post_delete_response_callback = post_save_response

        person = Person(name='Mr Smith', age=25)
        SASession.add(person)
        SASession.flush()

        PersonViews.include(self.config)
        testapp = TestApp(self.config.make_wsgi_app())

        request = testing.DummyRequest()
        params = {'csrf_token': request.session.get_csrf_token()}
        url = '/people/{0}/delete'.format(person.id)
        response = testapp.post(url, params)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location,
                         '{0}/people/2/edit'.format(self.application_url))


class TestLogin(TestBase):
    def setUp(self):
        super(TestLogin, self).setUp()
        self.config.add_route('login', '/login')
        pwd_context.load({'schemes': ['des_crypt']})
        user = BaseUser(account_id='admin@example.com', password='admin')
        user.save()
        SASession.flush()

    def test_login_GET_request(self):
        from views import user_login
        request = testing.DummyRequest()
        request.method = 'GET'
        context = BaseRootFactory(request)
        response = user_login(context, request)
        self.assertIn('csrf_token', response)
        self.assertIn('form', response)

    def test_login_returns_bad_request_if_no_csrf_token(self):
        from views import user_login
        request = testing.DummyRequest()
        request.method = 'POST'
        context = BaseRootFactory(request)
        response = user_login(context, request)
        self.assertEqual(response.status_code, 400)

    def test_login_POST_with_valid_credentials(self):
        from views import user_login
        request = testing.DummyRequest()
        request.method = 'POST'
        values = [
            ('csrf_token', request.session.get_csrf_token()),
            ('account_id', 'admin@example.com'),
            ('password', 'admin'),
        ]
        request.POST = MultiDict(values)
        context = BaseRootFactory(request)
        response = user_login(context, request)
        self.assertIsInstance(response, HTTPFound)

    def test_login_POST_with_invalid_credentials(self):
        from views import user_login
        request = testing.DummyRequest()
        request.method = 'POST'
        values = [
            ('csrf_token', request.session.get_csrf_token()),
            ('account_id', 'admin@example.com'),
            ('password', 'wrong'),
        ]
        request.POST = MultiDict(values)
        context = BaseRootFactory(request)
        response = user_login(context, request)
        self.assertIn('csrf_token', response)
        self.assertIn('form', response)
