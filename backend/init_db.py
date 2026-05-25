from db.database import Base
from db.database import engine

from db.models import ChannelRule
from db.models import Account
from db.models import CloneTask
from db.models import SentMessage
from db.models import ListenerTask
from db.models import ListenerSentMessage
from db.models import ContentTemplate
from db.models import CloneSendEvent
from db.models import ListenerSendEvent

Base.metadata.create_all(bind=engine)

print("数据库初始化完成")
