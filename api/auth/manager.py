from typing import Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users import BaseUserManager, IntegerIDMixin, exceptions

from api.auth.models import User
from api.auth.schemas import UserCreate
from api.auth.utils import get_user_db
from config import SECRET

from fastapi import Request


class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = SECRET

    verification_token_secret = SECRET

    async def get_by_username(self, username: str):
        """
        Get a user by username.

        :param user_email: E-mail of the user to retrieve.
        :raises UserNotExists: The user does not exist.
        :return: A user.
        """
        user = await self.user_db.get_by_username(username)
        if user is None:
            raise exceptions.UserNotExists()

        return user

    async def create(
            self,
            user_create: UserCreate,
            safe: bool = False,
            request: Optional[Request] = None,
    ):
        """
        Create a user in database.

        Triggers the on_after_register handler on success.

        :param user_create: The UserCreate model to create.
        :param safe: If True, sensitive values like is_superuser or is_verified
        will be ignored during the creation, defaults to False.
        :param request: Optional FastAPI request that
        triggered the operation, defaults to None.
        :raises UserAlreadyExists: A user already exists with the same e-mail.
        :return: A new user.
        """
        await self.validate_password(user_create.password, user_create)

        existing_user = await self.user_db.get_by_username(user_create.username)
        if existing_user is not None:
            raise exceptions.UserAlreadyExists()

        user_dict = (
            user_create.create_update_dict()
            if safe
            else user_create.create_update_dict_superuser()
        )
        password = user_dict.pop("password")
        user_dict["hashed_password"] = self.password_helper.hash(password)

        created_user = await self.user_db.create(user_dict)

        await self.on_after_register(created_user, request)

        return created_user

    async def authenticate(
            self, credentials: OAuth2PasswordRequestForm
    ):
        """
        Authenticate and return a user following an email and a password.

        Will automatically upgrade password hash if necessary.

        :param credentials: The user credentials.
        """
        try:
            user = await self.get_by_username(credentials.username)
        except exceptions.UserNotExists:
            # Run the hasher to mitigate timing attack
            # Inspired from Django: https://code.djangoproject.com/ticket/20760
            self.password_helper.hash(credentials.password)
            return None
        print(user)
        verified, updated_password_hash = self.password_helper.verify_and_update(
            credentials.password, user.hashed_password
        )
        if not verified:
            return None
        # Update password hash to a more robust one if needed
        if updated_password_hash is not None:
            await self.user_db.update(user, {"hashed_password": updated_password_hash})

        return user

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"Зарегистрирован пользователь {user}")

    async def on_after_forgot_password(

            self, user: User, token: str, request: Optional[Request] = None

    ):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(

            self, user: User, token: str, request: Optional[Request] = None

    ):
        print(f"Verification requested for user {user.id}. Verification token: {token}")



async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)
