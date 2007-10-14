
class LifeTime(object):
    __slots__ = "typeid address size varsize birth death".split()
    def __init__(self, typeid, address, size, varsize, birth, death=-1):
        self.typeid = typeid
        self.address = address
        self.size = size
        self.birth = birth
        self.death = death

def parse_file(f, callback):
    unknown_lifetime = {}
    current = 0
    for line in f:
        line = line.split()
        if line[0] == "free":
            _, typeid, address = line
            typeid = int(typeid)
            address = int(address, 16)
            unknown = unknown_lifetime.pop(address)
            unknown.death = current
            callback(unknown)
        else:
            if line[0] == "malloc_varsize":
                varsize = True
            else:
                varsize = False
            _, typeid, size, address = line
            size = int(size)
            typeid = int(typeid)
            address = int(address, 16)
            new = LifeTime(typeid, address, size, varsize, current)
            unknown_lifetime[address] = new
            current += size
    for unknown in unknown_lifetime.itervalues():
        unknown.death = current
        callback(unknown)
    return all

def collect_all(f):
    all = []
    def callback(obj):
        all.append(obj)
    parse_file(f, callback)
    return all

