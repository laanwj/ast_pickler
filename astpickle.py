'''
Pickle an object graph by generating (and compiling) a Python 
abstract syntax tree that constructs the objects, and compiling this to Python code.
'''
import ast
import marshal

class State(object):
    '''
    State object for ast-pickler. Bundles administrative structures required for serialization.
    '''
    def __init__(self):
        self.reset()

    def reset(self):
        self.xcount = 0
        self.imports = set()
    
    def unique_name(self):
        '''Generate a unique identifier'''
        self.xcount += 1
        return 'func_%08x' % self.xcount

    def class_name(self, obj):
        '''
        Return the class name for an object, as ast node. Also adds the neccesary
        import to the header.
        '''
        cls = obj.__class__
        module = cls.__module__
        self.imports.add(module)
        
        path = module.split('.')
        path.append(cls.__name__)
        
        # build attribute-path from '.' - separated expression
        rv = ast.Name(id=path[0], ctx=ast.Load())
        for path_part in path[1:]:
            rv = ast.Attribute(value=rv, attr=path_part, ctx=ast.Load())
        return rv

    def constructor_call(self, obj, *args, **kwargs):
        '''
        Create and return a constructor call node with parameters specified by args and kwargs.
        '''
        args_nodes = []
        kwargs_nodes = []
        funcs = []

        for value in args:
            (a_func, a_node) = to_node(value)
            args_nodes.append(a_node)
            funcs += a_func

        for key, value in kwargs.iteritems():        
            (a_func, a_node) = to_node(value)
            kwargs_nodes.append(ast.keyword(key, a_node))
            funcs += a_func
            
        return (funcs, ast.Call(
                    func=self.class_name(obj),
                    args=args_nodes,
                    keywords=kwargs_nodes,
                    starargs=None,
                    kwargs=None
                ))

    def build_function(self, func, body):
        '''
        Builds both a function and a function call wrapping body (a bit convoluted due to lack
        of general anonymous functions in Python).
        '''
        func_name = self.unique_name()

        func.append(ast.FunctionDef(name=func_name, args=ast.arguments(args=[],
            vararg=None, kwarg=None, defaults=[]), body=body, decorator_list=[]))

        node = ast.Call(
            func=ast.Name(id=func_name, ctx=ast.Load()),
            args=[],
            keywords=[],
            starargs=None,
            kwargs=None
            )
        return (func, node)

    def to_node(self, obj):
        '''
        Convert an object to a tuple (funcs, node), in which 
        func is a list of 0 or more FunctionDefs, and node is a 
        expression node that creates the object (using the function defs).
        '''
        if isinstance(obj, (int, long, float)):
            return ([], ast.Num(n=obj))
        elif isinstance(obj, (str, unicode)):
            return ([], ast.Str(s=obj))
        elif isinstance(obj, set):
            func = []
            values = []
            for x in obj:
                (vfunc, vnode) = self.to_node(x)
                func += vfunc
                values.append(vnode)
            return (func, ast.Set(elts=values))
        elif isinstance(obj, dict):
            func = []
            keys = []
            values = []
            for key,value in obj.iteritems():
                (kfunc, knode) = self.to_node(key)
                func += kfunc
                (vfunc, vnode) = self.to_node(value)
                func += vfunc
                keys.append(knode)
                values.append(vnode)
            return (func, ast.Dict(keys=keys, values=values))
        elif obj is None:
            return ([], ast.Name('None', ast.Load()))
        elif obj is True:
            return ([], ast.Name('True', ast.Load()))
        elif obj is False:
            return ([], ast.Name('False', ast.Load()))
        elif hasattr(obj, '__to_node__'):
            (func,node) = obj.__to_node__(self)
            if isinstance(node, list):
                # Multiple statements;  build a function around it
                (func, node) = self.build_function(func, node)

            return (func, node)
        else: # Build object from scratch
            (objdict_func, objdict_node) = self.to_node(obj.__dict__)
            tempvar_ld = ast.Name(id='obj', ctx=ast.Load())
            tempvar_st = ast.Name(id='obj', ctx=ast.Store())
            body = [
                # obj = $cls.__new()
                ast.Assign(targets=[tempvar_st], value=ast.Call(
                    func=ast.Attribute(value=self.class_name(obj), attr='__new__', ctx=ast.Load()),
                    args=[self.class_name(obj)],
                    keywords=[],
                    starargs=None,
                    kwargs=None
                )),
                # obj.__dict__ = $objdict
                ast.Assign(targets=[ast.Attribute(value=tempvar_ld, attr='__dict__', ctx=ast.Store())], 
                    value=objdict_node),
                #
                ast.Return(value=tempvar_ld)
            ]
            return self.build_function(objdict_func, body)
    
def generate_module(obj):
    '''
    Build and return the ast of a module that constructs object `obj`.
    '''
    state = State()

    func, node = state.to_node(obj)

    # Import needed modules into scope
    import_node = ast.Import(names=[ast.alias(name=module, asname=None) for module in state.imports])

    func = ast.Module(body=[import_node]+func+
        [
        ast.Assign(targets=[ast.Name(id='retval', ctx=ast.Store())], 
                   value=node),
        ])

    ast.fix_missing_locations(func)
    return func

def generate_code(obj):
    '''
    Generate and return a code object that constructs object 'obj'.
    '''
    func = generate_module(obj)
    code = compile(func, '<string>', 'exec')
    return code

#################################
# Marshal/pickle-like interface #
#################################
def dump(obj, f):
    '''
    Write an object to a file. Analogous to pickle.dump.
    '''
    code = generate_code(obj)
    marshal.dump(code, f)

def dumps(obj):
    '''
    Write an object to a string, and return the string. Analogous to pickle.dumps.
    '''
    code = generate_code(obj)
    return marshal.dumps(code)

def load(f):
    '''
    Load object from a file. Analogous to pickle.load.
    '''
    code = marshal.load(f)
    scope = {}
    exec code in scope
    return scope['retval']

def loads(s):
    '''
    Load object from a string. Analogous to pickle.loads.
    '''
    code = marshal.loads(s)
    scope = {}
    exec code in scope
    return scope['retval']

