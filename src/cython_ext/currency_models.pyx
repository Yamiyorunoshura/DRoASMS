# cython: language_level=3, embedsignature=True

cdef class CurrencyConfigResult:
    cdef public str currency_name
    cdef public str currency_icon

    def __cinit__(self, str currency_name, str currency_icon):
        self.currency_name = currency_name
        self.currency_icon = currency_icon

    def __repr__(self):
        return (
            f"CurrencyConfigResult(currency_name={self.currency_name!r}, "
            f"currency_icon={self.currency_icon!r})"
        )
