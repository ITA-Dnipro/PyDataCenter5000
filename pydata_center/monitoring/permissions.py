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
    Custom permission for Agent-based authentication.
    """

    def has_permission(self, request, view):
        user = request.user

        # Check if the user is an Agent
        if hasattr(user, '_meta') and user._meta.model_name == 'agent':

            return user.is_active

        # Otherwise fallback to normal Django permission system (for User)
        return request.user.has_perm('monitoring.add_serverstatus')
