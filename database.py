from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session
from sqlalchemy import UniqueConstraint, ForeignKey, or_, and_, case, union, text
from sqlalchemy.exc import DBAPIError as sql_error
from typing import List, Tuple
import enum

import time

from argon2 import PasswordHasher
import argon2.exceptions as exceptions

import logging
logging.basicConfig()
log = logging.getLogger("database")

ph = PasswordHasher()

engine = create_engine("sqlite:///main.db")

class Base(DeclarativeBase):
    pass

class User(Base):
    '''ORM mapping of the users table'''
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key = True)
    name: Mapped[str]
    password: Mapped[str]
    password_reset_on_next_login: Mapped[bool]
    student_requests_password_change: Mapped[bool]
    is_teacher: Mapped[bool]

    # In future I will likely use this
    # email: Mapped[str]

    wall_posts: Mapped[List["WallPost"]] = relationship(foreign_keys = "WallPost.author_id", cascade = "all, delete-orphan")
    wall_comments: Mapped[List["WallPostComment"]] = relationship(cascade = "all, delete-orphan")

    groups: Mapped[List["GroupMembership"]] = relationship(cascade="all, delete-orphan")
    group_posts: Mapped[List["GroupPost"]] = relationship(cascade = "all, delete-orphan")
    group_comments: Mapped[List["GroupPostComment"]] = relationship(cascade = "all, delete-orphan")

    __table_args__ = (UniqueConstraint("name"),)

class WallPost(Base):
    '''ORM mapping of the WallPost table'''
    __tablename__ = "wall_posts"
    id: Mapped[int] = mapped_column(primary_key = True)
    content: Mapped[str]
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    wall_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    publish_datetime: Mapped[int]
    
    author: Mapped["User"] = relationship(foreign_keys = [author_id], back_populates = "wall_posts")
    wall_owner: Mapped["User"] = relationship(foreign_keys = [wall_id])

    comments: Mapped[List["WallPostComment"]] = relationship(cascade = "all, delete-orphan")

class WallPostComment(Base):
    '''ORM mapping of the WallPostComment table'''
    __tablename__ = "wall_post_comments"
    id: Mapped[int] = mapped_column(primary_key = True)
    content: Mapped[str]
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    post_id: Mapped[int] = mapped_column(ForeignKey("wall_posts.id"))
    publish_datetime: Mapped[int]

    author: Mapped["User"] = relationship(back_populates = "wall_comments")
    post: Mapped["WallPost"] = relationship(back_populates = "comments")

class Friendship(Base):
    '''ORM mapping of the Friendship table'''
    __tablename__ = "friendships"
    first: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key = True)
    second: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key = True)
    is_request: Mapped[bool]

class PrivateMessage(Base):
    '''ORM mapping of the PrivateMessage table'''
    __tablename__ = "private_messages"
    id: Mapped[int] = mapped_column(primary_key = True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str]

    author: Mapped["User"] = relationship(foreign_keys = [author_id])
    recipient: Mapped["User"] = relationship(foreign_keys = [recipient_id])

class Group(Base):
    '''ORM mapping of the Group table'''
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(primary_key = True)
    name: Mapped[str]

    members: Mapped[List["GroupMembership"]] = relationship(cascade = "all, delete-orphan")
    posts: Mapped[List["GroupPost"]] = relationship(cascade = "all, delete-orphan")

class GroupMembership(Base):
    '''ORM mapping of the GroupMembership table'''
    __tablename__ = "group_memberships"
    member_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key = True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), primary_key = True)
    is_admin: Mapped[bool]

    group: Mapped["Group"] = relationship(back_populates="members")
    member: Mapped["User"] = relationship(back_populates="groups")

class GroupPost(Base):
    '''ORM mapping of the GroupPost table'''
    __tablename__ = "group_posts"
    id: Mapped[int] = mapped_column(primary_key = True) 
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    content: Mapped[str]
    publish_datetime: Mapped[int]

    author: Mapped["User"] = relationship(back_populates = "group_posts")
    group: Mapped["Group"] = relationship(back_populates = "posts")

    comments: Mapped[List["GroupPostComment"]] = relationship(cascade = "all, delete-orphan")

