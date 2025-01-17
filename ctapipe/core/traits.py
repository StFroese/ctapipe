"""
Traitlet implementations for ctapipe
"""
import copy
import os
import pathlib
from collections import UserList
from fnmatch import fnmatch
from typing import Optional, Union
from urllib.parse import urlparse

import numpy as np
import traitlets
import traitlets.config
from astropy.time import Time
from traitlets import Undefined

from .component import Component, non_abstract_children

__all__ = [
    # Implemented here
    "AstroTime",
    "BoolTelescopeParameter",
    "IntTelescopeParameter",
    "FloatTelescopeParameter",
    "TelescopeParameter",
    "classes_with_traits",
    "create_class_enum_trait",
    "has_traits",
    # imported from traitlets
    "Path",
    "Bool",
    "CRegExp",
    "CaselessStrEnum",
    "CInt",
    "Dict",
    "Enum",
    "Float",
    "Int",
    "Integer",
    "List",
    "Long",
    "Set",
    "TraitError",
    "Tuple",
    "Unicode",
    "flag",
    "observe",
]

import logging

logger = logging.getLogger(__name__)


# Aliases
Bool = traitlets.Bool
Int = traitlets.Int
CInt = traitlets.CInt
Integer = traitlets.Integer
Float = traitlets.Float
Long = traitlets.Long
Unicode = traitlets.Unicode
Dict = traitlets.Dict
Enum = traitlets.Enum
List = traitlets.List
Set = traitlets.Set
CRegExp = traitlets.CRegExp
CaselessStrEnum = traitlets.CaselessStrEnum
UseEnum = traitlets.UseEnum
TraitError = traitlets.TraitError
TraitType = traitlets.TraitType
Tuple = traitlets.Tuple
observe = traitlets.observe
flag = traitlets.config.boolean_flag


class AstroTime(TraitType):
    """A trait representing a point in Time, as understood by `astropy.time`"""

    def validate(self, obj, value):
        """try to parse and return an ISO time string"""
        try:
            the_time = Time(value)
            the_time.format = "iso"
            return the_time
        except ValueError:
            return self.error(obj, value)

    def info(self):
        info = "an ISO8601 datestring or Time instance"
        if self.allow_none:
            info += "or None"
        return info


class Path(TraitType):
    """
    A path Trait for input/output files.

    Attributes
    ----------
    exists: boolean or None
        If True, path must exist, if False path must not exist
    directory_ok: boolean
        If False, path must not be a directory
    file_ok: boolean
        If False, path must not be a file
    """

    def __init__(
        self,
        default_value=Undefined,
        exists=None,
        directory_ok=True,
        file_ok=True,
        **kwargs,
    ):
        super().__init__(default_value=default_value, **kwargs)
        self.exists = exists
        self.directory_ok = directory_ok
        self.file_ok = file_ok

    def info(self):
        info = "a pathlib.Path or non-empty str for "
        if self.exists is True:
            info += "an existing"
        elif self.exists is False:
            info += "a not existing"
        else:
            info += "a"

        if self.directory_ok and self.file_ok:
            info += " directory or file"
        else:
            if self.file_ok:
                info += " file"
            if self.directory_ok:
                info += "directory"
        if self.allow_none:
            info += " or None"

        return info

    def validate(self, obj, value):
        if isinstance(value, bytes):
            value = os.fsdecode(value)

        if value is None or value is Undefined:
            if self.allow_none:
                return value
            else:
                self.error(obj, value)

        if not isinstance(value, (str, pathlib.Path)):
            return self.error(obj, value)

        # expand any environment variables in the path:
        value = os.path.expandvars(value)

        if isinstance(value, str):
            if value == "":
                return self.error(obj, value)

            try:
                url = urlparse(value)
            except ValueError:
                return self.error(obj, value)

            if url.scheme in ("http", "https"):
                # here to avoid circular import, since every module imports
                # from ctapipe.core
                from ctapipe.utils.download import download_cached

                value = download_cached(value, progress=True)
            elif url.scheme == "dataset":
                # here to avoid circular import, since every module imports
                # from ctapipe.core
                from ctapipe.utils import get_dataset_path

                value = get_dataset_path(value.partition("dataset://")[2])
            elif url.scheme in ("", "file"):
                value = pathlib.Path(url.netloc, url.path)
            else:
                return self.error(obj, value)

        value = value.absolute()
        exists = value.exists()
        if self.exists is not None:
            if exists != self.exists:
                raise TraitError(
                    'Path "{}" {} exist'.format(
                        value, "does not" if self.exists else "must not"
                    )
                )
        if exists:
            if not self.directory_ok and value.is_dir():
                raise TraitError(f'Path "{value}" must not be a directory')
            if not self.file_ok and value.is_file():
                raise TraitError(f'Path "{value}" must not be a file')

        return value


