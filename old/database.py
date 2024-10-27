from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session
from sqlalchemy import String, UniqueConstraint, DateTime, ForeignKey
from typing import List, Self
import enum

import time

from argon2 import PasswordHasher
import argon2.exceptions

import logging
logger = logging.getLogger(__name__)

# logging.basicConfig(format="{name}:{message}", style="{",level=logging.DEBUG)

ph = PasswordHasher()

engine = create_engine("sqlite:///main.db")

class Base(DeclarativeBase):
    pass

class Friendship(Base):
    __tablename__ = "friendships"
    first: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key = True)
    second: Mapped[int] = mapped_column(ForeignKey("users.id"))

    friend: Mapped["User"] = relationship(foreign_keys = [second], back_populates="friends")

class User(Base):
    __tablename__ = "users" 
    id: Mapped[int] = mapped_column(primary_key = True)
    username: Mapped[str] = mapped_column(String(20))
    password: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool]
    is_teacher: Mapped[bool]
    is_active: Mapped[bool] = mapped_column(default=True)

    posts: Mapped[List["Post"]] = relationship(back_populates="author", cascade="all, delete-orphan")
    
    friends: Mapped[List["Friendship"]] = relationship(foreign_keys = [Friendship.second], back_populates="friend", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("username"), UniqueConstraint("email"))

class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(primary_key = True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str]
    published_datetime: Mapped[int]
    is_visible: Mapped[bool]

    @staticmethod
    def smuggle(item: Self) -> dict:
        '''Smuggle displayed content outside the session boundary'''
        logger.debug(f"time = {item.published_datetime}")
        return {
            "content": item.content,
            "username": item.author.username,
            "published_datetime": time.strftime(
                "%d %B %Y - %H:%M",
                time.gmtime(int(item.published_datetime)))
        }

    author: Mapped["User"] = relationship(back_populates="posts")



class _AuthenticationResult(enum.Enum):
    Success = enum.auto()
    NoSuchUser = enum.auto()
    VerifyMismatch = enum.auto()

    def __bool__(self):
        return self == _AuthenticationResult.Success

class AuthenticationResult:
    def __init__(self, enum: _AuthenticationResult, id: int|None):
        self.enum = enum
        self.id = id

    def __bool__(self):
        return bool(self.enum)

def authenticate(username: str, provided_password: str) -> AuthenticationResult:
    '''Given a provided username and plaintext password verify that the provided details check out'''
    with Session(engine) as session:
        user = session.execute(
            select(User.password, User.id)
            .with_only_columns(User.password, User.id)
            .where(User.username == username)
        ).one_or_none()
        
        if user is None:
            return AuthenticationResult(_AuthenticationResult.NoSuchUser, None)
        try:
            ph.verify(user.password, provided_password)
        except argon2.exceptions.VerifyMismatchError:
            return AuthenticationResult(_AuthenticationResult.VerifyMismatch, None)

        return AuthenticationResult(_AuthenticationResult.Success, user.id)

class RegistrationResult(enum.Enum):
    Success = enum.auto()
    UsernameAlreadyExists = enum.auto()
    EmailAlreadyExists = enum.auto()
    UnknownError = enum.auto()

    def __bool__(self):
        return self==RegistrationResult.Success

def register(username: str, password: str, email: str) -> RegistrationResult:
    '''Attempts to create a user based on the information provided'''
    with Session(engine) as session:
        if session.scalar(
            select(1)
            .where(User.email == email)
            .limit(1)) is not None:
            logger.debug("EmailAlreadyExists")
            return RegistrationResult.EmailAlreadyExists

        if session.scalar(
            select(1)
            .where(User.username == username)
            .limit(1)) is not None:
            logger.debug("UsernameAlreadyExists")
            return RegistrationResult.UsernameAlreadyExists

        else:
            
            try:
                session.add(
                    User(
                        username = username,
                        password = ph.hash(password),
                        email = email,
                        is_admin = False,
                        is_teacher = True
                    )
                )
                session.commit()
            except Exception as err:
                logger.error(f"Error in registration: {err}")
                return RegistrationResult.UnknownError

            logger.debug("RegistrationSuccess")
            return RegistrationResult.Success

def trusting_post(author_id: int, content: str):
    '''Blindly trusts that the callee has authenticated the author correctly and can trust the author actually sent this message'''
    with Session(engine) as session:
        session.add(
            Post(
                author_id = author_id,
                content = content,
                published_datetime = time.time()
            )
        )
        session.commit()

def user_exists(user_id: int):
    with Session(engine) as session:
        return session.scalar(select(1).where(User.id == user_id).limit(1)) is not None

def create_friendship(first_id: int, second_id: int):
    with Session(engine) as session:
        session.add(
            Friendship(
                first = first_id,
                second = second_id
            )
        )

        # This needs to be done to make querying friendships easier to code and (I think)
        # faster to query at the pretty small cost of memory compared to length
        session.add(
            Friendship(
                first = second_id,
                second = first_id
            )
        )
        session.commit()

def generate_feed(user_id: int, size: int = 100):
    with Session(engine) as session:
        subquery = select(Friendship.second).where(Friendship.first == user_id)
        return [Post.smuggle(post[0]) for post in session.execute(
                select(Post)
                .where(Post.author_id.in_(subquery))
                .limit(size)
            )]
