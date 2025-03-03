# app/models/enums.py
import enum
from sqlalchemy import Enum as SAEnum

class EntityType(str, enum.Enum):
    CHARACTER = "character"
    OBJECT = "object"

class CharacterType(str, enum.Enum):
    PLAYER = "player"
    AGENT = "agent"

class ObjectType(str, enum.Enum):
    GENERIC = "generic"

class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"

class EventType(str, enum.Enum):
    MESSAGE = "message"
    MOVEMENT = "movement"
    INTERACTION = "interaction"
    SYSTEM = "system"
    EMOTE = "emote"
    QUEST = "quest"
    COMBAT = "combat"
    TRADE = "trade"
    INVENTORY = "inventory"
    SKILL = "skill"

class EventScope(str, enum.Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    GLOBAL = "global"