def create_class_enum_trait(base_class, default_value, help=None, allow_none=False):
    """create a configurable CaselessStrEnum traitlet from baseclass

    the enumeration should contain all names of non_abstract_children()
    of said baseclass and the default choice should be given by
    ``base_class._default`` name.

    default must be specified and must be the name of one child-class
    """
    if help is None:
        help = "{} to use.".format(base_class.__name__)

    choices = [cls.__name__ for cls in non_abstract_children(base_class)]

    if default_value not in choices:
        raise ValueError(f"{default_value} is not in choices: {choices}")

    return CaselessStrEnum(
        choices,
        default_value=default_value,
        help=help,
        allow_none=allow_none,
    ).tag(config=True)


class ComponentName(Unicode):
    """A trait that is the name of a Component class"""

    def __init__(self, cls, **kwargs):
        if not issubclass(cls, Component):
            raise TypeError(f"cls must be a Component, got {cls}")

        self.cls = cls
        super().__init__(**kwargs)
        if "help" not in kwargs:
            self.help = f"The name of a {cls.__name__} subclass"

    @property
    def help(self):
        children = list(self.cls.non_abstract_subclasses())
        return f"{self._help}. Possible values: {children}"

    @help.setter
    def help(self, value):
        self._help = value

    @property
    def info_text(self):
        return f"Any of {list(self.cls.non_abstract_subclasses())}"

    def validate(self, obj, value):
        if self.allow_none and value is None:
            return None

        if value in self.cls.non_abstract_subclasses():
            return value

        self.error(obj, value)


class ComponentNameList(List):
    """A trait that is a list of Component classes"""

    def __init__(self, cls, **kwargs):
        if not issubclass(cls, Component):
            raise TypeError(f"cls must be a Component, got {cls}")

        self.cls = cls
        trait = ComponentName(cls)
        super().__init__(trait=trait, **kwargs)

        if "help" not in kwargs:
            self.help = f"A list of {cls.__name__} subclass names"

    @property
    def help(self):
        children = list(self.cls.non_abstract_subclasses())
        return f"{self._help}. Possible values: {children}"

    @help.setter
    def help(self, value):
        self._help = value

    @property
    def info_text(self):
        return f"A list of {list(self.cls.non_abstract_subclasses())}"


def classes_with_traits(base_class):
    """Returns a list of the base class plus its non-abstract children
    if they have traits"""
    all_classes = [base_class] + non_abstract_children(base_class)
    with_traits = []

    for cls in all_classes:
        if has_traits(cls):
            with_traits.append(cls)

        # add subcomponents
        if hasattr(cls, "classes"):
            # we will ignore failing classes to not break anyone
            if isinstance(cls.classes, List):
                classes = cls.classes.default()
            else:
                classes = cls.classes

            try:
                for component in classes:
                    with_traits.extend(classes_with_traits(component))
            except Exception:
                pass

    return with_traits


def has_traits(cls, ignore=("config", "parent")):
    """True if cls has any traits apart from the usual ones

    all our components have at least 'config' and 'parent' as traitlets
    this is inherited from `traitlets.config.Configurable` so we ignore them
    here.
    """
    return bool(set(cls.class_trait_names()) - set(ignore))


class TelescopePatternList(UserList):
    """
    Representation for a list of telescope pattern tuples. This is a helper class
    used  by the Trait TelescopeParameter as its value type
    """

    def __init__(self, *args):
        super().__init__(*args)
        self._lookup = None
        self._subarray = None

        for i in range(len(self)):
            self[i] = self.single_to_pattern(self[i])

    @property
    def tel(self):
        """access the value per telescope_id, e.g. `param.tel[2]`"""
        if self._lookup:
            return self._lookup
        else:
            raise RuntimeError(
                "No TelescopeParameterLookup was registered. You must "
                "call attach_subarray() first"
            )

    @staticmethod
    def single_to_pattern(value):
        # make sure we only change things that are not already a
        # pattern tuple
        if (
            not isinstance(value, tuple)
            or len(value) != 3
            or value[0] not in {"type", "id"}
        ):
            return ["type", "*", value]

        return value

    def append(self, value):
        """Validate and then append a new value"""
        super().append(self.single_to_pattern(value))

    def attach_subarray(self, subarray):
        """
        Register a SubarrayDescription so that the user-specified values can be
        looked up by tel_id. This must be done before using the `.tel[x]` property
        """
        self._subarray = subarray
        self._lookup.attach_subarray(subarray)


