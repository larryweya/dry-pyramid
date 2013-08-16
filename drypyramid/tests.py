import unittest

from sqlalchemy import (
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
from drypyramid.models import Base


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


class TestBaseModel(unittest.TestCase):
    def setUp(self):
        super(TestBaseModel, self).setUp()

    def tearDown(self):
        super(TestBaseModel, self).setUp()

    def test_something(self):
        self.assertEqual(1, 1)

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