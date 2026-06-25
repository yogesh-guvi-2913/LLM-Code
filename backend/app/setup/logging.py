import logging
import app.config as config
from pythonjsonlogger import jsonlogger # this is not technically used here, but required for the JSON formatter at runtime

def initLogging():
    loggingConfig = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'local': {
                'format': '%(levelname)s: %(message)s [%(name)s] [%(funcName)s: %(lineno)d] [%(process)d %(thread)d %(threadName)s]',
            },
            'production': {
                'format': '%(asctime)s %(levelname)s: %(message)s [%(name)s] [%(funcName)s: %(lineno)d] [%(process)d %(thread)d %(threadName)s]',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'production_json': {
                '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
                'format': '%(asctime)s %(levelname)s %(message)s %(name)s %(funcName)s %(lineno)d %(process)d %(thread)d %(threadName)s'
            }
        },
        'handlers': {
            'local_console': {
                'class': 'logging.StreamHandler',
                'formatter': 'local',
                'level': logging.INFO
            },
            # Currently not used, since json based logging for promtail for loki
            'production_console': {
                'class': 'logging.StreamHandler',
                'formatter': 'production',
                'level': logging.INFO
            },
            'production_json_console': {
                'class': 'logging.StreamHandler',
                'formatter': 'production_json',
                'level': logging.INFO
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': 'app.log',
                'formatter': 'production',
                'level': logging.INFO,
                'maxBytes': 10 * 1024 * 1024,  # 10 MB
                'backupCount': 10
            }
        },
        'loggers': {
            'uvicorn.error': {
                'handlers': ['production_json_console', 'file'] if config.ENVIRONMENT == 'production' else ['local_console'],
                'level': logging.INFO,
                'propagate': False
            },
            'uvicorn.access': {
                'handlers': ['production_json_console', 'file'] if config.ENVIRONMENT == 'production' else ['local_console'],
                'level': logging.INFO,
                'propagate': False
            }
        },
        'root': {
            'handlers': ['production_json_console', 'file'] if config.ENVIRONMENT == 'production' else ['local_console'],
            'level': logging.INFO
        }
    }

    logging.config.dictConfig(loggingConfig)

    logger = logging.getLogger(__name__)
    logger.info('Logging setup completed successfully.')
