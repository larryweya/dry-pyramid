import colander
from deform.widget import (
    CheckboxWidget, PasswordWidget, CheckboxChoiceWidget
    )


class UserLoginForm(colander.MappingSchema):
    account_id = colander.SchemaNode(
        colander.String(encoding='utf-8'), title='Account ID')
    password = colander.SchemaNode(
        colander.String(encoding='utf-8'), widget=PasswordWidget())


class UserGroups(colander.SequenceSchema):
    name = colander.SchemaNode(
        colander.String(encoding='utf-8'), title="Group")


class BaseUserForm(colander.MappingSchema):
    account_id = colander.SchemaNode(
        colander.String(encoding='utf-8'))
    password = colander.SchemaNode(
        colander.String(encoding='utf-8'), widget=PasswordWidget())
    confirm_password = colander.SchemaNode(
        colander.String(encoding='utf-8'), widget=PasswordWidget())
    is_active = colander.SchemaNode(
        colander.Boolean(), title="Active",
        description="Make this user active/inactive",
        widget=CheckboxWidget())
    group_names = UserGroups(widget=CheckboxChoiceWidget(
        values=[('su', 'Admin')]))

    def validator(self, node, cstruct):
        if cstruct['password'] != cstruct['confirm_password']:
            exc = colander.Invalid(
                self, 'Password and confirmation password must match')
            exc['confirm_password'] = 'Confirm password doesnt match.'
            raise exc


class BaseUserUpdateForm(BaseUserForm):
    password = colander.SchemaNode(
        colander.String(encoding='utf-8'), widget=PasswordWidget(),
        description="Leave blank to leave unchanged", missing=None)
    confirm_password = colander.SchemaNode(
        colander.String(encoding='utf-8'), widget=PasswordWidget(),
        missing=None)