class GroupPostComment(Base):
    '''ORM mapping of the GroupPostComment table'''
    __tablename__ = "group_post_comments"
    id: Mapped[int] = mapped_column(primary_key = True)
    content: Mapped[str]
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    post_id: Mapped[int] = mapped_column(ForeignKey("group_posts.id"))
    publish_datetime: Mapped[int]

    author: Mapped["User"] = relationship(back_populates = "group_comments")
    post: Mapped["GroupPost"] = relationship(back_populates = "comments")

def generate_feed(user_id: int) -> List[dict]:
    '''Returns a list of posts that populate a user's main feed on the home page'''
    group_post_query = select(GroupPost, 2).where(GroupPost.group_id.in_(
        select(GroupMembership.group_id).where(GroupMembership.member_id == user_id))
    )

    wall_post_query = select(WallPost, 1).where(or_(
        WallPost.wall_id == user_id,
        WallPost.wall_id.in_(
            select(case(
                (Friendship.first == user_id, Friendship.second),
                else_ = Friendship.first
            ).label("friend_id")).where(
                and_(or_(
                    Friendship.first == user_id,
                    Friendship.second == user_id
                ), Friendship.is_request != True))
        )
    ))

    # TODO: Come up with a better solution.
    # This is really sketchy and only works because of the precise layout of my testing database
    def conv(post):
        if post[-1]==1:
            ret = dict(zip(("id", "content", "author_id", "wall_id", "publish_datetime"),post))
            ret["type"] = "wall"
            return ret
        else:
            ret = dict(zip(("id", "author_id", "group_id", "content", "publish_datetime"),post))
            ret["type"] = "group"
            return ret
        
    joined_query = union(group_post_query, wall_post_query).order_by(text('publish_datetime DESC'))

    with Session(engine) as session:
        return [conv(post) for post in session.execute(joined_query)]

def post_to_wall(author_id: int, content: str, wall_id: int) -> bool:
    '''
    Publish a post to a wall. Assumes the person creating the post is authorised to post on behalf
    of the account referenced by author_id, and that account can post to the wall referenced by wall_id
    Returns true if the post was successfully made
    '''
    post = WallPost(
        content = content,
        author_id = author_id,
        wall_id = wall_id,
        publish_datetime = time.time_ns()
    )
    with Session(engine) as session:
        try:
            session.add(post)
            session.commit()
        except sql_error:
            log.error("Failed to add post to wall")
            log.debug("Post with {author_id=} {wall_id=} {len(content)=} failed to be added to {wall_id}")
            return None 
        
        log.info(f"User with id {author_id} added a post with content length {len(content)} to the wall with id {wall_id}")
        return {
            "content": content,
            "author_id": author_id,
            "wall_id": wall_id,
            "publish_datetime": post.publish_datetime,
            "type": "wall"
        }

def post_to_group(author_id: int, content: str, group_id: int) -> bool:
    '''
    Publish a post to a group. Assumes the person creating the post is authorised to post on behalf
    of the account referenced by author_id, and that account can post to the group referenced by group_id
    Returns true if the post was successfully made
    '''
    post = GroupPost(
            content = content,
            author_id = author_id,
            group_id = group_id,
            publish_datetime = time.time_ns()
    )
    
    with Session(engine) as session:
        try:
            session.add(post)
            session.commit()
        except sql_error:
            log.error("Failed to add post to group")
            log.debug("Post with {author_id=} {wall_id=} {len(content)=} failed to be added to group {group_id}")
            return None 
        
        log.info(f"User with id {author_id} added a post with content length {len(content)} to the group with id {group_id}")
        return {
            "content": content,
            "author_id": author_id,
            "group_id": group_id,
            "publish_datetime": post.publish_datetime,
            "type": "group"
        }

