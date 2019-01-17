"""Generate prototexts for LBANN models."""

import sys
import google.protobuf.text_format
from collections.abc import Iterable

# Attempt to find and load the lbann_pb2 module generated by protobuf.
# This should be built automatically during the LBANN build process.
# First see if it's in the default Python search path.
try:
    import lbann_pb2
except ImportError:
    # Not found, try to find and add the build directory for this system.
    import socket, re, os, os.path
    _system_name = re.sub(r'\d+', '', socket.gethostname())
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _lbann_dir = os.path.dirname(os.path.dirname(_script_dir))
    # For now, hardcode GCC, Release/Debug, and .llnl.gov.
    # TODO: Relax this.
    _release_dir = os.path.join(_lbann_dir, 'build',
                                'gnu.Release.' + _system_name + '.llnl.gov')
    _debug_dir = os.path.join(_lbann_dir, 'build',
                              'gnu.Debug.' + _system_name + '.llnl.gov')
    if os.path.isdir(_release_dir):
        sys.path.append(os.path.join(_release_dir,
                                     'install', 'share', 'python'))
        import lbann_pb2
    elif os.path.isdir(_debug_dir):
        sys.path.append(os.path.join(_debug_dir,
                                     'install', 'share', 'python'))
        import lbann_pb2
    else:
        raise  # Give up.

def _add_to_module_namespace(stuff):
    """Add stuff to the module namespace.

    stuff is a dict, keys will be the name.

    """
    g = globals()
    for k, v in stuff.items():
        g[k] = v

def _make_iterable(obj):
    """Convert to an iterable object.

    Simply returns 'obj' if it is alredy iterable. Otherwise returns a
    1-tuple containing 'obj'.

    """
    if isinstance(obj, Iterable):
        return obj
    else:
        return (obj,)

# ==============================================
# Layers
# ==============================================

class Layer:
    """Base class for layers."""

    num_layers = 0  # Static counter, used for default layer names

    def __init__(self, parents, children, weights,
                 name, data_layout, hint_layer):
        Layer.num_layers += 1
        self.parents = []
        self.children = []
        self.weights = []
        self.name = name if name else 'layer{0}'.format(Layer.num_layers)
        self.data_layout = data_layout
        self.hint_layer = hint_layer

        # Initialize parents, children, and weights
        for l in _make_iterable(parents):
            self.add_parent(l)
        for l in _make_iterable(children):
            self.add_child(child)
        for w in _make_iterable(weights):
            self.add_weights(w)

    def export_proto(self):
        """Construct and return a protobuf message."""
        proto = lbann_pb2.Layer()
        proto.parents = ' '.join([l.name for l in self.parents])
        proto.children = ' '.join([l.name for l in self.children])
        proto.weights = ' '.join([w.name for w in self.weights])
        proto.name = self.name
        proto.data_layout = self.data_layout
        proto.hint_layer = self.hint_layer.name if self.hint_layer else ''
        return proto

    def add_parent(self, parent):
        """This layer will receive an input tensor from 'parent'."""
        self.parents.append(parent)
        parent.children.append(self)

    def add_child(self, child):
        """"This layer will send an output tensor to 'child'."""
        self.children.append(child)
        child.parents.append(self)

    def add_weights(self, w):
        self.weights.append(w)

    def __call__(self, parent):
        """This layer will recieve an input tensor from 'parent'"""
        self.add_parent(parent)

