# simple tag/value 
import sqlite3
from geopy.point import Point
from geopy.location import Location
import geopy
from geopy.geocoders import Nominatim
from geopy.geocoders import GoogleV3

class cached_geolocator:
    geoloc = GoogleV3()

    def __init__(self):
        self.cachedb = sqlite3.connect("/var/spool/doublefault/geo.sl3")
        try:
            dbh = self.cachedb.execute("create table cache_lookup (addr varchar(1024) primary key, lat_lon char(64))")
            dbh.fetchall()
            dbh.close()
        except sqlite3.OperationalError as exc:
            # Probably table already created
            pass

        try:
            dbh = self.cachedb.execute("create table cache_reverse (lat_lon char(64) primary key, addrs varchar(1024))")
            dbh.fetchall()
            dbh.close()
        except sqlite3.OperationalError as exc:
            # Probably table already created
            pass

        pass

    # coord is Point object
    def lookup_reverse(self, coord):
        dbh = self.cachedb.execute("select addrs from cache_reverse where lat_lon = '{a.latitude},{a.longitude}'".format(a=coord))
        addrs = dbh.fetchone()
        dbh.close()
        if addrs is not None:
            print ("rev addr0 " + addrs[0])
            return addrs[0].split("\n")[0]

        revaddr = None
        try:
            revaddr = self.geoloc.reverse(coord)
        except socket.timeout:
            pass
        except geopy.exc.GeocoderTimedOut:
            pass
    
        if isinstance(revaddr, list):
            value = [ str(addr) for addr in revaddr ]
        else:
            value = [ str(revaddr) ]
            pass
            
        if revaddr is None:
            return ""

        addrs = "\n".join(value)
        
        dbh = self.cachedb.execute("insert into cache_reverse values('{a.latitude},{a.longitude}', '{addrs}')".format(a=coord, addrs=addrs))
        dbh.fetchall()
        self.cachedb.commit()
        dbh.close()

        return value[0]


    def lookup(self, addr):
        dbh = self.cachedb.execute("select lat_lon from cache_lookup where addr = '{a}'".format(a=addr))
        lat_lon = dbh.fetchone()
        dbh.close()
        if lat_lon is not None:
            print ("lookup lat_lon " + lat_lon[0])
            return Point( lat_lon[0] )

        log = None
        try:
            loc = self.geoloc.geocode(addr)
        except socket.timeout:
            pass
        except geopy.exc.GeocoderTimedOut:
            pass

        if loc is None:
            return None

        dbh = self.cachedb.execute("insert into cache_lookup values ( '{a}', '{ll.latitude},{ll.longitude}' )".format(a=addr, ll=loc))
        dbh.fetchall()
        self.cachedb.commit()
        dbh.close()
        
        return Point(loc.latitude, loc.longitude)


    pass

my_geo = cached_geolocator()

def get_cached_geolocator():
    return my_geo

if __name__ == "__main__":
    geo = cached_geolocator()
    v = geo.lookup("Arlington, MA")

    print (str(geo.lookup("Arlington, MA")))

    geo.lookup_reverse(Point('42.41,-71.15'))
    print (geo.lookup_reverse(Point('42.41,-71.15')))
    
    
