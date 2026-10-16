"""Configure the root logger - import only once."""
import logging
import logging.config
import sys

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "default",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "newsegsmodelapp": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": False,
        },
        # Control verbosity for database engines without cluttering stdout
        # Ensure that you gate this inside alembic/env.py using
        # if config.config_file_name and not logging.getLogger().hasHandlers():
        #     fileConfig(config.config_file_name)
        "sqlalchemy.engine": {
            "level": "WARNING",
            #,
            "propagate": True,
        },
        "sqlalchemy.pool": {
            "level": "WARNING",
            "propagate": True,
        },
        "alembic": {
            "level": "INFO",
            #"handlers": ["console"],
            "propagate": True,
        },
    },
}

# Apply configuration once
logging.config.dictConfig(LOGGING_CONFIG)
