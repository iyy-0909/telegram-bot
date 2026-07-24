from init_db import init_db
from sqlalchemy import text

from db.database import engine


if __name__ == "__main__":
    init_db()
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE search_bot_channel_submissions "
            "SET permission_status = 'unverified', "
            "permission_last_error = '历史提交记录，尚未通过 Telegram 自动回查' "
            "WHERE permission_status = 'pending' "
            "AND permissions_applied_at IS NULL "
            "AND (applied_admin_rights_json IS NULL OR applied_admin_rights_json = '' OR applied_admin_rights_json = '{}')"
        ))
    print("search bot migration complete")
