from sqlalchemy import (
    Column,
    Integer,
    Text,
    String,
    Boolean,
    Table,
    ForeignKey,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    relationship,
)
from pyramid.security import (
    Allow,
    Deny,
    Everyone,
    Authenticated,
    ALL_PERMISSIONS,
    DENY_ALL,
)
from zope.sqlalchemy import ZopeTransactionExtension
from .auth import pwd_context

SASession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))


class Model(object):
    def save(self):
        SASession.add(self)

    @classmethod
    def query(cls, **kwargs):
        return SASession.query(cls, **kwargs)

    def delete(self):
        SASession.delete(self)

    @classmethod
    def create_from_dict(cls, data):
        record = cls.__call__()
        record.update_from_dict(data)
        return record

    def to_dict(self):
        return dict([(c.name, getattr(self, c.name)) for c in
                     self.__mapper__.columns])

    def update_from_dict(self, data):
        [setattr(self, key, data.get(key)) for key in data]

    def update_url(self, request):
        raise NotImplementedError()

    def delete_url(self, request):
        raise NotImplementedError()


Base = declarative_base(cls=Model)

user_group = Table(
    'user_group', Base.metadata,
    Column('user_id', Integer, ForeignKey('user.id')),
    Column('group_id', Integer, ForeignKey('group.id')),
)


def group_finder(user_id, request):
    try:
        # todo: join with groups
        user = User.query().filter(User.id == user_id).one()
    except NoResultFound:
        return None
    else:
        groups = ['g:{0}'.format(g.name) for g in user.groups]
        groups.append('u:{0}'.format(user_id))
        return groups


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    account_id = Column(String(100), unique=True, nullable=False)
    password = Column(String(100), nullable=False)
    is_active = Column(Boolean(), nullable=False, default=False)
    groups = relationship('Group', secondary=user_group, backref='users')

    def check_password(self):
        raise NotImplementedError()

    def update_url(self, request):
        return request.route_url('site', traverse=('users', self.id, 'edit'))

    def delete_url(self, request):
        return request.route_url('site', traverse=('users', self.id, 'delete'))

    def to_dict(self):
        data = super(User, self).to_dict()
        # password can only be set, not edited
        data['password'] = None
        data['group_names'] = self.group_names
        return data

    def update_from_dict(self, data):
        # if password is blank, remove its key from data
        has_password = 'password' in data
        if has_password and not data['password']:
            del data['password']
        elif has_password:
            # encrypt
            data['password'] = pwd_context.encrypt(data['password'])
        super(User, self).update_from_dict(data)

    @property
    def group_names(self):
        return [g.name for g in self.groups]

    @group_names.setter
    def group_names(self, values):
        # todo: check if groups names have changed
        # get groups in values
        groups = Group.query().filter(
            Group.name.in_(values)).all()
        # delete all associations !IMPORTANT: done after the filter so our
        # changes aren't overwritten by the query results
        self.groups = []
        self.groups.extend(groups)


class Group(Base):
    __tablename__ = 'group'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)


class ModelFactory(object):
    def __init__(self, request):
        self.request = request

    def __getitem__(self, key):
        try:
            record = self.ModelClass.query().filter_by(
                id=key).one()
        except NoResultFound:
            raise KeyError
        else:
            record.__parent__ = self
            record.__name__ = key
            self.on_get_item(record)
            return record

    def on_get_item(self, item):
        """Called after __getitem__ to manipulate the returned item e.g. attach
        ACL"""
        pass

    def create_url(self, request, action_name='add'):
        return request.route_url(
            'site', traverse=(self.ModelClass.__pluralized__, action_name))