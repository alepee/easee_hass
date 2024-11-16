"""Easee charger component."""
import logging

from awesomeversion import AwesomeVersion
try:
    from pyeasee import __version__ as pyeasee_version
except Exception:
    pyeasee_version = "unknown"
from pysignalr import __version__ as pysignalr_version
from websockets import __version__ as websockets_version

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

try:
    from .const import (
        DOMAIN,
        LISTENER_FN_CLOSE,
        MIN_HA_VERSION,
        PLATFORMS,
        VERSION,
    )
    from .controller import Controller
    from .services import async_setup_services
except Exception as e:
    raise ImportError(f"easee_hass with pyeasee {pyeasee_version}, pysignalr {pysignalr_version}, websockets {websockets_version}") from e

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Easee integration from a config entry."""
    current = AwesomeVersion(HA_VERSION)
    req_min = AwesomeVersion(MIN_HA_VERSION)
    if current < req_min:
        _LOGGER.error(
            "Integration requires Home Assistant version %s or later", req_min
        )
        return False
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["entities"] = []
    hass.data[DOMAIN]["sites_to_remove"] = []
    _LOGGER.debug("Setting up Easee component version %s", VERSION)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    try:
        controller = Controller(username, password, hass, entry)
        await controller.initialize()
    except ConfigEntryAuthFailed as err:
        raise ConfigEntryAuthFailed from err

    hass.data[DOMAIN]["controller"] = controller

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await async_setup_services(hass)

    undo_listener = entry.add_update_listener(config_entry_update_listener)

    hass.data[DOMAIN][entry.entry_id] = {
        LISTENER_FN_CLOSE: undo_listener,
    }

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if hass.data[DOMAIN]["controller"] is not None:
        await hass.data[DOMAIN]["controller"].cleanup()
    if unload_ok:
        hass.data[DOMAIN][entry.entry_id][LISTENER_FN_CLOSE]()
        hass.data[DOMAIN] = {}

    return unload_ok


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.info("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        options = {**config_entry.options}
        # modify Config Entry data
        if "monitored_conditions" in options:
            options.pop("monitored_conditions")

        if "monitored_eq_conditions" in options:
            options.pop("monitored_eq_conditions")

        config_entry.options = {**options}

        config_entry.version = 2

    if config_entry.version == 2:
        options = {**config_entry.options}
        # modify Config Entry data
        if "custom_units" in options:
            options.pop("custom_units")

        config_entry.options = {**options}

        config_entry.version = 3

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
