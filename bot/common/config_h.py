import os.path as path
from common import json_h

#
# CONST
#

CONFIG_DIR = path.join(path.dirname(__file__), "../../config")

#
# PRIVATE
#

def _read_from_disk():
    try:
        config_file = path.join(CONFIG_DIR, "bot_config.json")
        secrets_file = path.join(CONFIG_DIR, "bot_secrets.json")

        # Read
        bot_config = json_h.get_json(config_file)
        bot_secrets = json_h.get_json(secrets_file)

        # Merge
        return {**bot_config, **bot_secrets}
    except IOError as e:
        if e.errno == 2:
            print("Config files are missing")
        quit()

_config_cache = _read_from_disk()

#
# PUBLIC
#

def get(*, from_disk = False):
    global _config_cache

    if from_disk:
        _config_cache = _read_from_disk()

    return _config_cache