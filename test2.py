import astpickle, ast
import codegen

class Test(object):
    def __init__(self, a):
        self._a = a

    def __to_node__(self):
        (a_func, a_node) = astpickle.to_node(self._a)
        return ([], a_func+[
            ast.Assign(targets=[ast.Name(id='rv', ctx=ast.Store())], 
                value=ast.Call(
                    func=astpickle.class_name(self),
                    args=[],
                    keywords=[ast.keyword('a', a_node)],
                    starargs=None,
                    kwargs=None
                )),
            ast.Return(value=ast.Name(id='rv', ctx=ast.Load()))
        ])
    
    def __repr__(self):
        return "Test(%s)" % self._a

class Test2(object):
    def __init__(self, a, b):
        self._a = a
        self._b = b
        
    def __to_node__(self):
        return constructor_call(self, a=self._a, b=self._b)
        
    def __repr__(self):
        (func, node) = self.__to_node__()
        return codegen.to_source(node)


class Test3(object):
    def __init__(self, a, b):
        self._a = a
        self._b = b

    def __repr__(self):
        return "Test3(a=%s,b=%s)" % (self._a,self._b)


import random
def gen_test(depth):
    if depth > 4:
        return None
    return Test2(gen_test(depth+1), gen_test(depth+1))

#x = gen_test(0)
x = Test({'a':2123, 'b':Test3(Test(1), True)})

func = astpickle.generate_module(x)
print "Generated code:"
print codegen.to_source(func)

print
print "Trying roundtrip"
code = astpickle.generate_code(x)

scope = {}
exec code in scope
create = scope['retval']

print create

# Try marshalling to disk
#import marshal
#f = open('test.out','wb')
#marshal.dump(code, f)
#f.close()

#import pickle
#f = open('test.pickle', 'wb')
#pickle.dump(x, f, -1)
#f.close()