class TelescopeParameterLookup:
    def __init__(self, telescope_parameter_list):
        """
        Handles the lookup of corresponding configuration value from a list of
        tuples for a tel_id.

        Parameters
        ----------
        telescope_parameter_list : list
            List of tuples in the form `[(command, argument, value), ...]`
        """
        self._telescope_parameter_list = copy.deepcopy(telescope_parameter_list)
        self._value_for_tel_id = None
        self._value_for_type = None
        self._subarray = None
        self._subarray_global_value = Undefined
        self._type_strs = None
        for param in telescope_parameter_list:
            if param[1] == "*":
                self._subarray_global_value = param[2]

    def attach_subarray(self, subarray):
        """
        Prepare the TelescopeParameter by informing it of the
        subarray description

        Parameters
        ----------
        subarray: ctapipe.instrument.SubarrayDescription
            Description of the subarray
            (includes mapping of tel_id to tel_type)
        """
        self._subarray = subarray
        self._value_for_tel_id = {}
        self._value_for_type = {}
        self._type_strs = {str(tel) for tel in self._subarray.telescope_types}
        for command, arg, value in self._telescope_parameter_list:
            if command == "type":
                matched_tel_types = [
                    str(t) for t in subarray.telescope_types if fnmatch(str(t), arg)
                ]
                logger.debug(f"argument '{arg}' matched: {matched_tel_types}")

                if len(matched_tel_types) == 0:
                    logger.warning(
                        "TelescopeParameter type argument '%s' did not match "
                        "any known telescope types",
                        arg,
                    )

                for tel_type in matched_tel_types:
                    self._value_for_type[tel_type] = value
                    for tel_id in subarray.get_tel_ids_for_type(tel_type):
                        self._value_for_tel_id[tel_id] = value
            elif command == "id":
                self._value_for_tel_id[int(arg)] = value
            else:
                raise ValueError(f"Unrecognized command: {command}")

    def __getitem__(self, tel: Optional[Union[int, str]]):
        """
        Returns the resolved parameter for the given telescope id
        """
        if tel is None:
            if self._subarray_global_value is not Undefined:
                return self._subarray_global_value

            raise KeyError("No subarray global value set for TelescopeParameter")

        if self._value_for_tel_id is None:
            raise ValueError(
                "TelescopeParameterLookup: No subarray attached, call "
                "`attach_subarray` first before trying to access a value by tel_id"
            )

        if isinstance(tel, (int, np.integer)):
            try:
                return self._value_for_tel_id[tel]
            except KeyError:
                raise KeyError(
                    f"TelescopeParameterLookup: no "
                    f"parameter value was set for telescope with tel_id="
                    f"{tel}. Please set it explicitly, "
                    f"or by telescope type or '*'."
                )

        from ctapipe.instrument import TelescopeDescription

        if isinstance(tel, TelescopeDescription):
            tel = str(tel)

        if isinstance(tel, str):
            if tel not in self._type_strs:
                raise ValueError(
                    f"Unknown telescope type {tel}, known: {self._type_strs}"
                )
            try:
                return self._value_for_type[tel]
            except KeyError:
                raise KeyError(
                    "TelescopeParameterLookup: no "
                    "parameter value was set for telescope type"
                    f" '{tel}'. Please set explicitly or using '*'."
                )

        raise TypeError(f"Unsupported lookup type: {type(tel)}")


