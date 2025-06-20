from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminOrOperatorForWrite(BasePermission):
    """
    - Allow read-only (GET, HEAD, OPTIONS) to everyone.
    - Allow write (POST, PATCH, DELETE) only to Admin and Operator.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True  # Viewer, Admin, Operator - GET access

        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.groups.filter(
            name__in=['Admin', 'Operator']).exists()
