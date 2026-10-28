"""Geohash cell bounds; never interpret a cell as an intersection."""
BASE32 = '0123456789bcdefghjkmnpqrstuvwxyz'

def decode_geohash(value):
    if not isinstance(value, str) or not value or len(value) > 12:
        raise ValueError('Invalid geohash')
    lat, lon = [-90., 90.], [-180., 180.]
    even = True
    for char in value:
        if char not in BASE32:
            raise ValueError('Invalid geohash character')
        digit = BASE32.index(char)
        for mask in (16, 8, 4, 2, 1):
            bounds = lon if even else lat
            mid = sum(bounds) / 2
            bounds[0 if digit & mask else 1] = mid
            even = not even
    return dict(latitude=sum(lat)/2, longitude=sum(lon)/2,
                lat_min=lat[0], lat_max=lat[1], lon_min=lon[0], lon_max=lon[1])

def in_bengaluru(lat, lon):
    # Conservative study envelope; this is a screening box, not a city boundary.
    return 12.7 <= lat <= 13.3 and 77.3 <= lon <= 77.9
