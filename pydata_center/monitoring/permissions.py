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


class IsAuthenticatedAgent(BasePermission):
    """
    Grants access if the user is an active authenticated Agent.
    """

    def has_permission(self, request, view):
        user = request.user
        return getattr(user, 'is_agent', False) and user.is_active


class HasMonitoringPermission(BasePermission):
    """
    Grants access if the user has the permission specified by the view.
    """

    def has_permission(self, request, view):
        required_perm = getattr(view, 'required_permission', None)

        if required_perm:
            return request.user.has_perm(required_perm)

        return False
