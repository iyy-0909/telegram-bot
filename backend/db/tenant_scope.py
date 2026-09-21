from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session, with_loader_criteria

from auth.tenant import current_tenant_is_admin, current_tenant_user_id


_registered = False


_OWNED_REFERENCE_RULES = {
    "ChannelRule": (("account_id", "Account"), ("clone_task_id", "CloneTask")),
    "AccountAutoReplyState": (("account_id", "Account"),),
    "NotificationAccountSetting": (("account_id", "Account"),),
    "ContentTemplate": (("parent_id", "ContentTemplate"),),
    "CloneTask": (
        ("account_id", "Account"),
        ("bot_id", "BotAccount"),
        ("ai_prompt_template_id", "AiPromptTemplate"),
        ("selected_head_template_group_id", "ContentTemplate"),
        ("selected_body_template_group_id", "ContentTemplate"),
        ("selected_footer_template_group_id", "ContentTemplate"),
        ("selected_filter_template_group_id", "ContentTemplate"),
        ("selected_link_template_group_id", "ContentTemplate"),
        ("selected_contact_template_group_id", "ContentTemplate"),
        ("selected_head_template_id", "ContentTemplate"),
        ("selected_body_template_id", "ContentTemplate"),
        ("selected_footer_template_id", "ContentTemplate"),
    ),
    "ListenerTask": (
        ("clone_task_id", "CloneTask"),
        ("account_id", "Account"),
        ("bot_id", "BotAccount"),
        ("ai_prompt_template_id", "AiPromptTemplate"),
        ("selected_head_template_group_id", "ContentTemplate"),
        ("selected_body_template_group_id", "ContentTemplate"),
        ("selected_footer_template_group_id", "ContentTemplate"),
        ("selected_filter_template_group_id", "ContentTemplate"),
        ("selected_link_template_group_id", "ContentTemplate"),
        ("selected_contact_template_group_id", "ContentTemplate"),
        ("selected_head_template_id", "ContentTemplate"),
        ("selected_body_template_id", "ContentTemplate"),
        ("selected_footer_template_id", "ContentTemplate"),
    ),
    "SentMessage": (("task_id", "CloneTask"),),
    "ListenerSentMessage": (("listener_task_id", "ListenerTask"),),
    "CloneSendEvent": (("task_id", "CloneTask"), ("bot_id", "BotAccount")),
    "ListenerSendEvent": (("task_id", "ListenerTask"), ("account_id", "Account"), ("bot_id", "BotAccount")),
    "BulkReplaceJobItem": (("job_id", "BulkReplaceJob"),),
    "TargetBotBinding": (("bot_id", "BotAccount"),),
    "MyChannel": (("bot_id", "BotAccount"),),
    "SearchBot": (("account_id", "Account"),),
    "SearchBotChannelSubmission": (
        ("search_bot_id", "SearchBot"),
        ("my_channel_id", "MyChannel"),
        ("account_id", "Account"),
    ),
    "SupportBot": (("bot_id", "BotAccount"),),
    "SupportCustomer": (("support_bot_id", "SupportBot"),),
    "SupportConversation": (("support_bot_id", "SupportBot"), ("customer_id", "SupportCustomer")),
    "SupportMessage": (
        ("support_bot_id", "SupportBot"),
        ("conversation_id", "SupportConversation"),
        ("customer_id", "SupportCustomer"),
    ),
    "SupportCustomerTag": (("customer_id", "SupportCustomer"), ("tag_id", "SupportTag")),
    "ControlAckAlert": (
        ("support_bot_id", "SupportBot"),
        ("customer_id", "SupportCustomer"),
        ("conversation_id", "SupportConversation"),
    ),
}


def _owned_models():
    from db import models

    return tuple(
        mapper.class_
        for mapper in models.Base.registry.mappers
        if hasattr(mapper.class_, "owner_user_id")
    )


def _model_map():
    return {model.__name__: model for model in _owned_models()}


def _referenced_owner_ids(session, instance):
    model_map = _model_map()
    owner_ids = set()
    missing = []
    database_inspector = inspect(session.get_bind())
    strict = current_tenant_user_id() is not None
    for field_name, referenced_model_name in _OWNED_REFERENCE_RULES.get(type(instance).__name__, ()):
        reference_id = getattr(instance, field_name, None)
        if reference_id in (None, "", 0, "0"):
            continue
        referenced_model = model_map[referenced_model_name]
        if not database_inspector.has_table(referenced_model.__tablename__):
            continue
        referenced_row = session.execute(
            select(referenced_model.id, referenced_model.owner_user_id).where(
                referenced_model.id == int(reference_id)
            )
        ).first()
        if referenced_row is None:
            missing.append(field_name)
            continue
        referenced_owner = referenced_row[1]
        if referenced_owner is None:
            if strict:
                missing.append(field_name)
            continue
        owner_ids.add(int(referenced_owner))
    return owner_ids, missing


def _apply_tenant_scope(execute_state):
    owner_user_id = current_tenant_user_id()
    if owner_user_id is None or current_tenant_is_admin():
        return

    statement = execute_state.statement
    if execute_state.is_select:
        for model in _owned_models():
            statement = statement.options(
                with_loader_criteria(
                    model,
                    model.owner_user_id == owner_user_id,
                    include_aliases=True,
                )
            )
        execute_state.statement = statement
        return

    if execute_state.is_update or execute_state.is_delete:
        table = getattr(statement, "table", None)
        if table is not None and "owner_user_id" in table.c:
            execute_state.statement = statement.where(
                table.c.owner_user_id == owner_user_id
            )


def _assign_and_protect_owner(session, _flush_context, _instances):
    owner_user_id = current_tenant_user_id()
    is_admin = current_tenant_is_admin()
    if owner_user_id is not None:
        for instance in session.new:
            if not hasattr(type(instance), "owner_user_id"):
                continue
            assigned_owner = getattr(instance, "owner_user_id", None)
            if assigned_owner is None:
                instance.owner_user_id = owner_user_id
            elif not is_admin and int(assigned_owner) != owner_user_id:
                raise PermissionError("不能为其他用户创建资源")

    for instance in tuple(session.new) + tuple(session.dirty):
        if not hasattr(type(instance), "owner_user_id"):
            continue
        referenced_owners, missing_references = _referenced_owner_ids(session, instance)
        assigned_owner = getattr(instance, "owner_user_id", None)
        if assigned_owner is None and len(referenced_owners) == 1:
            assigned_owner = referenced_owners.pop()
            instance.owner_user_id = assigned_owner
        if assigned_owner is None:
            continue
        if missing_references:
            raise PermissionError(
                "关联资源不存在或未完成归属迁移: " + ",".join(missing_references)
            )
        if referenced_owners and referenced_owners != {int(assigned_owner)}:
            raise PermissionError("不能跨账号关联资源")

    if owner_user_id is None or is_admin:
        return

    for instance in session.dirty:
        if not hasattr(type(instance), "owner_user_id"):
            continue
        owner_state = inspect(instance).attrs.owner_user_id
        if owner_state.history.has_changes() and getattr(instance, "owner_user_id", None) != owner_user_id:
            raise PermissionError("不能转移其他用户资源")


def register_tenant_scope():
    global _registered
    if _registered:
        return
    event.listen(Session, "do_orm_execute", _apply_tenant_scope)
    event.listen(Session, "before_flush", _assign_and_protect_owner)
    _registered = True


register_tenant_scope()