def comment_to_group(author_id: int, content: str, parent_id: int) -> bool:
    '''
    Publish a post to a group. Assumes the person creating the post is authorised to post on behalf
    of the account referenced by author_id, and that account can post to the group referenced by group_id
    Returns true if the post was successfully made
    '''
    post = GroupPostComment(
            content = content,
            author_id = author_id,
            post_id = parent_id,
            publish_datetime = time.time_ns()
    )
    
    with Session(engine) as session:
        try:
            session.add(post)
            session.commit()
        except sql_error:
            log.error("Failed to add comment to group")
            log.debug("Comment with {author_id=} {wall_id=} {len(content)=} failed to be added to group post {parent_id}")
            return None
        
        return {
            "content": content,
            "author_id": author_id,
            "publish_datetime": post.publish_datetime,
        }

def comment_to_wall(author_id: int, content: str, parent_id: int) -> bool:
    '''
    Publish a post to a group. Assumes the person creating the post is authorised to post on behalf
    of the account referenced by author_id, and that account can post to the group referenced by group_id
    Returns true if the post was successfully made
    '''
    post = WallPostComment(
            content = content,
            author_id = author_id,
            post_id = parent_id,
            publish_datetime = time.time_ns()
    )
    
    with Session(engine) as session:
        try:
            session.add(post)
            session.commit()
        except sql_error:
            log.error("Failed to add comment to wall")
            log.debug("Comment with {author_id=} {wall_id=} {len(content)=} failed to be added to wall post {parent_id}")
            return None
        
        return {
            "content": content,
            "author_id": author_id,
            "publish_datetime": post.publish_datetime,
        }

def user_exists(id: int) -> bool:
    '''Checks if a user exists'''
    with Session(engine) as session:
        stmt = select(text("null")).where(User.id == id)
        return session.execute(stmt).one_or_none() is not None

def grab_info_for(id: int) -> Tuple[str, bool] | None:
    '''Kind of stupid name. Grabs the name and whether the user is a teacher'''
    stmt = select(User.name, User.is_teacher).where(User.id == id)
    with Session(engine) as session:
        result = session.execute(stmt).one_or_none()
        if result is None:
            return None

        log.debug(f"{result=}")

        return (result.name, result.is_teacher)

class AuthenticationError(enum.Enum):
    '''Enum describing the failstates of an authentication attempt'''
    UserDoesNotExist = enum.auto()
    IncorrectPassword = enum.auto()

    def __bool__(self) -> bool:
        return False

    def __str__(self) -> str:
        match self:
            case AuthenticationError.UserDoesNotExist:
                return "No user with that username exists"
            case AuthenticationError.IncorrectPassword:
                return "An incorrect password was provided"
            case _:
                return "Unexpected"

def authenticate(username: str, password: str) -> int | AuthenticationError :
    '''Given a username and password, returns the user's id if the password is correct, else an error pinpointing the mistake'''
    with Session(engine) as session:
        stmt = select(User.password, User.id).where(User.name == username).limit(1)
        user = session.execute(stmt).one_or_none()
        if user.password is None:
            return AuthenticationError.UserDoesNotExist
        try:
            ph.verify(user.password, password)
        except exceptions.VerifyMismatchError:
            return AuthenticationError.IncorrectPassword

        return user.id

def register(name: str, password: str):
    '''Attempts to register a user. Returns a bool representing success'''
    if user_exists(name):
        return False
    with Session(engine) as session:
        user = User(
            name = name,
            password = ph.hash(password),
            password_reset_on_next_login = False,
            student_requests_password_change = False,
            is_teacher = False
        )

        try:
            session.add(user)
            session.commit()
        except Exception as e:
            log.debug(e)
            return False

    return True

def are_friends(a_id: int, b_id: int) -> bool:
    '''Checks if two users are friends'''
    stmt = select(Friendship.is_request).where(
        or_(
            and_(
                Friendship.first == a_id, Friendship.second == b_id
            ),
            and_(
                Friendship.first == b_id, Friendship.second == a_id
            )
        )
    )

    with Session(engine) as session:
        res = session.execute(stmt).one_or_none()
        if res is None:
            return False
        else:
            return not res[0]

