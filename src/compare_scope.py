from typing import List, Tuple, Union
from lang import *
from lang_address import *
from lang_datatype import *
from util import *
from compare_variable import *

# represents a "snapshot"/set of variables at a given PC during the program
# allows us to compare memory regions, etc. for variables at a given PC
class ConstPCVariableSetSnapshot(object):
    def __init__(self, varnodes: List[Varnode]):
        self.varnodes = varnodes

        # partition Varnodes into address spaces based on their address regions
        self.spaces: dict[AddressRegion, ConstPCAddressSpace] = self._partition_spaces()

    def _partition_spaces(self) -> 'List[ConstPCAddressSpace]':
        # collect Varnodes for each AddressRegion
        _map: dict[AddressRegion, List[Varnode]] = {}

        for varnode in self.varnodes:
            region = varnode.get_addr().get_region()
            if region in _map:
                _map[region].append(varnode)
            else:
                _map[region] = [varnode]

        # construct the ConstPCAddressSpace objects for each
        return dict([ (region, ConstPCAddressSpace(region, varnodes)) for (region, varnodes) in _map.items() ])

    def get_varnodes(self) -> List[Varnode]:
        return self.varnodes

    def flatten(self) -> 'ConstPCVariableSetSnapshot':
        return ConstPCVariableSetSnapshot(sum([ varnode.flatten() for varnode in self.varnodes ], []))

    def get_address_spaces(self) -> 'dict[AddressRegion, ConstPCAddressSpace]':
        return self.spaces

    # returns the correct ConstPCAddressSpace based on the AddressRegion key (or None)
    def get_address_space(self, region: AddressRegion) -> 'Union[ConstPCAddressSpace, None]':
        return self.spaces.get(region, None)

    def get_bytes(self, varnode_filter=None) -> int:
        return sum([ varnode.get_size() for varnode in self.varnodes if varnode_filter is None or varnode_filter(varnode) ])

    def _find_overlaps(self) -> Tuple[Varnode, Varnode]:
        return sum([ space._find_overlaps() for space in self.spaces.values() ], [])

    def __hash__(self) -> int:
        return hash(tuple(self.varnodes))

