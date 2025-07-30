from typing import ClassVar, Iterable

from rest_framework.permissions import SAFE_METHODS, BasePermission


class ReadOnlyOrGroupWritePermission(BasePermission):
    """
    Allow read-only access (GET, HEAD, OPTIONS) to everyone.
    Allow write access only to users in `allowed_groups`.
    """
    allowed_groups: ClassVar[Iterable[str]] = ()

    def has_permission(self, request, view) -> bool:
        # 1) If this is a safe method, grant access immediately
        if request.method in SAFE_METHODS:
            return True

        # 2) Ensure the user is authenticated
        user = getattr(request, 'user', None)
        if not getattr(user, 'is_authenticated', False):
            return False

        # 3) Check that the user belongs to one of the allowed groups
        return user.groups.filter(name__in=self.allowed_groups).exists()


class IsAdminOrOperatorForWrite(ReadOnlyOrGroupWritePermission):
    """
    Read-only for everyone.
    Write only for users in the 'Admin' or 'Operator' groups.
    """
    allowed_groups = ('Admin', 'Operator')
