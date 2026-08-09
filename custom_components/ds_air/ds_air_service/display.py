from enum import Enum


def display(o, d="") -> str:
    if isinstance(o, (int, str, bool, float)):
        return str(o)

    if isinstance(o, Enum):
        return o.name

    if isinstance(o, list):
        st = "["
        for i in range(len(o)):
            st += "\n" + d + str(i) + ": " + display(o[i], d + "    ")
        st += "]"
        return st

    li = dir(o)
    st = f"\033[31m{o.__class__.__name__}:\033[0m" + " {"
    for i in li:
        if (not i.startswith("_")) and (not callable(o.__getattribute__(i))):
            st += "\n" + d + i + ": " + display(o.__getattribute__(i), d + "    ")
    st += "}"
    return st