# compares 2 sets of variables representing a certain "scope" in the program (constant PC)
# this could mean a point in a function or the global scope
class ConstPCVariableSetSnapshotCompare2(object):
    def __init__(self,
        left: ConstPCVariableSetSnapshot,
        right: ConstPCVariableSetSnapshot
    ):
        self.left = left
        self.right = right

        # match left address spaces with right address spaces based on region
        # if there is a region that doesn't match, create empty space to compare with
        self.space_comparison_map: dict[AddressRegion, ConstPCAddressSpaceCompare2] = self._compare_spaces()

        self.varnode_compare_record_map: dict[Varnode, VarnodeCompareRecord] = self._make_varnode_compare_record_map()

    def _compare_spaces(self):
        
        _map: dict[AddressRegion, ConstPCAddressSpaceCompare2] = {}

        for region, left_space in self.left.get_address_spaces().items():
            right_space = self.right.get_address_space(region)
            right_space = right_space if right_space is not None else ConstPCAddressSpace(region, [])
            comparison = ConstPCAddressSpaceCompare2(left_space, right_space)
            _map[region] = comparison

        for region, right_space in self.right.get_address_spaces().items():
            if region not in _map:
                left_space = ConstPCAddressSpace(region, [])
                comparison = ConstPCAddressSpaceCompare2(left_space, right_space)
                _map[region] = comparison

        return _map

    # combine the subspace Varnode->VarnodeCompareRecord maps into a single map
    def _make_varnode_compare_record_map(self) -> 'dict[Varnode, VarnodeCompareRecord]':
        _map = {}
        for region, compare2 in self.space_comparison_map.items():
            _map.update(compare2.get_varnode_compare_record_map())
        return _map

    def get_left(self) -> ConstPCVariableSetSnapshot:
        return self.left

    def get_right(self) -> ConstPCVariableSetSnapshot:
        return self.right

    def bytes_overlapped(self, varnode_filter=None) -> int:
        return sum([ cmp.bytes_overlapped(varnode_filter=varnode_filter) for cmp in self.space_comparison_map.values() ])

    def get_bytes(self) -> int:
        return self.left.get_bytes()

    def compare_primitives(self) -> 'ConstPCVariableSetSnapshotCompare2':
        return ConstPCVariableSetSnapshotCompare2(self.left.flatten(), self.right.flatten())

    def get_varnode_compare_records(self) -> List[VarnodeCompareRecord]:
        return sum([ list(space.get_varnode_compare_records()) for space in self.space_comparison_map.values() ], [])

    def get_primitive_varnode_compare_records(self) -> List[VarnodeCompareRecord]:
        return self.compare_primitives().get_varnode_compare_records()

    def get_space_comparison(self, region: AddressRegion) -> 'Union[ConstPCAddressSpaceCompare2, None]':
        return self.space_comparison_map.get(region, None)

    def get_space_comparison_map(self) -> 'dict[AddressRegion, ConstPCAddressSpaceCompare2]':
        return self.space_comparison_map

    def get_varnode_compare_record(self, varnode: Varnode) -> 'Union[VarnodeCompareRecord, None]':
        return self.varnode_compare_record_map.get(varnode, None)

    def get_varnode_compare_record_map(self) -> 'dict[Varnode, VarnodeCompareRecord]':
        return self.varnode_compare_record_map

    # flatten all varnodes in left & right, then create new comparison & return
    def get_flattened_comparison(self) -> 'ConstPCVariableSetSnapshotCompare2':
        return ConstPCVariableSetSnapshotCompare2(self.left.flatten(), self.right.flatten())

    def select_varnode_compare_records(self, varnode_cmp_record_cond=None) -> List['VarnodeCompareRecord']:
        return [ record for record in self.get_varnode_compare_records() if varnode_cmp_record_cond is None or varnode_cmp_record_cond(record) ]

    def select_primitive_varnode_compare_records(self, varnode_cmp_record_cond=None) -> List['VarnodeCompareRecord']:
        return [ record for record in self.get_primitive_varnode_compare_records() if varnode_cmp_record_cond is None or varnode_cmp_record_cond(record) ]

    def select_varnode_comparisons(self, varnode_cmp_record_cond=None, varnode_cmp2_cond=None) -> List['VarnodeCompare2']:
        cmps = sum([ record.get_comparisons() for record in self.select_varnode_compare_records(varnode_cmp_record_cond=varnode_cmp_record_cond)], [])
        return [ cmp for cmp in cmps if varnode_cmp2_cond is None or varnode_cmp2_cond(cmp) ]

    def select_primitive_varnode_comparisons(self, varnode_cmp_record_cond=None, varnode_cmp2_cond=None) -> List['VarnodeCompare2']:
        cmps = sum([ record.get_comparisons() for record in self.select_primitive_varnode_compare_records(varnode_cmp_record_cond=varnode_cmp_record_cond)], [])
        return [ cmp for cmp in cmps if varnode_cmp2_cond is None or varnode_cmp2_cond(cmp) ]

    def __hash__(self) -> int:
        return hash((self.left, self.right))

    def show_summary(self, indent=0) -> str:
        # s = "BYTES OVERLAPPED = {}\nTOTAL BYTES = {}\nBYTE RECOVERY % = {}%\n".format(
        #     self.bytes_overlapped(),
        #     self.get_bytes(),
        #     0 if self.get_bytes() == 0 else 100.0 * (self.bytes_overlapped() / self.get_bytes())
        # )
        s = ""
        for record in self.varnode_compare_record_map.values():
            s += record.show_summary(indent=0)
        s += "\n"

        return indent_str(s, indent)


