# cython: language_level=3, embedsignature=True
# cython: optimize.use_switch=True
# cython: boundscheck=False
# cython: wraparound=False

cdef class CurrencyConfig:
    cdef public int guild_id
    cdef public str currency_name
    cdef public str currency_icon

    def __cinit__(self, int guild_id, str currency_name, str currency_icon):
        self.guild_id = guild_id
        self.currency_name = currency_name
        self.currency_icon = currency_icon

    cpdef dict to_dict(self):
        return {
            "guild_id": self.guild_id,
            "currency_name": self.currency_name,
            "currency_icon": self.currency_icon,
        }
