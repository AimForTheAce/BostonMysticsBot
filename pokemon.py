
import sys, time, mysql.connector, geopy.point, geopy.distance, json, re

from geopy.point import Point

class Pokemon:
    def __init__(self, dexno, name):
        self.dexno = dexno
        self.name = name
        pass

    pass



class PokemonDB:

    def __init__(self, uname, pw, db_name="doublefault"):
        self.table_name = "pokemon"
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
        sql = "create table if not exists %s (dexno int not null primary key, name char(32) not null, index(name)) engine=myisam" % self.table_name
        dbh.execute(sql)
        dbh.close()
        self.db.commit()
        pass

    def put_pokemon(self, dexno, name):
        dbh = self.db.cursor()
        query = "insert into %s (dexno, name) " % self.table_name
        values = "values({dexno}, '{name}') on duplicate key update dexno={dexno}, name='{name}'".format(dexno=dexno, name=name.lower())
        sql = query + values
        dbh.execute(sql)
        self.db.commit()
        dbh.close()
        pass


    def find_pokemon_by_name(self, name):
        user = pokemon
        dbh = self.db.cursor()
        sql = "select  (dexno) from %s where name = '%s'" % (self.table_name, name.lower)
        dbh.execute(sql)
        while True:
            row = dbh.fetchone()
            if row == None:
                break
            dexno = row
            pokemon = Pokemon(name=name, dexno=dexno)
            pass
        self.db.commit()
        dbh.close()
        return pokemon

    pass


def main():
    account = json.load(open("/var/lib/doublefault/account.json"))
    db = PokemonDB(account["db-username"], account["db-password"])
    # db.drop_table()
    # db.create_table()

    filename = "pokemon.txt"
    dexno = 0
    src = open(filename)
    name = None

    type_re = re.compile(r'^Type: (.+)$')
    fast_re = re.compile(r'^Fast Attacks: (.+)$')
    charge_re = re.compile(r'^Special Attacks: (.+)$')
    evo_to_re = re.compile(r'^Evolves Into: (.+)$')
    
    for line in src.readlines():
        if line[0] != ' ':
            dexno = dexno + 1
            name = line.strip().lower()
            db.put_pokemon(dexno, name)
            pass
        pass

    db.put_pokemon(-1, "iv100")
    db.put_pokemon(-2, "iv90")

    pass


if __name__ == "__main__":
    main()
    pass
