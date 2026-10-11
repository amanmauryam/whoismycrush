from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

User = get_user_model()


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        identifier = username.strip()
        try:
            user = User.objects.get(
                Q(email__iexact=identifier) | Q(username__iexact=identifier)
            )
        except User.DoesNotExist:
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            user = (
                User.objects.filter(
                    Q(email__iexact=identifier) | Q(username__iexact=identifier)
                )
                .order_by("id")
                .first()
            )
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
