import sys, time, mysql.connector, geopy.point, geopy.distance, json

from geopy.point import Point


class SelectionDB:

    def __init__(self, uname, pw, db_name="doublefault", master_table="setting"):
        self.table_name = "selection"
        self.master_table = master_table
        try:
            self.db = mysql.connector.connect(user=uname, password=pw, database=db_name)
        except:
            self.db = None
            pass

        self.pokemons = {}
        dbh = self.db.cursor()
        dbh.execute("select dexno, name from pokemon")
        while True:
            row = dbh.fetchone()
            if row == None:
                break
            dexno, name = row
            self.pokemons[name] = dexno
            pass
        dbh.close()
        pass


    def drop_table(self):
        dbh = self.db.cursor()
        dbh.execute("drop table if exists %s" % self.table_name)
        dbh.close()
        self.db.commit()
        pass

    def create_table(self):
        dbh = self.db.cursor()
        sql = '''
create table if not exists {table}
   ( settingid int not null,
     dexno int not null,
     coord point not null,
     distance int not null,
     spatial index(coord),
     foreign key ( dexno ) references pokemon (dexno) on delete cascade,
     foreign key ( settingid ) references {master} (settingid) on delete cascade,
     primary key(settingid, dexno)
  ) engine=myisam;'''.format(table=self.table_name,
                             master=self.master_table)
        dbh.execute(sql)
        dbh.close()
        self.db.commit()
        pass


    def update_range(self, surrogateid, pokemons, coord, distance):
        dbh = self.db.cursor()
        reply = ""

        for pokemon in pokemons.split(","):
            dexno = self.pokemons.get(pokemon.lower().strip())
            if dexno is not None:
                inssql = "insert into %s (settingid, dexno, coord, distance) values " % self.table_name
                fmt = "({surrogateid}, {dexno}, GeomFromText('Point({coord.latitude} {coord.longitude})'), {distance})"
                values = fmt.format(coord=coord, distance=distance, surrogateid=surrogateid, dexno=dexno)
                fmt = " on duplicate key update coord = GeomFromText('Point({coord.latitude} {coord.longitude})'), distance={distance}, dexno={dexno}, settingid={surrogateid}"
                sql = inssql + values + fmt.format(coord=coord, distance=distance, surrogateid=surrogateid, dexno=dexno)
                dbh.execute(sql)
                pass
            else:
                reply = reply + pokemon + "\n"
                pass
            pass
        self.db.commit()
        dbh.close()
        return reply


    def update_coord(self, surrogateid, coord):
        dbh = self.db.cursor()
        sql = "update {table} set coord = GeomFromText('Point({coord.latitude} {coord.longitude})') where settingid = {surrogateid}".format(table=self.table_name, surrogateid=surrogateid, coord=coord)
        dbh.execute(sql)
        self.db.commit()
        dbh.close()
        return


    def update_distance(self, surrogateid, distance):
        dbh = self.db.cursor()
        sql = "update {table} set distance = {d} where settingid = {surrogateid}".format(table=self.table_name, surrogateid=surrogateid, d=distance)
        dbh.execute(sql)
        self.db.commit()
        dbh.close()
        return


    def purge(self, surrogateid):
        dbh = self.db.cursor()
        sql = "delete from {table} where settingid = {surrogateid}".format(table=self.table_name, surrogateid=surrogateid)
        dbh.execute(sql)
        self.db.commit()
        dbh.close()
        return


    def delete_pokemons(self, surrogateid, pokemons):
        dbh = self.db.cursor()
        reply = ""

        for pokemon in pokemons.split(","):
            dexno = self.pokemons.get(pokemon.lower().strip())
            if dexno is not None:
                delsql = "delete from %s where settingid=%d and dexno=%d" % (self.table_name, surrogateid, dexno)
                dbh.execute(delsql)
                pass
            else:
                reply = reply + "\n" + pokemon
                pass
            pass
        self.db.commit()
        dbh.close()
        return reply


    def set_user_selection(self, user):
        dbh = self.db.cursor()
        sql = "delete from {me} where settingid = {u.surrogateid}".format(me=self.table_name, u=user)
        dbh.execute(sql)
        inssql = "insert into %s (settingid, dexno, coord, distance) values " % self.table_name
        values = ",".join([ "({u.surrogateid}, {dexno}, GeomFromText('Point({u.coordinates.latitude} {u.coordinates.longitude})'), {u.distance})".format(u=user, dexno=self.pokemons[pokemon.lower().strip()]) for pokemon in user.pokemons.split(",")])
        sql = inssql + values
        dbh.execute(sql)
        self.db.commit()
        dbh.close()
        pass


    def set_pokemno_distance(self, user, pokemon, distance):
        dbh = self.db.cursor()
        sql = "insert into {table} (settingid, dexno, coord, distance) value ({u.discordid}, {dexno}, {coord}, {distance}) on duplicate key update coord={coord}".format(u=user,
                                                                                                                                                                         dexno=dexno,
                                                                                                                                                                         coord=coord,
                                                                                                                                                                         distance=distance)
        dbh.execute(sql)
        self.db.commit()
        dbh.close()
        pass


    def choose_listeners(self, pokemon, center):
        longest = geopy.distance.distance(kilometers=16)
        hexgon = "POLYGON((" + ",".join( [ "%g %g" % (point.latitude, point.longitude) for point in [ longest.destination(center, angle) for angle in range(0, 361, 60) ] ] ) + "))"
        dbh = self.db.cursor()
        sql = "select t2.discordid, t2.pm_channel, t1.distance, ST_AsText(t1.coord) from {me} as t1, {master} as t2 where t2.on_off = 'y' and MBRContains(ST_GeomFromText('{hexgon}'), t1.coord) and t1.settingid = t2.settingid and dexno={dexno}".format(me=self.table_name, master=self.master_table, hexgon=hexgon, dexno=self.pokemons[pokemon])
        dbh.execute(sql)

        users = []

        user_loc = Point()
        while True:
            row = dbh.fetchone()
            if row == None:
                break
            discordid, pm_channel, distance, coord = row
                              
            lat_lng = [ float(value) for value in coord.replace("POINT(", "").replace(")", "").split(" ") ]
            user_loc.latitude = lat_lng[0]
            user_loc.longitude = lat_lng[1]
            dt = geopy.distance.vincenty(center, user_loc)

            if dt.m <= distance:
                users.append((discordid, pm_channel, center, dt.m))
                pass
            pass


        dbh.close()
        self.db.commit()
        return users




    # This is for testing only however
    def find_users_by_pokemon(self, pokemon):
        dbh = self.db.cursor()
        sql = "select t2.discordid, ST_AsText(t1.coord) from {me} as t1, {master} as t2 where t1.dexno = {dexno} and t1.settingid = t2.settingid".format(me=self.table_name,
                                                                                                                                                         master=self.master_table,
                                                                                                                                                         dexno=self.pokemons[pokemon])
        dbh.execute(sql)

        users = []
        user_loc = Point()
        while True:
            row = dbh.fetchone()
            if row == None:
                break
            discordid, coord = row
                              
            lat_lng = [ float(value) for value in coord.replace("POINT(", "").replace(")", "").split(" ") ]
            user_loc.latitude = lat_lng[0]
            user_loc.longitude = lat_lng[1]

            users.append(discordid)
            pass


        dbh.close()
        self.db.commit()
        return users


    # This is for testing only however
    def report_for_user(self, discordid):
        dbh = self.db.cursor()
        fmt = "select t3.name, t1.distance, ST_AsText(t1.coord) from {me} as t1, {master} as t2, pokemon as t3 where t1.dexno = t3.dexno and t1.settingid = t2.settingid and t2.discordid = '{discordid}' order by t3.dexno"
        sql = fmt.format(me=self.table_name,
                         master=self.master_table,
                         discordid=discordid)
        # print(sql)
        dbh.execute(sql)

        outputs = []
        user_loc = Point()
        while True:
            row = dbh.fetchone()
            if row == None:
                break
            pokemon_name, distance, coord = row
            lat_lng = [ float(value) for value in coord.replace("POINT(", "").replace(")", "").split(" ") ]
            outputs.append("%s in %dm from https://maps.google.com/maps?q=%s,%s" % (pokemon_name, distance, lat_lng[0], lat_lng[1]))
            pass
        dbh.close()
        self.db.commit()
        return "\n".join(outputs)

    pass