def _create_layer_subclass(type_name):
    """Generate a new Layer sub-class based on lbann.proto.

    'type_name' is the name of a message in lbann.proto,
    e.g. 'FullyConnected'. It will be the name of the generated
    sub-class.

    """

    # Extract the names of all fields.
    layer_type = getattr(lbann_pb2, type_name)
    field_names = list(layer_type.DESCRIPTOR.fields_by_name.keys())

    # Name of corresponding field within the 'Layer' message in lbann.proto.
    layer_field_name = None
    for field in lbann_pb2.Layer.DESCRIPTOR.fields:
        if field.message_type and field.message_type.name == type_name:
            layer_field_name = field.name
            break

    # Sub-class constructor.
    def __init__(self, parents=[], children=[], weights=[],
                 name='', data_layout='data_parallel', hint_layer=None,
                 **kwargs):
        Layer.__init__(self, parents, children, weights,
                       name, data_layout, hint_layer)
        for field in kwargs:
            if field not in field_names:
                raise ValueError('Unknown argument {0}'.format(field))
        for field_name in field_names:
            if field_name in kwargs:
                setattr(self, field_name, kwargs[field_name])
            else:
                setattr(self, field_name, None)

    # Method for exporting a protobuf message.
    def export_proto(self):
        proto = Layer.export_proto(self)
        layer_message = getattr(proto, layer_field_name)
        layer_message.SetInParent() # Create empty message
        for field_name in field_names:
            v = getattr(self, field_name)
            if v is not None:
                if type(v) is list: # Repeated field
                    getattr(layer_message, field_name).extend(v)
                else: # Singular field
                    setattr(layer_message, field_name, v)
        return proto

    # Create sub-class.
    return type(type_name, (Layer,),
                {'__init__': __init__, 'export_proto': export_proto})

# Generate Layer sub-classes from lbann.proto
# Note: The list of skip fields must be updated if any new fields are
# added to the Layer message in lbann.proto
_skip_fields = set([
    'name', 'parents', 'children', 'data_layout', 'device_allocation',
    'weights', 'num_neurons_from_data_reader', 'freeze', 'hint_layer',
    'weights_data', 'top', 'bottom', 'type', 'motif_layer'
])
_generated_classes = {}
for field in lbann_pb2.Layer.DESCRIPTOR.fields:
    if field.name not in _skip_fields:
        type_name = field.message_type.name
        _generated_classes[type_name] = _create_layer_subclass(type_name)
_add_to_module_namespace(_generated_classes)

def traverse_layer_graph(start_layers):
    """Traverse a layer graph.

    The traversal starts from the entries in 'start_layers'. The
    traversal is in depth-first order, except that no layer is visited
    until all its parents have been visited.

    """
    layers = []
    visited = set()
    stack = [l for l in _make_iterable(start_layers)]
    while stack:
        l = stack.pop()
        layers.append(l)
        visited.add(l)
        for child in l.children:
            if ((child not in visited)
                and all([(i in visited) for i in child.parents])):
                stack.append(child)
    return layers

# ==============================================
# Weights and weight initializers
# ==============================================

# Set up weight initializers.
class Initializer:
    """Base class for weight initializers."""

    def __init__(self):
        pass

    def export_proto(self):
        """Construct and return a protobuf message."""
        raise NotImplementedError('export_proto not implemented')

def _create_init_subclass(type_name):
    """Generate a new Initializer sub-class based on lbann.proto.

    'type_name' is the name of a message in lbann.proto,
    e.g. 'ConstantInitializer'. It will be the name of the generated
    sub-class.

    """

    # Extract the names of all fields
    init_type = getattr(lbann_pb2, type_name)
    field_names = list(init_type.DESCRIPTOR.fields_by_name.keys())

    # Sub-class constructor.
    def __init__(self, **kwargs):
        Initializer.__init__(self)
        for field in kwargs:
            if field not in field_names:
                raise ValueError('Unknown argument {0}'.format(field))
        for field_name in field_names:
            if field_name in kwargs:
                setattr(self, field_name, kwargs[field_name])
            else:
                setattr(self, field_name, None)

    # Method for exporting a protobuf message.
    def export_proto(self):
        proto = init_type()
        for field_name in field_names:
            v = getattr(self, field_name)
            if v is not None:
                if type(v) is list: # Repeated field
                    getattr(proto, field_name).extend(v)
                else: # Singular field
                    setattr(proto, field_name, v)
        return proto

    # Create sub-class.
    return type(type_name, (Initializer,),
                {'__init__': __init__,
                 'export_proto': export_proto})

