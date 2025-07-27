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


class IsAgentWithPermission(BasePermission):
    """
    Grants access if the user is an active Agent or has a specific permission
    defined by the view.
    """

    def has_permission(self, request, view):
        user = request.user

        if getattr(user, 'is_agent', False):
            return user.is_active

        required_perm = getattr(view, 'required_permission', None)
        if required_perm:
            return user.has_perm(required_perm)

        return False
