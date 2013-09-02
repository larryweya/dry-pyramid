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
from .views import ModelView


person_hobby = Table(
    'person_hobby', Base.metadata,
    Column('person_id', Integer, ForeignKey('people.id')),
    Column('hobby_id', Integer, ForeignKey('hobbies.id')),
)


class Person(Base):
    __tablename__ = 'people'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    age = Column(Integer, nullable=False)
    hobbies = relationship('Hobby', secondary=person_hobby, backref='people')


class Hobby(Base):
    __tablename__ = 'hobbies'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)


class PersonModelFactory(ModelFactory):
    ModelClass = Person

    def on_get_item(self, item):
        self.on_get_item_called = True


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
    def test_create_url(self):
        request = testing.DummyRequest()
        factory = PersonModelFactory(request)
        url = factory.create_url(request)
        expected_url = "%s/people/add" % request.application_url
        self.assertEqual(url, expected_url)

    def test_create_url_with_custom_action_name(self):
        request = testing.DummyRequest()
        factory = PersonModelFactory(request)
        url = factory.create_url(request, 'create')
        expected_url = "%s/people/create" % request.application_url
        self.assertEqual(url, expected_url)

    def test_get_item_calls_on_get_item(self):
        request = testing.DummyRequest()
        factory = PersonModelFactory(request)
        # create a Person
        person = Person(name="Mr Smith", age=23)
        person.save()
        factory.__getitem__('1')
        self.assertTrue(factory.on_get_item_called)


class TestModelView(TestBase):
    class TestRootFactory(BaseRootFactory):
        #__factories__ = {
        #    Person.__tablename__: PersonModelFactory
        #}
        pass

    class TestRenderer(object):
        responses = {
            'templates/people_list.pt': '{{"title": "People List"}}',
            'templates/people_create.pt': '{{"title": "People Create"}}',
            'templates/people_show.pt': '{{"title": "Person Show"}}',
            'templates/people_update.pt': '{{"title": "Person Update",'
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

    class PersonForm(colander.MappingSchema):
        name = colander.SchemaNode(colander.String(encoding='utf-8'))
        age = colander.SchemaNode(colander.Integer())

    class PersonUpdateForm(colander.MappingSchema):
        class HobbiesSchema(colander.SequenceSchema):
            name = colander.SchemaNode(
                colander.String(encoding='utf-8'), title="Hobby")
        hobbies = HobbiesSchema(values=[
            ('su', 'Superuser'),
            ('billing', 'Billing'),
            ('customer_care', 'Customer Care')
        ])

    def setUp(self):
        super(TestModelView, self).setUp()
        self.config.set_root_factory(self.TestRootFactory)
        session_factory = testing.DummySession
        self.config.set_session_factory(session_factory)
        self.config.add_renderer('.pt', self.TestRenderer)

        person = Person(name="Mr Smith", age=23)
        person.save()
        SASession.flush()

    def test_view_registration(self):
        """
        Check that all views (list, create, show, update, delete) are
        registered by default
        """
        class PersonView(ModelView):
            ModelFactoryClass = PersonModelFactory
            ModelFormClass = self.PersonForm

        PersonView.include(self.config)
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
        class PersonView(ModelView):
            ModelFactoryClass = PersonModelFactory
            ModelFormClass = self.PersonForm
            enabled_views = (ModelView.LIST, ModelView.CREATE, ModelView.UPDATE)

        PersonView(self.config)
        testapp = TestApp(self.config.make_wsgi_app())

        # list
        response = testapp.get('/people')
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
        class PersonView(ModelView):
            ModelFactoryClass = PersonModelFactory
            ModelFormClass = self.PersonForm
            ModelUpdateFormClass = self.PersonUpdateForm

        PersonView(self.config)
        testapp = TestApp(self.config.make_wsgi_app())

        # update
        response = testapp.get('/people/1/edit')
        response.mustcontain('PersonUpdateForm')

    def test_renderer_overrides_work_on_all_views(self):
        class PersonView(ModelView):
            ModelFactoryClass = PersonModelFactory
            ModelFormClass = self.PersonForm

            list_view_renderer = 'templates/person_custom_list.pt'
            create_view_renderer = 'templates/person_custom_create.pt'
            show_view_renderer = 'templates/person_custom_show.pt'
            update_view_renderer = 'templates/person_custom_update.pt'

        PersonView(self.config)
        testapp = TestApp(self.config.make_wsgi_app())

        # list
        response = testapp.get('/people')
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


class TestLogin(TestBase):
    def setUp(self):
        super(TestLogin, self).setUp()
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
