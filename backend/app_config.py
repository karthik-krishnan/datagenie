"""
Central application configuration.
Values are read from environment variables so they can be overridden in
docker-compose.yml, a .env file, or the host environment without code changes.
"""
import os

# Maximum number of root-entity records the generate endpoint will produce
# in a single request.  Child-table rows multiply on top of this.
# Increase carefully — very large values will slow down in-browser rendering.
MAX_VOLUME_RECORDS: int = int(os.getenv("MAX_VOLUME_RECORDS", "10000"))
