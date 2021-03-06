from sqlalchemy import (
    Column,
    Integer,
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
    synonym,
    backref,
)
from zope.sqlalchemy import ZopeTransactionExtension
from slugify import slugify
from .auth import pwd_context

SASession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))


def prettify(value):
    return ' '.join([w.capitalize() for w in value.split('_')])


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

    @property
    def __prettyname__(self):
        return prettify(self.__name__)


Base = declarative_base(cls=Model)

user_group = Table(
    'user_groups', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('group_id', Integer, ForeignKey('groups.id')),
)


def generate_slug(column, value, unique_query):
    i = 0
    base_slug = slugify(value)
    slug = base_slug
    while unique_query.filter(column == slug).count() > 0:
        i += 1
        slug = "{0}-{1}".format(base_slug, i)
    return slug


def set_slug(mapper, connection, target):
    target_column = mapper.class_.slug_target_column()
    source_column = mapper.class_.slug_source_column()
    slug = generate_slug(
        target_column, target.__getattribute__(
            source_column.name), target.slug_unique_query())
    target.__setattr__(target_column.name, slug)


class Slugable(object):
    def slug_unique_query(self):
        raise NotImplementedError

    @classmethod
    def slug_target_column(cls):
        return cls.slug

    @classmethod
    def slug_source_column(cls):
        return cls.name


def group_finder(user_id, request):
    try:
        # todo: join with groups
        user = BaseUser.query().filter(BaseUser.id == user_id).one()
    except NoResultFound:
        return None
    else:
        groups = ['g:{0}'.format(g.name) for g in user.groups]
        groups.append('u:{0}'.format(user_id))
        return groups


class BaseUser(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    account_id = Column(String(100), unique=True, nullable=False)
    _password = Column(String(255), nullable=False)
    is_active = Column(Boolean(), nullable=False, default=False)
    groups = relationship('BaseGroup', secondary=user_group,
                          backref=backref('users', enable_typechecks=False),
                          enable_typechecks=False)

    def check_password(self, against):
        return pwd_context.verify(against, self._password)

    def to_dict(self):
        data = super(BaseUser, self).to_dict()
        # password can only be set, not edited
        data['password'] = None
        data['group_names'] = self.group_names
        return data

    def update_from_dict(self, data):
        # if password is blank, remove its key from data
        contains_password = 'password' in data
        if contains_password and not data['password']:
            del data['password']
        #elif contains_password:
        #    # encrypt
        #    data['password'] = pwd_context.encrypt(data['password'])
        super(BaseUser, self).update_from_dict(data)

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, value):
        self._password = pwd_context.encrypt(value)

    password = synonym('_password', descriptor=password)

    @property
    def group_names(self):
        return [g.name for g in self.groups]

    @group_names.setter
    def group_names(self, values):
        # todo: check if groups names have changed to optimise
        # get groups in values
        groups = BaseGroup.query().filter(
            BaseGroup.name.in_(values)).all()
        # delete all associations !IMPORTANT: done after the filter so our
        # changes aren't overwritten by the query results
        self.groups = []
        self.groups.extend(groups)


class BaseGroup(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)


class ModelFactory(object):
    __name__ = ''
    __parent__ = None
    __route_name__ = None

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
            record.request = self.request
            self.post_get_item(record)
            return record

    def post_get_item(self, item):
        """Called after __getitem__ to manipulate the returned item e.g. attach
        ACL"""
        pass

    def list_url(self, request):
        return request.route_url(
            self.__route_name__, traverse=())

    def create_url(self, request):
        return request.route_url(
            self.__route_name__, traverse=('add',))

    def show_url(self, request, record):
        return request.route_url(self.__route_name__, traverse=(record.id,))

    def update_url(self, request, record):
        return request.route_url(self.__route_name__,
                                 traverse=(record.id, 'edit'))

    def delete_url(self, request, record):
        return request.route_url(self.__route_name__,
                                 traverse=(record.id, 'delete'))

    @property
    def __prettyname__(self):
        return prettify(self.__name__)


class BaseRootFactory(object):
    __name__ = None
    __parent__ = None
    __acl__ = []
    __factories__ = {}

    def __init__(self, request):
        self.request = request

    def __getitem__(self, key):
        try:
            factory = self.__factories__[key]
        except KeyError:
            raise
        else:
            item = factory(self.request)
            item.__name__ = key
            item.__parent__ = self
            return item