class TelescopeParameter(List):
    """
    Allow a parameter value to be specified as a simple value (of type *dtype*),
    or as a list of patterns that match different telescopes.

    The patterns are given as a list of 3-tuples in the
    form: ``[(command, argument, value), ...]``.

    Command can be one of:

    - ``'type'``: argument is then a telescope type  string (e.g.
      ``('type', 'SST_ASTRI_CHEC', 4.0)`` to apply to all telescopes of that type,
      or use a wildcard like "LST*", or "*" to set a pure default value for all
      telescopes.
    - ``'id'``:  argument is a specific telescope ID ``['id', 89, 5.0]``)

    These are evaluated in-order, so you can first set a default value, and then set
    values for specific telescopes or types to override them.

    Examples
    --------

    .. code-block: python

        tel_param = [
            ('type', '*', 5.0),                       # default for all
            ('type', 'LST_*', 5.2),
            ('type', 'MST_MST_NectarCam', 4.0),
            ('type', 'MST_MST_FlashCam', 4.5),
            ('id', 34, 4.0),                   # override telescope 34 specifically
        ]

    .. code-block: python

        tel_param = 4.0  # sets this value for all telescopes

    """

    klass = TelescopePatternList
    _valid_defaults = (object,)  # allow everything, we validate the default ourselves

    def __init__(self, trait, default_value=Undefined, **kwargs):
        """
        Create a new TelescopeParameter
        """
        self._help = ""

        if not isinstance(trait, TraitType):
            raise TypeError("trait must be a TraitType instance")

        self._trait = trait
        self.allow_none = kwargs.get("allow_none", False)
        if default_value != Undefined:
            default_value = self.validate(self, default_value)

        if "help" not in kwargs:
            self.help = "A TelescopeParameter"

        super().__init__(default_value=default_value, **kwargs)

    @property
    def help(self):
        sep = "." if not self._help.endswith(".") else ""
        return f"{self._help}{sep} {self._trait.help}"

    @help.setter
    def help(self, value):
        self._help = value

    def from_string(self, s):
        val = super().from_string(s)
        # for strings, parsing fails and traitlets returns None
        if val == [("type", "*", None)] and s != "None":
            val = [("type", "*", self._trait.from_string(s))]
        return val

    def _validate_entry(self, obj, value):
        if value is None and self.allow_none is True:
            return None
        return self._trait.validate(obj, value)

    def validate(self, obj, value):

        # Support a single value for all (check and convert into a default value)
        if not isinstance(value, (list, List, UserList, TelescopePatternList)):
            value = [("type", "*", self._validate_entry(obj, value))]

        # Check each value of list
        normalized_value = TelescopePatternList()

        for pattern in value:

            # now check for the standard 3-tuple of (command, argument, value)
            if len(pattern) != 3:
                raise TraitError(
                    "pattern should be a tuple of (command, argument, value)"
                )

            command, arg, val = pattern
            val = self._validate_entry(obj, val)

            if not isinstance(command, str):
                raise TraitError("command must be a string")

            if command not in ["type", "id"]:
                raise TraitError("command must be one of: 'type', 'id'")

            if command == "type":
                if not isinstance(arg, str):
                    raise TraitError("'type' argument should be a string")

            if command == "id":
                try:
                    arg = int(arg)
                except ValueError:
                    raise TraitError(f"Argument of 'id' should be an int (got '{arg}')")

            val = self._validate_entry(obj, val)
            normalized_value.append((command, arg, val))
            normalized_value._lookup = TelescopeParameterLookup(normalized_value)

            if isinstance(value, TelescopePatternList) and value._subarray is not None:
                normalized_value.attach_subarray(value._subarray)

        return normalized_value

    def set(self, obj, value):
        # Support a single value for all (check and convert into a default value)
        if not isinstance(value, (list, List, UserList, TelescopePatternList)):
            value = [("type", "*", self._validate_entry(obj, value))]

        # Retain existing subarray description
        # when setting new value for TelescopeParameter
        try:
            old_value = obj._trait_values[self.name]
        except KeyError:
            old_value = self.default_value

        super().set(obj, value)

        if getattr(old_value, "_subarray", None) is not None:
            obj._trait_values[self.name].attach_subarray(old_value._subarray)


class FloatTelescopeParameter(TelescopeParameter):
    """a `~ctapipe.core.traits.TelescopeParameter` with Float trait type"""

    def __init__(self, **kwargs):
        """Create a new FloatTelescopeParameter"""
        super().__init__(trait=Float(), **kwargs)


class IntTelescopeParameter(TelescopeParameter):
    """a `~ctapipe.core.traits.TelescopeParameter` with Int trait type"""

    def __init__(self, **kwargs):
        """Create a new IntTelescopeParameter"""
        super().__init__(trait=Integer(), **kwargs)


class BoolTelescopeParameter(TelescopeParameter):
    """a `~ctapipe.core.traits.TelescopeParameter` with Bool trait type"""

    def __init__(self, **kwargs):
        """Create a new BoolTelescopeParameter"""
        super().__init__(trait=Bool(), **kwargs)
