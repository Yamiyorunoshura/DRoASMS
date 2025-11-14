# cython: language_level=3, embedsignature=True

cdef class GovernmentDepartment:
    cdef public str department_id
    cdef public str display_name
    cdef public int level
    cdef public object parent_id
    cdef public bint is_council
    cdef public object subordinates

    def __cinit__(self, str department_id, str display_name, int level,
                  object parent_id=None, bint is_council=False, object subordinates=None):
        self.department_id = department_id
        self.display_name = display_name
        self.level = level
        self.parent_id = parent_id
        self.is_council = is_council
        self.subordinates = subordinates


cdef class DepartmentEdge:
    cdef public str parent_id
    cdef public str child_id
    cdef public int weight

    def __cinit__(self, str parent_id, str child_id, int weight=1):
        self.parent_id = parent_id
        self.child_id = child_id
        self.weight = weight