def posts_to_wall(wall_id: int):
    '''Returns a list of all posts to a walll'''
    stmt = select(WallPost).where(WallPost.wall_id == wall_id).order_by(text('publish_datetime DESC'))
    with Session(engine) as session:
        return list(tag(obj, {"type": "wall"}) for obj in session.scalars(stmt))

def posts_to_group(group_id: int):
    '''Returns a list of all posts to a group'''
    stmt = select(GroupPost).where(GroupPost.group_id == group_id).order_by(text('publish_datetime DESC'))
    with Session(engine) as session:
        return list(tag(post, {"type": "group"}) for post in session.scalars(stmt))

def get_user_by_id(user_id: int):
    '''Get a user object by id'''
    stmt = select(User).where(User.id == user_id)
    with Session(engine) as session:
        return session.execute(stmt).scalar_one_or_none()

def is_group_member(user: int, group_id: int):
    '''Returns a bool representing if a user is a member of a particular group'''
    stmt = select(GroupMembership).where(
        and_(GroupMembership.member_id == user, GroupMembership.group_id == group_id)
    )
    with Session(engine) as session:
        return session.execute(stmt).one_or_none() is not None

def get_friends_of(user: int) -> List[int]:
    '''Return a list of user ids of the user's friends'''
    stmt = select(Friendship.second, Friendship.is_request).where(Friendship.first == user) \
    .union(select(Friendship.first, Friendship.is_request).where(Friendship.second == user))

    with Session(engine) as session:
        return list(session.execute(stmt))

def get_groups_of(user: int) -> List[int]:
    '''Return a list of group ids of the user's groups'''
    stmt = select(GroupMembership.group_id).where(GroupMembership.member_id == user)
    
    with Session(engine) as session:
        return [_[0] for _ in session.execute(stmt)]

class UserSidebarInfo:
    '''Represents the information needed to provide a sidebar entry for a user'''
    def __init__(self, name: str):
        self.name = name


def get_sidebar_user_info(user: int) -> UserSidebarInfo | None:
    '''Gets the information for a sidebar entry for a particular user'''
    stmt = select(User.name).where(User.id == user)

    with Session(engine) as session:
        result = session.execute(stmt).one_or_none()
        if result is None:
            return None
        
        return UserSidebarInfo(name = result[0])

class GroupSidebarInfo:
    '''Represents the information needed to provide a sidebar entry for a group'''
    def __init__(self, group_id: int, name: str):
        self.name = name
        self.group_id = group_id

def get_sidebar_group_info(group: int) -> GroupSidebarInfo | None:
    '''Gets the information for a sidebar entry for a particular group'''
    stmt = select(Group.name).where(Group.id == group)

    with Session(engine) as session:
        result = session.execute(stmt).one_or_none()
        if result is None:
            return None

        return GroupSidebarInfo(group_id = group, name = result[0])

def get_wall_post(id: int):
    '''Gets a wall post by id'''
    stmt = select(WallPost).where(WallPost.id == id)

    with Session(engine) as session:
        return session.scalars(stmt).one_or_none()

def tag(obj, tag: dict):
    '''Helper function to add values to a object functionally. Returns obj but with attrs set'''
    for key,value in tag.items():
        setattr(obj, key, value)

    return obj

def get_group_post(id: int):
    '''Get's a group post by id'''
    stmt = select(GroupPost).where(GroupPost.id == id)

    with Session(engine) as session:
        return tag(session.scalars(stmt).one_or_none(), {"type": "group"})

def get_wall_post_comments(parent_id: int):
    '''Get a list of comments on a wall post'''
    stmt = select(WallPostComment).where(WallPostComment.post_id == parent_id).order_by(text('publish_datetime DESC'))

    with Session(engine) as session:
        return list(session.scalars(stmt))

