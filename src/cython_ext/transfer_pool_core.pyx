# cython: language_level=3, embedsignature=True

cdef class TransferCheckStateStore:
    cdef dict _states
    cdef object _required

    def __cinit__(self):
        self._states = {}
        self._required = frozenset({"balance", "cooldown", "daily_limit"})

    cpdef bint record(self, object transfer_id, str check_type, int result):
        cdef dict state = <dict>self._states.get(transfer_id)
        if state is None:
            state = {}
            self._states[transfer_id] = state
        state[check_type] = result
        return set(state.keys()).issuperset(self._required)

    cpdef object get_state(self, object transfer_id):
        return self._states.get(transfer_id, {})

    cpdef bint all_passed(self, object transfer_id):
        cdef dict state = <dict>self._states.get(transfer_id)
        if not state:
            return False
        cdef object required = self._required
        for name in required:
            if state.get(name) != 1:
                return False
        return True

    cpdef bint remove(self, object transfer_id):
        return self._states.pop(transfer_id, None) is not None

    cpdef void clear(self):
        self._states.clear()
