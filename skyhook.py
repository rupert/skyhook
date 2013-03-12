import ctypes as c
from ctypes.util import find_library
from collections import namedtuple
import argparse

class NameCode(c.Structure):
    """A WPS_NameCode struct"""
    _fields_ = [
        ("name", c.c_char_p),
        ("code", c.c_char * 3)]

class StreetAddress(c.Structure):
    """A WPS_StreetAddress struct"""
    _fields_ = [
        ("street_number", c.c_char_p),
        ("address_line", c.POINTER(c.c_char_p)),
        ("city", c.c_char_p),
        ("postal_code", c.c_char_p),
        ("county", c.c_char_p),
        ("province", c.c_char_p),
        ("state", NameCode),
        ("region", c.c_char_p),
        ("country", NameCode)]

class Location(c.Structure):
    """A WPS_Location struct"""
    _fields_ = [
        ("latitude", c.c_double),
        ("longitude", c.c_double),
        ("hpe", c.c_double),
        ("nap", c.c_ushort),
        ("speed", c.c_double),
        ("bearing", c.c_double),
        ("street_address", c.POINTER(StreetAddress)),
        ("ncell", c.c_ushort),
        ("nlac", c.c_ushort),
        ("nsat", c.c_ushort),
        ("altitude", c.c_double),
        ("type", c.c_uint),
        ("age", c.c_ulong)]

class SimpleAuthentication(c.Structure):
    """A WPS_SimpleAuthentication struct"""
    _fields_ = [
        ("username", c.c_char_p),
        ("realm", c.c_char_p)]

def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    reverse = {value:key for key, value in enums.iteritems()}
    enums['reverse_mapping'] = reverse
    return type('Enum', (), enums)

WPS_ReturnCode = enum(
    OK=0,
    ERROR_SCANNER_NOT_FOUND=1,
    ERROR_WIFI_NOT_AVAILABLE=2,
    ERROR_NO_WIFI_IN_RANGE=3,
    ERROR_UNAUTHORIZED=4,
    ERROR_SERVER_UNAVAILABLE=5,
    ERROR_LOCATION_CANNOT_BE_DETERMINED=6,
    ERROR_PROXY_UNAUTHORIZED=7,
    ERROR_FILE_IO=8,
    ERROR_INVALID_FILE_FORMAT=9,
    ERROR_TIMEOUT=10,
    NOT_APPLICABLE=11,
    GEOFENCE_ERROR=12,
    ERROR_NOT_TUNED=13,
    NOMEM=98,
    ERROR=99
)

WPS_StreetAddressLookup = enum(
    NO_STREET_ADDRESS_LOOKUP=0,
    LIMITED_STREET_ADDRESS_LOOKUP=1,
    FULL_STREET_ADDRESS_LOOKUP=2
)

Coordinate = namedtuple("Coordinate", ["latitude", "longitude"])

class SkyhookError(Exception):
    """Exception rasied when a Skyhook API call fails"""

    def __init__(self, return_code):
        Exception.__init__(self, "Skyhook Error {}: {}".format(
            return_code,
            WPS_ReturnCode.reverse_mapping[return_code])
        )
        self.return_code = return_code

class Skyhook(object):
    """Wrapper around the Skyhook library"""

    library = find_library("wpsapi")

    if library == None:
        raise IOError("wpsapi library not found")

    cdll = c.CDLL(library)

    # WPS_location
    cdll.WPS_location.argtypes = [
        c.POINTER(SimpleAuthentication),
        c.c_uint,
        c.POINTER(c.POINTER(Location))
    ]
    cdll.WPS_location.restype = c.c_uint

    # WPS_register_user
    cdll.WPS_register_user.argtypes = [
        c.POINTER(SimpleAuthentication),
        c.POINTER(SimpleAuthentication),
    ]
    cdll.WPS_register_user.restype = c.c_uint

    # WPS_free_location
    cdll.WPS_free_location.argtypes = [c.POINTER(Location)]

    def __init__(self, username, realm):
        self.authentication = SimpleAuthentication()
        self.authentication.username = username
        self.authentication.realm = realm

        # Auto-registration
        return_code = Skyhook.cdll.WPS_register_user(
            c.byref(self.authentication),
            None
        )

        if return_code != WPS_ReturnCode.OK:
            raise SkyhookError(return_code)

    def location(self, street_address_lookup=WPS_StreetAddressLookup.NO_STREET_ADDRESS_LOOKUP):
        """Find current location, return a pointer to a Location object"""

        location_p = c.POINTER(Location)()

        return_code = self.cdll.WPS_location(
            c.byref(self.authentication),
            street_address_lookup,
            c.byref(location_p)
        )

        if return_code == WPS_ReturnCode.OK:
            return location_p
        else:
            raise SkyhookError(return_code)

    def coordinate(self):
        """Get current GPS coordinate"""

        location_p = self.location()
        coordinate = Coordinate(location_p.contents.latitude, location_p.contents.longitude)
        Skyhook.free_location(location_p)
        return coordinate

    @classmethod
    def free_location(cls, location_p):
        """Free a Location object"""

        cls.cdll.WPS_free_location(location_p)

def address(address_line):
    """Convert an array of address lines to a string"""

    i = 0

    while address_line[i] != None:
        i += 1

    return '\n'.join(address_line[0:i])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('username')
    parser.add_argument('realm')
    args = parser.parse_args()

    skyhook = Skyhook(args.username, args.realm)
    
    # Print our current street address
    location_p = skyhook.location(WPS_StreetAddressLookup.FULL_STREET_ADDRESS_LOOKUP)
    print address(location_p.contents.street_address.contents.address_line)    
    skyhook.free_location(location_p)

    # Print our current GPS position
    print skyhook.coordinate()