def get_group_post_comments(parent_id: int):
    '''Gets a list of comments on a group post'''
    stmt = select(GroupPostComment).where(GroupPostComment.post_id == parent_id).order_by(text('publish_datetime DESC'))

    with Session(engine) as session:
        return list(session.scalars(stmt))

def wall_post_owner(post_id: int):
    '''Gets the id of a wall post's wall owneer'''
    stmt = select(WallPost.author_id).where(WallPost.id == post_id)

    with Session(engine) as session:
        return session.execute(stmt).one_or_none()

def group_post_group(post_id: int):
    '''Get's the id of a group post's group'''
    stmt = select(GroupPost.group_id).where(GroupPost.id == post_id)

    with Session(engine) as session:
        return session.execute(stmt).one_or_none()

def can_see_detail_on_post(target_t: str, current_user_id: int, post_id: int) -> bool:
    '''Checks if a user can see a detailed view of a post (equiv. they can see the post at all)'''
    if target_t == "wall":
        post_owner = wall_post_owner(post_id)
        if post_owner is None:
            return False

        return current_user_id == post_owner[0] or are_friends(current_user_id, post_owner[0])

    elif target_t == "group":
        group_id = group_post_group(post_id)
        if group_id is None:
            return False

        return is_group_member(current_user_id, group_id[0])

    return False

def friend_request(requester_id: int, requestee_name: str) -> bool:
    '''Creates a friend request from the requester to a user with name == requestee_name'''
    with Session(engine) as session:
        requestee_id = session.execute(
                select(User.id).where(User.name == requestee_name)
            ).one_or_none()
   
        if requestee_id is None or requestee_id[0] == requester_id:
            return False

        try:
            session.add(Friendship(
            first = requester_id,
            second = requestee_id[0],
            is_request = True
            ))
            session.commit()
        except sql_error:
            return False
        except Exception as err:
            log.debug(f"found error: {err=}")
            return False

        return True

def requester(first: id, second: id):
    '''Returns the id of the user who requested a friendship'''
    stmt = select(Friendship.first).where(and_(Friendship.first == first, Friendship.second == second)).union(
            select(Friendship.first).where(and_(Friendship.first == second, Friendship.second == first)))
    with Session(engine) as session:
        return session.execute(stmt).one_or_none()

def accept_friend_request(self: id, other: id):
    '''Changes a friend request into a friendship'''
    with Session(engine) as session:
        # Leverages the fact that acceptance has to come from second
        res = session.scalar(select(Friendship).where(and_(Friendship.first == other, Friendship.second == self)))

        if res is None:
            return False

        res.is_request = False 

        try:
            session.commit()
        except sql_error:
            return False

        return True

def end_friendship(self: id, other: id):
    '''Deletes a friendship between self and other. Returns whether it succeeds'''
    with Session(engine) as session:
        res = session.scalar(
                select(Friendship).from_statement(select(Friendship).where(and_(Friendship.first == other, Friendship.second == self)).union(
            select(Friendship).where(and_(Friendship.first == self, Friendship.second == other))
        )))

        if res is None:
            return False

        try:
            session.delete(res)
            session.commit()
        except sql_error:
            return False

        return True

def create_group(user_id: int, group_name: str):
    '''Creates a group, owned by the user with id user_id'''
    with Session(engine) as session:
        group = Group(
            name = group_name
        )
 
        session.add(group)
        
        membership = GroupMembership(
            group = group,
            member_id = user_id,
            is_admin = True
        )

        session.add(membership)

        try:
            session.commit()
        except sql_error:
            return False

        return True

def join_group(user_id: int, group_id: int):
    '''Adds a user as a member of a group'''
    with Session(engine) as session:
        membership = GroupMembership(
                group_id = group_id,
                member_id = user_id,
                is_admin = False
        )
       
        session.add(membership)

        try:
            session.commit()
        except sql_error:
            return False

        return True

