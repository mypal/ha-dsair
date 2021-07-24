from enum import Enum


def display(o, d='') -> str:
    if type(o) == int or type(o) == str or type(o) == bool or type(o) == float:
        return str(o)
    elif isinstance(o, Enum):
        return o.name
    elif type(o) == list:
        st = '['
        for i in range(len(o)):
            st += '\n' + d + str(i) + ': ' + display(o[i], d + '    ')
        st += ']'
        return st
    else:
        li = dir(o)
        st = ("\033[31m%s:\033[0m"%o.__class__.__name__) + ' {'
        for i in li:
            if (not i.startswith('_')) and (not callable(o.__getattribute__(i))):
                st += '\n' + d + i + ': ' + display(o.__getattribute__(i), d + '    ')
        st += '}'
        return st
