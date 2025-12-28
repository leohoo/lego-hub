import json
import os

CONFIG_FILE = os.path.expanduser("~/.lego-hub.json")


def load_config():
    """Load config from file."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_config(config):
    """Save config to file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_hub_address():
    """Get saved hub address."""
    return load_config().get("hub_address")


def save_hub_address(address, name=None):
    """Save hub address to config."""
    config = load_config()
    config["hub_address"] = address
    if name:
        config["hub_name"] = name
    save_config(config)
