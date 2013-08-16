import colander
from deform.widget import CheckboxWidget, TextAreaWidget, PasswordWidget


class UserLoginForm(colander.MappingSchema):
    account_id = colander.SchemaNode(
        colander.String(encoding='utf-8'), title='Account ID')
    password = colander.SchemaNode(
        colander.String(encoding='utf-8'), widget=PasswordWidget())
