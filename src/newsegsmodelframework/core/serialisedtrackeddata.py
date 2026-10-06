import copy
from typing import Any, Mapping, Sequence, Type, override

from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.core.serialisation import T, StateSerialiseToDictMixin
from newsegsmodelframework.core.trackeddata import ComponentPropertyInterface, ConfigurationMixin, DataWithRevision


class SerialisedConfigurationMixin(
    ConfigurationMixin,
    StateSerialiseToDictMixin
):
    @override
    def _preupdate_from_dict(self, config):
        super()._preupdate_from_dict(config)
        
        config_exists = hasattr(self, '_config')
        full_update = False
        
        # If config exists in the dict, it has to be the first thing out
        inst_config = config.pop('_config', None)
        if inst_config:
            if isinstance(inst_config, DataWithRevision):
                full_update = True
                setattr(self, '_config', inst_config)
                config_exists = True
            elif isinstance(inst_config, Mapping):
                if not config_exists:
                    full_update = True
                    setattr(self, '_config', self._generate_config())
                    config_exists = True
                cfg = self._config
                for k, v in inst_config.items():
                    setattr(cfg, k, v)
            else:
                raise TypeError(f'Unsupported type for config update: {type(inst_config)}')
        if not config_exists:
            full_update = True
            setattr(self, '_config', self._generate_config())

        # Set a temporary store of the config revision so that it may be reset
        # at the end of update
        if full_update:
            object.__setattr__(self, '_config_revis_0', self._config._revision)

    @override
    def _main_update_from_dict(self, config):
        # We want to be able to accept property updates, but need to strip
        # them out of the update dict and apply them after other updates
        type_ = type(self)
        property_updates = {}
        for k in config.keys():
            # (Writable) properties are expected to be attributes on the class 
            # which either implement ComponentPropertyInterface or have a valid fset
            if hasattr(type_, k):
                prop = getattr(type_, k)
                if (
                    isinstance(prop, ComponentPropertyInterface) 
                    or hasattr(prop, 'fset') and getattr(prop, 'fset') is not None
                ):
                    v = config.get(k)
                    if isinstance(v, dict) and hasattr(getattr(self, k), 'update'):
                        continue
                    else:
                        property_updates[k] = v

        # Remove items which update properties
        for k in property_updates.keys():
            config.pop(k)

        # Remainder do a standard update
        super()._main_update_from_dict(config)

        # Not all properties have a valid fset; if so, we are going to overwrite it
        for k, v in property_updates.items():
            try:
                prop = getattr(type_, k)
                getattr(prop, 'fset')(self, v)
            except AttributeError:
                setattr(self, k, v)

    def _post_update_from_dict(self):
        if hasattr(self, '_config_revis_0'):
            self._config._revision = self._config_revis_0
            delattr(self, '_config_revis_0')

    @override
    def update(self, config: dict[str, Any] | type[T]):
        super().update(config)
        self._post_update_from_dict()
    