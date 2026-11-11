# Compatibility shim — this module was renamed to bandofy.radius_auth.
# Import from bandofy.radius_auth in new code.
from bandofy.radius_auth import (  # noqa: F401
	RADIUS_CONTROLLER_TYPES,
	check_login,
	issue_login,
	login_form,
	uses_radius as is_ruijie,
	uses_radius,
)
