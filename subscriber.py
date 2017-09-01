
import sys, time, mysql.connector, geopy.point, geopy.distance, json

from geopy.point import Point
from geopy.geocoders import Nominatim
from geopy.geocoders import GoogleV3

from settingdb import SettingDB
from selectiondb import SelectionDB

import geocache

class Subscriber:
    geoloc = geocache.get_cached_geolocator()
    
    async def set_address(self, address):
        self.address = address
        self.resolve_address()
        pass

    def resolve_address(self):
        loc = self.geoloc.lookup(self.address)
        if loc is not None:
            self.coordinates = Point(loc.latitude, loc.longitude)
            pass
        pass

    def __init__(self, discordid, pm_channel,
                 settingdb,
                 selectiondb,
                 coordinates=None,
                 mysql_geom_coord=None, distance=5000, on_off='y', pokemons="mareep,flaaffy,ampharos,unown,chansey,blissey,larvitar,pupitar,tyranitar,porygon", surrogateid=None):
        create_new_user = True

        self.coordinates = coordinates
        self.address = None
        self.settingdb = settingdb
        self.selectiondb = selectiondb
        self.surrogateid = surrogateid
        self.discordid = discordid
        self.pm_channel = pm_channel
        if mysql_geom_coord is not None:
            self.set_mysql_geom(mysql_geom_coord)
            pass
        self.distance = distance # in meter
        self.pokemons = pokemons #
        self.on_off = on_off # switch

        dbh = self.settingdb.db.cursor()
        sql = "select settingid, pm_channel, address, coordinates, on_off, distance from %s where discordid = '%s'" % (self.settingdb.table_name, discordid)
        dbh.execute(sql)
        while True:
            row = dbh.fetchone()
            if row == None:
                break
            create_new_user = False
            settingid, pm_channel, address, coord, on_off, distance = row
            self.surrogateid = settingid
            self.pm_channel = pm_channel
            self.address = address
            self.set_mysql_geom(coord)
            self.on_off = on_off
            self.distance = distance
            pass

        self.settingdb.db.commit()
        dbh.close()
        pass
    
    def set_mysql_geom(self, coord):
        lat_lng = [ float(value) for value in coord.replace("POINT(", "").replace(")", "").split(",") ]
        self.coordinates = Point(lat_lng[0], lat_lng[1])
        pass

        
    def __str__(self):
        return self.discordid


    def save_setting(self):
        self.settingdb.put_user_data(self)
        self.selectiondb.update_coord(self.surrogateid, self.coordinates)
        pass


    def report_for_user(self):
        return "%s\n%s" % (self.discordid, self.selectiondb.report_for_user(self.discordid))


    def set_range(self, pokemons, distance):
        return self.selectiondb.update_range(self.surrogateid, pokemons, self.coordinates, distance)


    def delete_pokemons(self, pokemons):
        return self.selectiondb.delete_pokemons(self.surrogateid, pokemons)


    # Only for test
    def select_listeners(udb, sdb, pokemon, center):
        longest = geopy.distance.distance(kilometers=10)
        hexgon = "POLYGON((" + ",".join( [ "%g %g" % (point.latitude, point.longitude) for point in [ longest.destination(center, angle) for angle in range(0, 361, 60) ] ] ) + "))"
        dbh = udb.db.cursor()
        sql = "select t2.discordid, t2.distance, ST_AsText(t1.coord) from {seldb} as t1, {master} as t2, pokemon as t3 where MBRContains(ST_GeomFromText('{hexgon}'), t1.coord) and t1.settingid = t2.settingid and t3.dexno = t1.dexno and t3.name='{pokemon}' and t2.on_off = 'y'".format(seldb=sdb.table_name, master=sdb.master_table, hexgon=hexgon, pokemon=pokemon)
        dbh.execute(sql)

        users = []

        user_loc = Point()
        while True:
            row = dbh.fetchone()
            if row == None:
                break
            discordid, distance, coord = row
                              
            lat_lng = [ float(value) for value in coord.replace("POINT(", "").replace(")", "").split(" ") ]
            user_loc.latitude = lat_lng[0]
            user_loc.longitude = lat_lng[1]
            dt = geopy.distance.vincenty(center, user_loc)

            if dt.m <= distance:
                users.append((discordid, center, round(dt.m), pokemon))
                pass
            pass


        dbh.close()
        udb.db.commit()
        return users

    pass



def test():

    account = json.load(open("/var/lib/doublefault/account.json"))
    udb = SettingDB(account["db-username"], account["db-password"])
    udb.drop_table()
    udb.create_table()

    seldb = SelectionDB(account["db-username"], account["db-password"])
    seldb.drop_table()
    seldb.create_table()

    user1 = Subscriber("user1", "1", udb, seldb, coordinates=Point(10.0001, 10.0001), pokemons="bulbasaur,ivysaur,venusaur")
    user2 = Subscriber("user2", "2", udb, seldb, coordinates=Point(10.0002, 10.0002), pokemons="ivysaur,venusaur")
    user3 = Subscriber("user3", "3", udb, seldb, coordinates=Point(10.0003, 10.0003), pokemons="venusaur")
    user4 = Subscriber("user4", "4", udb, seldb, coordinates=Point(10.1, 10.1), pokemons="bulbasaur,ivysaur,venusaur")
    user5 = Subscriber("user5", "5", udb, seldb, coordinates=Point(10.0005, 10.0005))

    users = [user1, user2, user3, user4, user5]

    for user in users:
        udb.put_user_data(user)
        seldb.update_range(user.surrogateid, user.pokemons, user.coordinates, user.distance)
        pass


    for user in users:
        temp = Subscriber(user.discordid, user.pm_channel, udb, seldb)
        print (temp.report_for_user())
        pass

    print("---")

    temp = Subscriber("user5", "5", udb, seldb)
    print ("surrogateid %d, pm_channel %s" % (temp.surrogateid, temp.pm_channel))
    temp.set_range("ivysaur,mareep,unown", 4000)

    print("---")

    users = Subscriber.select_listeners(udb, seldb, "ivysaur", Point(10.0, 10.0))
    for user in users:
        print (str(user))
        pass

    temp = Subscriber("user5", "5", udb, seldb)
    print (temp.report_for_user())

    temp.delete_pokemons("mareep,unown,ivysaur,dratini")

    print (temp.report_for_user())

    udb.drop_table()
    udb.create_table()
    seldb.drop_table()
    seldb.create_table()
    pass

if __name__ == "__main__":
    test()
    pass
