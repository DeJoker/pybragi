__version__ = "0.0.21.post1"

__version_tuple__ = tuple(num for num in __version__.split('.'))

pybragi_version_num = (
    int(__version_tuple__[0]) * 1000
    + int(__version_tuple__[1]) * 100
    + int(__version_tuple__[2])
)
