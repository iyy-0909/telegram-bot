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
from db.models import SupportConversation
from db.models import SupportCustomer
from db.models import SupportCustomerTag
from db.models import SupportMessage
from db.models import SupportQuickReply
from db.models import SupportSetting
from db.models import SupportTag

Base.metadata.create_all(bind=engine)

print("数据库初始化完成")