# Generate Initializer sub-classes from lbann.proto.
# Note: The list of skip fields must be updated if any new fields are
# added to the Weights message in lbann.proto
_skip_fields = set(['name', 'optimizer'])
_generated_classes = {}
for field in lbann_pb2.Weights.DESCRIPTOR.fields:
    if field.name not in _skip_fields:
        type_name = field.message_type.name
        _generated_classes[type_name] = _create_init_subclass(type_name)
_add_to_module_namespace(_generated_classes)

class Weights:
    """Trainable model parameters."""

    def __init__(self, name, initializer=None, optimizer=None):
        self.name = name
        self.initializer = initializer
        self.optimizer = optimizer

    def export_proto(self):
        """Construct and return a protobuf message."""
        proto = lbann_pb2.Weights()
        proto.name = self.name

        # Set initializer if needed
        if self.initializer:
            type_name = type(self.initializer).__name__
            field_name = None
            for field in lbann_pb2.Weights.DESCRIPTOR.fields:
                if field.message_type and field.message_type.name == type_name:
                    field_name = field.name
                    break
            init_message = getattr(proto, field_name)
            init_message.CopyFrom(self.initializer.export_proto())
            init_message.SetInParent()

        # TODO: implement
        if self.optimizer:
            raise NotImplementedError('Weights cannot handle non-default optimizers')

        return proto

# ==============================================
# Objective functions
# ==============================================

# Note: Currently, only layer terms and L2 weight regularization terms
# are supported in LBANN. If more terms are added, it may be
# worthwhile to autogenerate sub-classes of ObjectiveFunctionTerm.

class ObjectiveFunctionTerm:
    """Base class for objective function terms."""

    def __init__(self):
        pass

    def export_proto(self):
        """Construct and return a protobuf message."""
        raise NotImplementedError('export_proto not implemented')

class LayerTerm(ObjectiveFunctionTerm):
    """Objective function term that takes value from a layer."""

    def __init__(self, layer, scale=1.0):
        self.layer = layer
        self.scale = scale

    def export_proto(self):
        """Construct and return a protobuf message."""
        proto = lbann_pb2.LayerTerm()
        proto.layer = self.layer.name
        proto.scale_factor = self.scale
        return proto

class L2WeightRegularization(ObjectiveFunctionTerm):
    """Objective function term for L2 regularization on weights."""

    def __init__(self, weights=[], scale=1.0):
        self.scale = scale
        self.weights = [w for w in _make_iterable(weights)]

    def export_proto(self):
        """Construct and return a protobuf message."""
        proto = lbann_pb2.L2WeightRegularization()
        proto.scale_factor = self.scale
        proto.weights = ' '.join([w.name for w in self.weights])
        return proto

class ObjectiveFunction:
    """Objective function for optimization algorithm."""

    def __init__(self, terms=[]):
        """Create an objective function with layer terms and regularization.

        'terms' should be a sequence of 'ObjectiveFunctionTerm's and
        'Layer's.

        """
        self.terms = []
        for t in _make_iterable(terms):
            self.add_term(t)

    def add_term(self, term):
        """Add a term to the objective function.

        'term' may be a 'Layer', in which case a 'LayerTerm' is
        constructed and added to the objective function.

        """
        if isinstance(term, Layer):
            term = LayerTerm(term)
        self.terms.append(term)

    def export_proto(self):
        """Construct and return a protobuf message."""
        proto = lbann_pb2.ObjectiveFunction()
        for term in self.terms:
            term_message = term.export_proto()
            if type(term) is LayerTerm:
                proto.layer_term.extend([term_message])
            elif type(term) is L2WeightRegularization:
                proto.l2_weight_regularization.extend([term_message])
        return proto

# ==============================================
# Metrics
# ==============================================

class Metric:
    """Metric that takes value from a layer.

    Corresponds to a "layer metric" in LBANN. This may need to be
    generalized if any other LBANN metrics are implemented.

    """

    def __init__(self, layer, name='', unit=''):
        """Initialize a metric based of off layer."""
        self.layer = layer
        self.name = name if name else self.layer.name
        self.unit = unit

    def export_proto(self):
        """Construct and return a protobuf message."""
        proto = lbann_pb2.Metric()
        proto.layer_metric.layer = self.layer.name
        proto.layer_metric.name = self.name
        proto.layer_metric.unit = self.unit
        return proto