def test():
    from subscriber import Subscriber
    from settingdb import SettingDB

    account = json.load(open("/var/lib/doublefault/account.json"))
    db = SettingDB(account["db-username"], account["db-password"], table_name="test")
    db.drop_table()
    db.create_table()

    user1 = Subscriber("user1", coordinates=Point(10.0001, 10.0001), pokemons="bulbasaur,ivysaur,venusaur")
    user2 = Subscriber("user2", coordinates=Point(10.0002, 10.0002), pokemons="ivysaur,venusaur")
    user3 = Subscriber("user3", coordinates=Point(10.0003, 10.0003), pokemons="venusaur")
    user4 = Subscriber("user4", coordinates=Point(10.1, 10.1), pokemons="bulbasaur,ivysaur,venusaur")
    user5 = Subscriber("user5", coordinates=Point(10.0005, 10.0005))

    users = [user1, user2, user3, user4, user5]

    for user in users:
        db.put_user_data(user)
        print ("user: {u.discordid},  surrogateid: {u.surrogateid}, pokemons: {u.pokemons}".format(u=user))
        pass


    seldb = SelectionDB(account["db-username"], account["db-password"], master_table="test")
    seldb.drop_table()
    seldb.create_table()

    for user in users:
        seldb.set_user_selection(user)
        pass

    print(seldb.find_users_by_pokemon("ivysaur"))

    print(seldb.choose_listeners("ivysaur", Point(10.0, 10.0)))

    print (seldb.report_for_user("user2"))
    pass



if __name__ == "__main__":
    test()
    pass