def delete_group(group_id: int):
    '''Deletes a group with id == group_id. Returns bool regarding whether it succeeded'''
    with Session(engine) as session:
        group = session.scalar(select(Group).where(Group.id == group_id))
        if group is None:
            return False

        try:
            session.delete(group)
            session.commit()
        except sql_error:
            return False

        return True

def rename(user_id: int, name: str):
    '''Renames a user with id == user_id to have name = name. Returns whether it was successful'''
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.id == user_id))
        if user is None:
            return False
        user.name = name

        try:
            session.commit()
        except sql_error:
            return False

        return True

def is_wall_admin(user_id: int, wall_id: int):
    '''Returns a bool representing if user is admin of wall. i.e it's theirs or they are site admin'''
    if wall_id == user_id:
        return True

    with Session(engine) as session:
        res = session.scalar(select(User.is_teacher).where(User.id == user_id))
        return res is not None and res

def is_wall_post_admin(user_id: int, post_id: int):
    '''Returns a bool representing whether the user is an admin of the wall where the wall post was posted'''
    with Session(engine) as session:
        wall_id = session.scalar(select(WallPost.wall_id).where(WallPost.id == post_id))
        if wall_id is None:
            return False

        if wall_id == user_id:
            return True

        res = session.scalar(select(User.is_teacher).where(User.id == user_id))
        return res is not None and res

def is_group_admin(user_id: int, group_id: int):
    '''Returns a bool representing if user is admin of wall. i.e explicit admin or they are site admin'''
    with Session(engine) as session:
        user = session.scalar(select(User.is_teacher).where(User.id == user_id))
        group_admin = session.scalar(select(GroupMembership.is_admin).where(and_(
            GroupMembership.member_id == user_id,
            GroupMembership.group_id == group_id
        )))

        return user or group_admin

def is_group_post_admin(user_id: int, post_id: int):
    '''Returns a bool representing whether the user is an admin of the grou where the group post was posted'''
    with Session(engine) as session:
        group_id = session.scalar(select(GroupPost.group_id).where(GroupPost.id == post_id))
        print(f"{group_id=}")
        if group_id is None:
            return False

        user = session.scalar(select(User.is_teacher).where(User.id == user_id))
        print(f"{user=}")
        group_admin = session.scalar(select(GroupMembership.is_admin).where(and_(
            GroupMembership.member_id == user_id,
            GroupMembership.group_id == group_id
        )))
        print(f"{group_admin=}")

        return user or group_admin

def delete_post(target_t: str, post_id: str):
    '''Thin wrapper around deleting wall or group post'''
    if target_t == "wall":
        return delete_wall_post(post_id)
    elif target_t == "group":
        return delete_group_post(post_id)
    else:
        return False

def delete_wall_post(post_id):
    '''Deletes wall post with id == post_id'''
    with Session(engine) as session:
        post = session.scalar(select(WallPost).where(WallPost.id == post_id))
        if post is None:
            return False

        try:
            session.delete(post)
            session.commit()
        except sql_error:
            return False

        return True

def delete_group_post(post_id):
    '''Deletes group post with id == post_id'''
    with Session(engine) as session:
        post = session.scalar(select(GroupPost).where(GroupPost.id == post_id))
        if post is None:
            return False

        try:
            session.delete(post)
            session.commit()
        except sql_error:
            return False

        return True

def can_comment_on_wall_post(user_id: int, post_id: int):
    '''Checks if a user can comment on a wall post (i.e. they are allowed to see it)'''
    with Session(engine) as session:
        resp = session.scalar(select(WallPost.wall_id).where(WallPost.id == post_id))
        if resp is None:
            return False

        return user_id == resp or are_friends(user_id, resp)

def can_comment_on_group_post(user_id: int, post_id: int):
    '''Checks if a user can comment on a group post (i.e. they are allowed to see it)'''
    with Session(engine) as session:
        resp = session.scalar(select(GroupPost.group_id).where(GroupPost.id == post_id))
        if resp is None:
            return False

        return is_group_member(user_id, resp) 
    
if __name__ == "__main__":
    print(f"{are_friends(5,6)=}")