# ==============================================
# Callbacks
# ==============================================

class Callback:
    """Base class for callbacks."""

    def __init__(self):
        pass

    def export_proto(self):
        """Construct and return a protobuf message."""
        return lbann_pb2.Callback()

def _create_callback_subclass(type_name):
    """Generate a new Callback sub-class based on lbann.proto.

    'type_name' is the name of a message in lbann.proto,
    e.g. 'CallbackPrint'. It will be the name of the generated
    sub-class.

    """

    # Extract the names of all fields.
    callback_type = getattr(lbann_pb2, type_name)
    field_names = list(callback_type.DESCRIPTOR.fields_by_name.keys())

    # Name of corresponding field within the 'Callback' message in lbann.proto.
    callback_field_name = None
    for field in lbann_pb2.Callback.DESCRIPTOR.fields:
        if field.message_type and field.message_type.name == type_name:
            callback_field_name = field.name
            break

    # Sub-class constructor.
    def __init__(self, **kwargs):
        Callback.__init__(self)
        for field in kwargs:
            if field not in field_names:
                raise ValueError('Unknown argument {0}'.format(field))
        for field_name in field_names:
            if field_name in kwargs:
                setattr(self, field_name, kwargs[field_name])
            else:
                setattr(self, field_name, None)

    # Method for exporting a protobuf message.
    def export_proto(self):
        proto = Callback.export_proto(self)
        callback_message = getattr(proto, callback_field_name)
        callback_message.SetInParent() # Create empty message
        for field_name in field_names:
            v = getattr(self, field_name)
            if v is not None:
                if type(v) is list: # Repeated field
                    getattr(callback_message, field_name).extend(v)
                else: # Singular field
                    setattr(callback_message, field_name, v)
        return proto

    # Create sub-class.
    return type(type_name, (Callback,),
                {'__init__': __init__, 'export_proto': export_proto})

# Generate Callback sub-classes from lbann.proto
# Note: The list of skip fields must be updated if any new fields are
# added to the Callback message in lbann.proto
_skip_fields = set([])
_generated_classes = {}
for field in lbann_pb2.Callback.DESCRIPTOR.fields:
    if field.name not in _skip_fields:
        type_name = field.message_type.name
        _generated_classes[type_name] = _create_callback_subclass(type_name)
_add_to_module_namespace(_generated_classes)

# ==============================================
# Export models
# ==============================================

def save_model(filename, mini_batch_size, epochs,
               layers=[], weights=[], objective_function=None,
               metrics=[], callbacks=[]):
    """Save a model to file."""

    # Initialize protobuf message
    pb = lbann_pb2.LbannPB()
    pb.model.mini_batch_size = mini_batch_size
    pb.model.block_size = 256  # TODO: Make configurable.
    pb.model.num_epochs = epochs
    pb.model.num_parallel_readers = 0  # TODO: Make configurable
    pb.model.procs_per_model = 0  # TODO: Make configurable

    # Add layers
    layers = traverse_layer_graph(layers)
    pb.model.layer.extend([l.export_proto() for l in layers])

    # Add weights
    weights = set(weights)
    for l in layers:
        for w in l.weights:
            weights.add(w)
    pb.model.weights.extend([w.export_proto() for w in weights])

    # Add objective function
    if not objective_function:
        objective_function = ObjectiveFunction()
    pb.model.objective_function.CopyFrom(objective_function.export_proto())

    # Add metrics and callbacks
    pb.model.metric.extend([m.export_proto() for m in metrics])
    pb.model.callback.extend([c.export_proto() for c in callbacks])

    # Write to file
    with open(filename, 'wb') as f:
        f.write(google.protobuf.text_format.MessageToString(
            pb, use_index_order=True).encode())
