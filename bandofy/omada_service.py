# Compatibility shim — this module was renamed to bandofy.omada_auth.
# Import from bandofy.omada_auth in new code.
from bandofy.omada_auth import (  # noqa: F401
	OmadaAuthError,
	authorize_client,
	diagnose,
	get_live_stats,
	site_controller,
	_new_session,
	_operator_login,
	_settings,
)
