from collections import OrderedDict

import numpy as np

__author__ = 'peter'


def flatten_struct(struct, primatives = (int, float, np.ndarray, basestring, bool), custom_handlers = {},
        break_into_objects = True, detect_duplicates = True, memo = None):
    """
    Given some nested struct, return a list<*(str, primative)>, where primative
    is some some kind of object that you don't break down any further, and str is a
    string representation of how you would access that propery from the root object.

    Don't try any fancy circular references here, it's not going to go well for you.

    :param struct: Something, anything.
    :param primatives: A list of classes that will not be broken into.
    :param custum_handlers: A dict<type:func> where func has the form data = func(obj).  These
        will be called if the type of the struct is in the dict of custom handlers.
    :param break_into_objects: True if you want to break into objects to see what's inside.
    :return: list<*(str, primative)>
    """
    if memo is None:
        memo = {}

    if id(struct) in memo:
        return [(None, memo[id(struct)])]
    elif detect_duplicates:
        memo[id(struct)] = 'Already Seen object at %s' % hex(id(struct))

    if isinstance(struct, primatives):
        return [(None, struct)]
    elif isinstance(struct, tuple(custom_handlers.keys())):
        handler = custom_handlers[custom_handlers.keys()[[isinstance(struct, t) for t in custom_handlers].index(True)]]
        return [(None, handler(struct))]
    elif isinstance(struct, dict):
        return sum([
            [("[%s]%s" % (("'%s'" % key if isinstance(key, str) else key), subkey if subkey is not None else ''), v)
                for subkey, v in flatten_struct(value, custom_handlers=custom_handlers, primatives=primatives, break_into_objects=break_into_objects, memo=memo, detect_duplicates=detect_duplicates)]
                for key, value in struct.iteritems()
            ], [])
    elif isinstance(struct, (list, tuple)):
        # for i, value in enumerate(struct):
        return sum([
            [("[%s]%s" % (i, subkey if subkey is not None else ''), v)
                for subkey, v in flatten_struct(value, custom_handlers=custom_handlers, primatives=primatives, break_into_objects=break_into_objects, memo=memo, detect_duplicates=detect_duplicates)]
                for i, value in enumerate(struct)
            ], [])
    elif struct is None or not hasattr(struct, '__dict__'):
        return []
    elif break_into_objects:  # It's some kind of object, lets break it down.
        return sum([
            [(".%s%s" % (key, subkey if subkey is not None else ''), v)
                for subkey, v in flatten_struct(value, custom_handlers=custom_handlers, primatives=primatives, break_into_objects=break_into_objects, memo=memo, detect_duplicates=detect_duplicates)]
                for key, value in struct.__dict__.iteritems()
            ], [])
    else:
        return [(None, memo[id(struct)])]


_primitive_containers = (list, tuple, dict, set)


def flatten_nested_object(data_object, containers = _primitive_containers, include_classes = False):
    """
    Given a data object, walk through the object and return a dict of contained objects.
    It's best to see the tests to understand this function.

    Don't try any fancy circular references here - it's not going to go well for you.

    :param data_object:
    :return: An OrderedDict containing, in depth-first-order, the list of objects and containers.
    """
    directory_listing = OrderedDict()
    if include_classes:
        directory_listing['__class__'] = type(data_object)
    if data_object in containers:
        if isinstance(data_object, (list, tuple)):
            directory_listing[None] = type(data_object)
            for i, x in enumerate(data_object):
                sub_obj = flatten_nested_object(data_object)
                for k, v in sub_obj.iteritems():
                    directory_listing[(i, )+k] = v
        elif isinstance(data_object, dict):
            for key, val in data_object.iteritems():
                sub_obj = flatten_nested_object(val)
                for k, v in sub_obj.iteritems():
                    directory_listing[(key, )+k] = v
        else:
            raise Exception('Unidentified container type: {}'.format(type(data_object)))
    else:
        directory_listing[()] = data_object


def get_meta_object(data_object, containers = _primitive_containers):
    """
    Given an arbitrary data structure, return a "meta object" which is the same structure, except all non-container
    objects are replaced by their types.

    e.g.
        get_meta_obj([1, 2, {'a':(3, 4), 'b':['hey', 'yeah']}, 'woo']) == [int, int, {'a':(int, int), 'b':[str, str]}, str]

    :param data_object: A data object with arbitrary nested structure
    :param containers: Which classes to consider containers.  Classes derived from these are also considered containers.
    :return:
    """
    if isinstance(data_object, containers):
        if isinstance(data_object, (list, tuple, set)):
            return type(data_object)(get_meta_object(x) for x in data_object)
        elif isinstance(data_object, dict):
            return type(data_object)((k, get_meta_object(v)) for k, v in data_object.iteritems())
    else:
        return type(data_object)