# associates an AddressRegion (group of 0+ addresses) with the varnodes that occupy it for a particular PC in the program
class ConstPCAddressSpace(object):
    def __init__(self,
        region: AddressRegion, # determines the region of addresses occupied by this space
        varnodes: List[Varnode] # the list of varnodes within the region
    ):
        self.region = region
        self.varnodes = sorted(varnodes, key=lambda v: v.get_addr()) if self.rangeable() else varnodes

        for varnode in self.varnodes:
            self._verify_region(varnode)

        assert(not self._find_overlaps())

    def _verify_region(self, varnode: Varnode):
        assert( varnode.get_addr().get_region() == self.region )

    def get_region(self) -> AddressRegion:
        return self.region

    def get_varnodes(self) -> List[Varnode]:
        return self.varnodes

    # is this address space "rangeable" / can the addresses be ordered?
    # by default, return False
    def rangeable(self):
        return self.region.is_range()

    # can this space be compared to another?
    def comparable(self):
        return self.rangeable()

    # find erroneous overlaps within this space of varnodes
    def _find_overlaps(self) -> Tuple[Varnode, Varnode]:
        return [ (l, r) for l, r in self._get_comparison_pairs_rangeable(self) if l != r and l is not r and hash(l) != hash(r) ] if self.rangeable() else []

    # by default, no comparison pairs can be formed
    def get_comparison_pairs(self, other: 'ConstPCAddressSpace') -> 'List[Tuple[Varnode, Varnode]]':
        return self._get_comparison_pairs_rangeable(other) if self.rangeable() else []

    def _get_comparison_pairs_rangeable(self, other: 'ConstPCAddressSpace') -> 'List[Tuple[Varnode, Varnode]]':
        # create iterator the "merges" the 2 address spaces
        zipper = OrderedZipper(
            self.get_varnodes(),
            other.get_varnodes(),
            key=lambda varnode: varnode.get_addr() # sort by addr
        )

        # accumulate a list of Varnode pairs that overlap between the sets
        pairs = []

        # state variables
        # If prev_left set, then it implies that the prev_left addr range
        # could possibly overlap with the next right addr range.
        # The same applies for prev_right.

        # Varnode | None
        prev_left = None
        # Varnode | None
        prev_right = None

        def _addr_range_overlap(l: Varnode, r: Varnode) -> bool:
            return l.get_addr_range().does_overlap(r.get_addr_range())

        for cur in zipper:
            if cur.is_left(): # left list was iterated
                left_varnode = cur.get_value()
                if prev_right:
                    if _addr_range_overlap(left_varnode, prev_right):
                        pairs.append((left_varnode, prev_right))
                    else:
                        prev_right = None
                prev_left = left_varnode

            elif cur.is_right(): # right list was iterated
                right_varnode = cur.get_value()
                if prev_left:
                    if _addr_range_overlap(prev_left, right_varnode):
                        pairs.append((prev_left, right_varnode))
                    else:
                        prev_left = None
                prev_right = right_varnode

            elif cur.is_conflict(): # left & right varnodes matched start addr
                left_varnode, right_varnode = cur.get_value()
                if _addr_range_overlap(left_varnode, right_varnode):
                    pairs.append((left_varnode, right_varnode))
                prev_left = left_varnode
                prev_right = right_varnode

        return pairs

    def __hash__(self) -> int:
        return hash((self.region, tuple(self.varnodes)))


# compare the varnode sets in left and right address spaces
class ConstPCAddressSpaceCompare2(object):
    def __init__(self,
        left: ConstPCAddressSpace,
        right: ConstPCAddressSpace
    ):
        # ensure regions are matched
        assert ( left.get_region() == right.get_region() )

        self.left = left
        self.right = right
        
        # gather Varnode comparisons for the left "target" set
        self.varnode_comparisons: List[VarnodeCompare2] = []

        # map of Varnode -> VarnodeCompareRecord for each (left, right) address space
        # we will update these maps each time we make a comparison
        self.varnode_compare_record_map: dict[Varnode, VarnodeCompareRecord] = \
            dict([(varnode, VarnodeCompareRecord(varnode)) for varnode in self.left.get_varnodes()])

        # merge the two sets and get pairs of varnodes to compare
        # based on address overlaps
        compare_pairs: List[Tuple[Varnode, Varnode]] = left.get_comparison_pairs(right)

        # for each pair to compare, make the comparison and update internal state
        for left_varnode, right_varnode in compare_pairs:
            self._compare(left_varnode, right_varnode)

    # compare the 2 varnodes and update the internal state
    def _compare(self, left_varnode: Varnode, right_varnode: Varnode):
        # do comparison
        comparison = VarnodeCompare2(left_varnode, right_varnode)

        # store into varnode_comparisons
        if comparison and comparison.does_overlap():
            self.varnode_comparisons.append(comparison)
            self.varnode_compare_record_map[left_varnode].add_comparison(comparison)

    def get_varnode_compare_record(self, varnode: Varnode) -> Union[VarnodeCompareRecord, None]:
        return self.varnode_compare_record_map.get(varnode, None)
    
    def get_varnode_compare_record_map(self) -> 'dict[Varnode, VarnodeCompareRecord]':
        return self.varnode_compare_record_map

    def get_varnode_compare_records(self) -> List[VarnodeCompareRecord]:
        return self.varnode_compare_record_map.values()

    def bytes_overlapped(self, varnode_filter=None) -> int:
        return sum([ cmp.bytes_overlapped() for cmp in self.varnode_comparisons if varnode_filter is None or varnode_filter(cmp.get_left())] )

    def __hash__(self) -> int:
        return hash((self.left, self.right))
