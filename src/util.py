from collections import OrderedDict

# _map: the original unordered dict
# transform: the transformation to apply to the key before ordering
def ordered_dict_by_key(_map: dict, transform=lambda x: x) -> OrderedDict:
    return OrderedDict(sorted(_map.items(), key=lambda pair: transform(pair[0])))

def indent_str(s: str, indent: int) -> str:
    if indent <= 0:
        return s
    
    lines = s.splitlines()
    return "".join(["{}{}\n".format("\t" * indent, _s) for _s in lines])

def count(_iter, start=0, step=1):
    __iter = iter(_iter)
    cnt = start
    while try_next(__iter) is not None:
        cnt += step
    return cnt

# intercept StopIteration from the vanilla next() method and return None instead
def try_next(_iter):
    try:
        return next(_iter)
    except StopIteration:
        return None

# An Iterator class that "zips" 2 ordered iterators together
# Produces and ordered iterator of 'Left', 'Right', and 'Conflict' objects
class OrderedZipper(object):

    class ZipItem(object):
        def __init__(self):
            pass

        # get the value(s)
        # () -> A | (A, A), where A the type of the obj being stored
        def get_value(self):
            raise NotImplementedError()

        # get the index(es) of this item from the original input iterator(s)
        # () -> int | (int, int)
        def get_idx(self):
            raise NotImplementedError()
        
        def is_left(self):
            return False
        
        def is_right(self):
            return False

        def is_conflict(self):
            return False

    class Left(ZipItem):
        def __init__(self, obj, idx):
            super(__class__, self).__init__()
            self.obj = obj
            self.idx = idx

        def get_value(self):
            return self.obj

        def get_idx(self):
            return self.idx

        def is_left(self):
            return True

        def __str__(self):
            return "<Left({})>".format(self.obj)

        def __repr__(self):
            return self.__str__()

    class Right(ZipItem):
        def __init__(self, obj, idx):
            super(__class__, self).__init__()
            self.obj = obj
            self.idx = idx

        def get_value(self):
            return self.obj

        def get_idx(self):
            return self.idx

        def is_right(self):
            return True

        def __str__(self):
            return "<Right({})>".format(self.obj)

        def __repr__(self):
            return self.__str__()

    class Conflict(ZipItem):
        def __init__(self, objl, idxl, objr, idxr):
            super(__class__, self).__init__()
            self.objl = objl
            self.idxl = idxl
            self.objr = objr
            self.idxr = idxr

        def get_value(self):
            return (self.objl, self.objr)

        def get_idx(self):
            return (self.idxl, self.idxr)

        def is_conflict(self):
            return True

        def __str__(self):
            return "<Conflict({},{})>".format(self.objl, self.objr)

        def __repr__(self):
            return self.__str__()

    # left: Iterator<A>
    # right: Iterator<A>
    # key: (Ord B) => A -> B
    def __init__(self, left, right, key=None):
        self.key = key if key is not None else (lambda v: v)
        self.left = iter(sorted(left, key=self.key))
        self.right = iter(sorted(right, key=self.key))

        # get the first elements of each iterator
        self.curleft = try_next(self.left)
        self.curright = try_next(self.right)

        # keep track of the current index of each of the iterators
        self.left_idx = 0
        self.right_idx = 0

    def _exhausted_left(self):
        return self.curleft == None

    def _exhausted_right(self):
        return self.curright == None

    def __next__(self):
        if self._exhausted_left():
            self.curright = next(self.right)
            self.right_idx += 1
            return OrderedZipper.Right(self.curright, self.right_idx)

        elif self._exhausted_right():
            self.curleft = next(self.left)
            self.left_idx += 1
            return OrderedZipper.Left(self.curleft, self.left_idx)

        elif self.key(self.curleft) == self.key(self.curright):
            ret = OrderedZipper.Conflict(self.curleft, self.left_idx, self.curright, self.right_idx)
            self.curleft = try_next(self.left)
            self.left_idx += 1
            self.curright = try_next(self.right)
            self.right_idx += 1
            return ret

        elif self.key(self.curleft) < self.key(self.curright):
            ret = OrderedZipper.Left(self.curleft, self.left_idx)
            self.curleft = try_next(self.left)
            self.left_idx += 1
            return ret

        elif self.key(self.curleft) > self.key(self.curright):
            ret = OrderedZipper.Right(self.curright, self.right_idx)
            self.curright = try_next(self.right)
            self.right_idx += 1
            return ret

        else:
            raise StopIteration

    def __iter__(self):
        return self
