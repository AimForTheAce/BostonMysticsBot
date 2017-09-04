
import sys, time, mysql.connector, geopy.point, geopy.distance, json

from geopy.point import Point


class SettingDB:

    def __init__(self, uname, pw, table_name="setting", db_name="doublefault"):
        self.table_name = table_name
        try:
            self.db = mysql.connector.connect(user=uname, password=pw, database=db_name)
        except:
            self.db = None
            pass
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
   ( settingid int auto_increment primary key,
     discordid char(64) not null unique,
     pm_channel char(32) not null unique,
     on_off char(1) not null default 'y',
     address varchar(255),
     coordinates char(64),
     distance int not null default 1500
   ) engine=MyISAM'''.format(table=self.table_name)
        dbh.execute(sql)
        dbh.close()
        self.db.commit()
        pass


    def put_user_data(self, user):
        dbh = self.db.cursor()
        query = "insert into {table} (discordid, pm_channel, on_off, address, coordinates, distance) values ".format(table=self.table_name)
        values = "('{u.discordid}', '{u.pm_channel}', '{u.on_off}', '{u.address}', '{u.coordinates.latitude},{u.coordinates.longitude}', {u.distance})".format(u=user)
        update = " on duplicate key update on_off='{u.on_off}', address='{u.address}', coordinates='{u.coordinates.latitude},{u.coordinates.longitude}', distance='{u.distance}'".format(u=user)
        sql = query + values + update
        dbh.execute(sql)

        sql2 = "select settingid from {table} where discordid = '{u.discordid}'".format(u=user, table=self.table_name)
        dbh.execute(sql2)
        row = dbh.fetchone()
        if row != None:
            user.surrogateid = row[0]
            pass
        self.db.commit()
        dbh.close()
        pass


    def set_enable(self, discordid, on_off):
        dbh = self.db.cursor()
        sql = "update {table} set on_off = '{on_off}' where discordid = '{discordid}'".format(table=self.table_name,
                                                                                            on_off=on_off,
                                                                                            discordid=discordid)
        dbh.execute(sql)
        self.db.commit()
        dbh.close()
        pass


    def purge(self, discordid):
        dbh = self.db.cursor()
        sql = "delete from {table} where discordid = '{discordid}'".format(table=self.table_name, discordid=discordid)
        dbh.execute(sql)
        self.db.commit()
        dbh.close()
        pass


    pass


def test():
    from subscriber import Subscriber

    account = json.load(open("/var/lib/doublefault/account.json"))
    db = SettingDB(account["db-username"], account["db-password"], table_name="test")
    db.drop_table()
    db.create_table()

    db.put_user_data(Subscriber("user1", address="10.0001,10.0001"))
    db.put_user_data(Subscriber("user2", address="10.0002,10.0002"))
    db.put_user_data(Subscriber("user3", address="10.0003,10.0003"))
    db.put_user_data(Subscriber("user4", address="10.0004,10.0004"))
    db.put_user_data(Subscriber("user5", address="37 Wellington St., Arlington MA"))


    subsc = db.find_user("user1")
    print ("ID: {u.surrogateid}  address: {u.address}, coord: {u.coordinates.latitude},{u.coordinates.longitude}".format(u=subsc))

    db.put_user_data(Subscriber("user1", address="20.0001,20.0001"))

    for user in ["user1", "user2", "user3", "user4", "user5", "user6"]:
        subsc = db.find_user(user)
        if subsc:
            print ("ID: {u.surrogateid}  address: {u.address}, coord: {u.coordinates.latitude},{u.coordinates.longitude}".format(u=subsc))
            pass
        else:
            print ("no %s" % user)
            pass
        pass

    pass


if __name__ == "__main__":
    test()
    pass
