# simple tag/value 
import sqlite3
from geopy.point import Point
from geopy.location import Location
import geopy
from geopy.geocoders import Nominatim
from geopy.geocoders import GoogleV3
import socket
import urllib.parse
import time

class cached_geolocator:

    def __init__(self):
        self.cachedb = sqlite3.connect("/var/spool/doublefault/geo.sl3")
        try:
            dbh = self.cachedb.execute("create table cache_lookup (addr varchar(1024) primary key, lat_lon char(64), sponsor varchar, zipcode char(10))")
            dbh.fetchall()
            dbh.close()
        except sqlite3.OperationalError as exc:
            # Probably table already created
            pass

        try:
            dbh = self.cachedb.execute("create table cache_reverse (lat_lon char(64) primary key, addrs varchar(1024), sponsor varchar, zipcode char(10))")
            dbh.fetchall()
            dbh.close()
        except sqlite3.OperationalError as exc:
            # Probably table already created
            pass

        # self.new_geoloc()
        pass

    # def new_geoloc(self):
    #    self.geoloc = GoogleV3()
    #    pass

    # coord is Point object
    def lookup_reverse(self, coord):
        dbh = self.cachedb.execute("select addrs, sponsor, zipcode from cache_reverse where lat_lon = '{a.latitude},{a.longitude}'".format(a=coord))
        addrs = dbh.fetchone()
        dbh.close()
        if addrs is not None:
            return (urllib.parse.unquote(addrs[0]).split("\n")[0],
                    addrs[1] if addrs[1] is not None else "",
                    addrs[2] if addrs[2] is not None else "")

        revaddr = None
        geoloc = GoogleV3()

        for retrying in [ 0, 1 ]:
            try:
                revaddr = geoloc.reverse(coord)
            except socket.timeout:
                pass
            except geopy.exc.GeocoderTimedOut:
                pass
            if revaddr is not None:
                break
            if retrying == 0:
                time.sleep(0.2)
                pass
            pass
    
        if revaddr is None:
            return ("", "", "")

        if isinstance(revaddr, list):
            value = [ str(addr) for addr in revaddr ]
        else:
            value = [ str(revaddr) ]
            pass

        addrs = "\n".join(value)
        
        sql = "insert into cache_reverse (lat_lon, addrs, sponsor, zipcode) values('{a.latitude},{a.longitude}', '{addrs}', '', '')".format(a=coord, addrs=urllib.parse.quote(addrs))
        dbh = self.cachedb.execute(sql)
        dbh.fetchall()
        self.cachedb.commit()
        dbh.close()

        return (value[0].replace(", USA", ""), "", "")


    def lookup(self, addr):
        addr = addr.lower()
        dbh = self.cachedb.execute("select lat_lon, sponsor, zipcode from cache_lookup where addr = '{a}'".format(a=addr))
        lat_lon = dbh.fetchone()
        dbh.close()
        if lat_lon is not None:
            # print ("lookup lat_lon " + lat_lon[0])
            return (Point( lat_lon[0] ), lat_lon[1] if lat_lon[1] is not None else '', lat_lon[2] if lat_lon[2] is not None else '')
        
        geoloc = GoogleV3()
        loc = None
        for retrying in [ 0, 1 ]:
            try:
                loc = geoloc.geocode(addr)
            except socket.timeout:
                pass
            except geopy.exc.GeocoderTimedOut:
                pass
            if loc is not None:
                break
            if retrying == 0:
                time.sleep(0.2)
                pass
            pass

        if loc is None:
            return None

        dbh = self.cachedb.execute("insert into cache_lookup (addr, lat_lon, sponsor, zipcode) values( '{a}', '{ll.latitude},{ll.longitude}', '', '' )".format(a=addr, ll=loc))
        dbh.fetchall()
        self.cachedb.commit()
        dbh.close()
        
        return (Point(loc.latitude, loc.longitude), '', '')
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
    
    
