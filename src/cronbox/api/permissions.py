from fastapi import Depends, HTTPException

from cronbox.api.auth import get_current_user
from cronbox.models.auth import User, UserRole


def require_role(*allowed_roles: UserRole):
    async def _check(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(403, "Insufficient permissions")
        return current_user

    return _check


require_viewer = require_role(UserRole.admin, UserRole.operator, UserRole.viewer)
require_operator = require_role(UserRole.admin, UserRole.operator)
require_admin = require_role(UserRole.admin)