class NestedType(object):
    """
    An object which represents the type of an arbitrarily nested data structure.  It can be constructed directly
    from a nested type descriptor, or indirectly using the NestedType.from_data(...) constructor.

    For example
        NestedType.from_data([1, 2, {'a':(3, 4.), 'b':'c'}]) == NestedType([int, int, {'a':(int, float), 'b':str}])
    """

    def __init__(self, meta_object):
        """
        :param meta_object: A nested type descriptor.  See docstring and tests for examples.
        """
        self.meta_object = meta_object

    def is_type_for(self, data_object):
        return get_meta_object(data_object)==self.meta_object

    def check_type(self, data_object):
        """
        Assert that the data_object has a format matching this NestedType.  Throw a TypeError if it does not.
        :param data_object:
        :return:
        """
        if not self.is_type_for(data_object):
            raise TypeError('The data object has type {}, which does not match this format: {}'.format(NestedType.from_data(data_object), self))

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, self.meta_object)

    def __eq__(self, other):
        return self.meta_object == other.meta_object

    def get_leaves(self, data_object):
        """
        :param data_object: Given a nested object, get the "leaf" values in Depth-First Order
        :return: A list of leaf values.
        """
        assert self.is_type_for(data_object)
        return get_leaf_values(data_object)

    def expand_from_leaves(self, leaves, check_types = True):
        return _fill_meta_object(self.meta_object, (x for x in leaves), check_types=check_types)

    @staticmethod
    def from_data(data_object, containers = _primitive_containers):
        """
        :param data_object: A nested data object
        :param containers: The list of classes defined as "containers"
        :return: A NestedType object
        """
        return NestedType(get_meta_object(data_object, containers=containers))


def get_leaf_values(data_object, containers = _primitive_containers):
    """
    Collect leaf values.
    Caution: If your data contains dicts, you may not get the same order of results when you call this function with
    different dict objects containing the same data.  Python only guarantees that a given dict will always iterate in
    the same order so long as it is not modified.  See https://docs.python.org/2/library/stdtypes.html#dict.items

    :param data_object: An arbitrary nested data object
    :param containers: The list of "container" classes that we should break into.
    :return:
    """
    leaf_values = []
    if isinstance(data_object, containers):
        if isinstance(data_object, (list, tuple)):
            leaf_values += [val for x in data_object for val in get_leaf_values(x)]
        elif isinstance(data_object, OrderedDict):
            leaf_values += [val for k, x in data_object.iteritems() for val in get_leaf_values(x)]
        elif isinstance(data_object, dict):
            leaf_values += [val for k in sorted(data_object.keys()) for val in get_leaf_values(data_object[k])]
        else:
            raise Exception('Have no way to consistently extract leaf values from a {}'.format(data_object))
        return leaf_values
    else:
        return [data_object]


def _fill_meta_object(meta_object, data_iteratable, assert_fully_used = True, check_types = True):
    """
    Fill the data from the iterable into the meta_object.
    :param meta_object: A nested type descripter.  See NestedType init
    :param data_iteratable: The iterable data object
    :param assert_fully_used: Assert that we actually get through all the items in the iterable
    :return: The filled object
    """

    try:
        if isinstance(meta_object, _primitive_containers):
            if isinstance(meta_object, (list, tuple, set)):
                filled_object = type(meta_object)(_fill_meta_object(x, data_iteratable, assert_fully_used=False, check_types=check_types) for x in meta_object)
            elif isinstance(meta_object, OrderedDict):
                filled_object = type(meta_object)((k, _fill_meta_object(val, data_iteratable, assert_fully_used=False, check_types=check_types)) for k, val in meta_object.iteritems())
            elif isinstance(meta_object, dict):
                filled_object = type(meta_object)((k, _fill_meta_object(meta_object[k], data_iteratable, assert_fully_used=False, check_types=check_types)) for k in sorted(meta_object.keys()))
            else:
                raise Exception('Cannot handle container type: "{}"'.format(type(meta_object)))
        else:
            next_data = data_iteratable.next()
            if check_types and meta_object is not type(next_data):
                raise TypeError('The type of the data object: {} did not match type from the meta object: {}'.format(type(next_data), meta_object))
            filled_object = next_data
    except StopIteration:
        raise TypeError('The data iterable you were going through ran out before the object {} could be filled.'.format(meta_object))

    if assert_fully_used:
        try:
            data_iteratable.next()
            raise TypeError('It appears that the data object you were using to fill your meta object had more data than could fit.')
        except StopIteration:
            pass
    return filled_object


def get_nested_value(data_object, key_chain):
    if len(key_chain)>0:
        return get_nested_value(data_object[key_chain[0]], key_chain=key_chain[1:])
    else:
        return data_object


class ExpandingDict(dict):

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            self[key] = ExpandingDict()
            return dict.__getitem__(self, key)


def expand_struct(struct):

    expanded_struct = ExpandingDict()

    for k in struct.keys():
        exec('expanded_struct%s = struct["%s"]' % (k, k))

    return expanded_struct
