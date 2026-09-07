"""Test-suite isolation from the developer's ``server/.env``.

That file carries real deployment values (API tokens, an Instagram session
cookie). Tests must not read it: several assert behaviour for an *unconfigured*
server. `xownloader_server.config` builds a module-level ``settings`` singleton
and `xownloader_server.main` builds its registry, job manager, and preview
service from it at import time, so isolating only the `Settings` class is not
enough — the already-built singletons are rebuilt here too, before any test
module imports `main`.
"""

from xownloader_server import config

config.Settings.model_config["env_file"] = None
config.settings = config.Settings()

from xownloader_server import main  # noqa: E402

main.settings = config.settings
main.provider_registry = main.build_registry(config.settings)
main.job_manager = main.JobManager(config.settings, registry=main.provider_registry)
main.preview_service = main.PreviewService(config.settings, registry=main.provider_registry)
main.app.state.preview_service = main.preview_service
