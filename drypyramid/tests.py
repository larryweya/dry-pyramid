import unittest
from pyramid import testing, traversal
from pyramid.paster import bootstrap
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Text,
    String,
    Boolean,
    Table,
    ForeignKey,
)
from sqlalchemy.orm import (
    relationship,
)
from drypyramid.models import (
    SASession, Base, ModelFactory
)


person_hobby = Table(
    'person_hobby', Base.metadata,
    Column('person_id', Integer, ForeignKey('person.id')),
    Column('hobby_id', Integer, ForeignKey('hobby.id')),
)


class Person(Base):
    __tablename__ = 'person'
    __pluralized__ = 'people'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    age = Column(Integer, nullable=False)
    hobbies = relationship('Hobby', secondary=person_hobby, backref='people')


class Hobby(Base):
    __tablename__ = 'hobby'
    __pluralized__ = 'hobbies'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)


class PersonModelFactory(ModelFactory):
    ModelClass = Person

    def on_get_item(self, item):
        self.on_get_item_called = True


class TestBase(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        self.config.add_route('site', '/*traverse')
        engine = create_engine('sqlite:///:memory:', echo=True)
        SASession.configure(bind=engine)
        Base.metadata.create_all(engine)

    def tearDown(self):
        SASession.remove()
        testing.tearDown()


class TestModel(TestBase):
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