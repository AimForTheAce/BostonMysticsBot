#/usr/bin/python3

import discord, json, sys, time, re, mysql.connector, geopy, datetime
import discord.user

from subscriber import Subscriber
from settingdb import SettingDB
from selectiondb import SelectionDB
from geopy.point import Point


VERSION = "0.1"

#

google_map_re = re.compile(r"https://maps.google.com/maps\?q=([+-]{0,1}\d+\.\d+),([+-]{0,1}\d+\.\d+)")

def parse_spawn_message(spawn):
    coords = google_map_re.search(spawn, re.MULTILINE)
    if coords is not None:
        return Point(float(coords.group(1)), float(coords.group(2)))
    return None


# Count members on the server which has any role
def count_members(server):
    role_counts = {  }

    for member in server.members:
        the_role = None
        if (len(member.roles) > 1):
            for role in member.roles:
                if role.name in [ "valor", "instinct", "CallAbuser", "Carbon" ]:
                    the_role = role.name
                    break
                pass
            if the_role == None:
                the_role = "Mystic"
                pass
            pass
        else:
            the_role = "none"
            pass

        if role_counts.get(the_role) is not None:
            role_counts[the_role] = role_counts[the_role] + 1
            pass
        else:
            role_counts[the_role] = 1
            pass
        pass
    return role_counts


async def assign_member_role(connection, server, members, role_name):
    role = discord.utils.find(lambda role: role.name == role_name, server.roles)
    if role is not None:
        for member in members:
            await connection.add_roles(member, role)
            pass
        pass
    pass


class DoubleFault(discord.Client):
    
    set_raid_channels_re = re.compile("^set raid channels (.+)$")
    gymhuntr_raid_clock_re = re.compile('Raid Ending: (\d+) hours (\d+) min (\d+) sec')
    raid_level_re = re.compile('Level (\d+) Raid')
    gymhuntr_raid_coord_re = re.compile('https://GymHuntr\.com/#([+-]{0,1}\d+\.\d+),([+-]{0,1}\d+\.\d+)')


    def __init__(self):
        super().__init__()

        self.config = json.load(open( "/var/lib/doublefault/config.json"))
        self.account = json.load(open("/var/lib/doublefault/account.json"))
        self.new_members = []
        self.greeting_servers = {}
        for server_desc in self.config["greeting-servers"]:
            self.greeting_servers[server_desc[0]] = server_desc[1]
            pass
        self.my_servers = {} # The severs that the bot belongs
        self.xfer_map = {}
        self.current_log = None
        self.raid_data_file = None
        self.raid_channels = self.config["raid-channels"]

        self.settingdb = SettingDB(self.account["db-username"], self.account["db-password"])
        self.settingdb.create_table()
        self.selectiondb = SelectionDB(self.account["db-username"], self.account["db-password"])
        self.selectiondb.create_table()
        pass


    async def on_member_join(self, member):
        server = member.server

        if not member.server.name in self.greeting_servers.keys():
            return

        self.new_members.append(member)

        # if this is a 
        greeting_spec = self.greeting_servers[member.server.name]
        
        info_channel_name = greeting_spec.get("info-channel")
        if info_channel_name is None: info_channel_name = "info"

        info_channel = discord.utils.find(lambda channel: channel.name == info_channel_name, server.channels)

        greetings_main = greeting_spec.get("greetings-main")
        if greetings_main is not None:
            message = greetings_main.format(member, server)
        else:
            # Reasonable default message.
            message = "Welcome!"
            pass

        greetings_info = greeting_spec.get("greetings-info")
        if info_channel is not None and greetings_info is not None:
            message = message + "\n" + greetings_info.format(info_channel)
            pass

        await self.send_message(server, message)
        pass

        if len(self.greeters) > 0:
            line_to_drop = '{0.mention} is here'.format(member)
            for greeter in self.greeters:
                await self.send_message(greeter, line_to_drop)
                pass
            pass
        pass


    async def on_message(self, message):
        # If I'm dispatching the message that I sent, ignore
        if message.author == self.user:
            return

        # PM
        if message.server is None:
            if message.author.bot:
                await self.handle_bot_pm(message)
            else:
                await self.handle_pm(message)
                pass
            return
        await self.handle_server_message(message)
        return
            
    async def handle_server_message(self, message):
        # Handing the message

        if self.xfer_map is not None:
            from_server = self.xfer_map.get(message.server.name)
            if from_server is not None:
                destination_spec = from_server.get(message.channel.name)
                if destination_spec is not None:
                    dst_server, dst_channel, format_spec, everyone = destination_spec
                    lines = message.content.split("\n")
                    if format_spec == "raid":
                        output = " ".join( [lines[0], lines[2], lines[4], lines[5], lines[8], lines[10]])
                    else:
                        output = " ".join( [lines[0], lines[2], lines[7], lines[9]])
                        pass
                    if everyone:
                        output = "@everyone " + output
                        pass
                    await self.send_message(dst_channel, output)
                    pass
                pass
            pass
    
        if message.server.name == self.config["scanner"]  and message.channel.name in self.raid_channels:
            await self.save_raid_data(message.content)
            return

        if message.server.name == self.config["scanner"]:
            pokemon = message.channel.name.lower()
            await self.relay_spawn(pokemon, message.content)
            pass


        i_am = self.user
        if i_am in message.mentions:
            if "thank" in message.content.lower():
                await self.send_message(message.channel, str(self.config.get("ur-welcome")))
                pass
            pass
        return
 

    async def relay_spawn(self, pokemon, spawn_data):
        dexno = self.selectiondb.pokemons.get(pokemon)
        if dexno is not None:
            coord = parse_spawn_message(spawn_data)
            if coord is not None:
                listeners = self.selectiondb.choose_listeners(pokemon, coord)
                for listener in listeners:
                    discord_id, pm_channel, center, meter = listener
                    discriminator = None
                    name_n_disc = discord_id.split('#')
                    if len(name_n_disc) == 2:
                        where = discord.user.User(username=name_n_disc[0],
                                                  discriminator=name_n_disc[1],
                                                  id=pm_channel)
                    else:
                        where = discord.user.User(username=discord_id,
                                                  id=pm_channel)
                        pass
                    lines = spawn_data.split("\n")
                    try:
                        reply = lines[0] + " " + lines[2] + " " + lines[3] + " " + lines[5] + "\n" + lines[9] + " **Distance**: %d meters" % meter
                    except:
                        reply = spawn_data
                        pass
                    await self.send_message(where, reply)
                    pass
                pass
            else:
                print( "Something fishy.\n" + spwan_data)
                pass
            pass
        pass


    async def save_raid_data(self, content):
        current = "raid." + time.strftime("%Y-%m-%d", time.localtime()) + ".txt"

        if current != self.current_log:
            if self.raid_data_file is not None:
                self.raid_data_file.close()
                self.raid_data_file = None
                pass
            pass
        
        if self.raid_data_file is None:
            self.current_log = current
            try:
                self.raid_data_file = open("/var/spool/doublefault/" + current, "a+")
            except:
                pass
            pass

        if self.raid_data_file is not None:
            self.raid_data_file.write(content)
            self.raid_data_file.write("\n\n")
            self.raid_data_file.flush()
            pass

        pass


    # Handling PM from person
    async def handle_pm(self, message):
        reply = None

        # From down, low-tech!
        content = message.content.lower()
        words = content.split(' ')
        if len(words) == 0:
            return

        if len(words) > 1 and words[0] == self.account["handshake"]:
            if words[1] == "count":
                counted_server_spec = self.my_servers.get(self.config.get("count"))
                counted_server = counted_server_spec[None] if counted_server_spec is not None else None
                if counted_server:
                    reply = " ".join( [ "%s: %d" % item for item in sorted( count_members(counted_server).items(), key=lambda item: item[1] ) ] )
                    pass
                else:
                    reply = "no counting server? %s" % "\n".join(servers.keys())
                    pass
                pass
            elif words[1] == "iamgreeter":
                self.greeters.append(message.author)
                reply = "Greetings!\n"
                pass

            elif words[1] == "tellmegreeters":
                if len(self.greeters) == 0:
                    reply = "<cricket> <cricket> <cricket>"
                else:
                    reply = " ".join( [ greeter.mention for greeter in self.greeters ] )
                    pass
                pass

            elif words[1] == "nogreeter":
                self.greeters = [ greeter for greeter in self.greeters if greeter != message.author ]
                reply = "No greetings\n"
                pass

            elif words[1] == "version":
                reply = VERSION
                pass

            elif words[1] == "raid":
                reply = "Raid channels: %s" % ",".join(self.raid_channels)
                pass
            else:
                matched = self.set_raid_channels_re.match(" ".join(words[1:]))
                if matched:
                    self.raid_channels = [ ch.strip() for ch in matched.group(1).split(",") ]
                    reply = "New raid channels: %s" % ",".join(self.raid_channels)
                    pass
                pass
            pass
        elif len(words) > 1 and words[0] == self.account["bot-prefix"]:
            try:
                await self.handle_user_command(message)
            except Exception as exc:
                await self.send_message(message.channel, "The command failed. AimForTheAce needs to fix the bug.")
                raise exc
                pass
            pass


        if reply is not None:
            await self.send_message(message.channel, reply)
            pass
        
        return
    
    # handle user command
    async def handle_user_command(self, message):
        content = message.content.lower()
        words = content.split(' ')
        if len(words) == 0:
            return

        discordid = str(message.author)
        pm_channel = message.author.id
        words = words[1:]

        if words[0] == "pin":
            user = Subscriber(discordid, pm_channel, self.settingdb, self.selectiondb)
            address = " ".join(words[1:])
            await user.set_address(address)

            if user.surrogateid is None:
                self.settingdb.put_user_data(user)
                self.selectiondb.update_range(user.surrogateid, user.pokemons, user.coordinates, user.distance)
                pass
            else:
                self.selectiondb.update_coord(user.surrogateid, user.coordinates)
                pass

            reply = "https://maps.google.com/maps?q={lat},{lon}".format(lat=user.coordinates.latitude,
                                                                        lon=user.coordinates.longitude)
            await self.send_message(message.channel, reply)
            pass
        
        elif words[0] == "info":
            user = Subscriber(discordid, pm_channel, self.settingdb, self.selectiondb)
            if user.surrogateid == None:
                reply = "%s has nothing here." % discordid
            else:
                reply = user.report_for_user()
                pass
            await self.send_message(message.channel, reply)
            pass
        
        elif words[0] == "range":
            user = Subscriber(discordid, pm_channel, self.settingdb, self.selectiondb)

            if len(words) == 3:
                pokemons = words[1]
                distance = words[2]

                reply = user.set_range(pokemons, distance)
                if len(reply) > 0:
                    await self.send_message(message.channel, "bad pokemon names\n" + reply)
                    pass
                pass
            else:
                await self.send_message(message.channel, user.report_for_user())
                pass
            pass

        elif words[0] == "all-range":
            user = Subscriber(discordid, pm_channel, self.settingdb, self.selectiondb)

            if len(words) == 2:
                distance = words[1]
                self.selectiondb.update_distance(user.surrogateid, distance)
                pass
            else:
                await self.send_message(message.channel, "no sir.")
                pass
            pass

        elif words[0] == "start":
            self.settingdb.set_enable(discordid, 'y')
            pass

        elif words[0] == "stop":
            self.settingdb.set_enable(discordid, 'n')
            pass

        elif words[0] == "bye":
            user = Subscriber(discordid, pm_channel, self.settingdb, self.selectiondb)
            if user.surrogateid:
                self.selectiondb.purge(user.surrogateid)
                self.settingdb.purge(discordid)
                pass
            else:
                await self.send_message(message.channel, "There is abyss already.")
                pass
            pass

        elif words[0] == "delete":
            user = Subscriber(discordid, pm_channel, self.settingdb, self.selectiondb)
            if user.surrogateid:
                if len(words) > 1:
                    pokemons = words[1]
                    self.selectiondb.delete_pokemons(user.surrogateid, pokemons)
                    pass
                pass
            else:
                await self.send_message(message.channel, "There is abyss already.")
                pass
            pass


        elif words[0] == "help":
            usage = '''pin <address>
  sets up the location you are interested in.

info
  prints out what DoubleFault knows

start/stop
  starts/stops the spwan relay.

range [pokemons,...] distance
  The spawn of pokemons within the distance is relayed to you.

all-range distance
  All of spawn max distance is set to it.

delete [pokemons,]
  delete the spawn setting of pokemons

bye
  forget all about you.'''

            await self.send_message(message.channel, usage)
            pass


        elif words[0] == "test":
            data = '''[Cambridgeport] **Rhydon** (22%)

**Until**: 01:53:41AM (29:39 left) 
**L30+ IV**: 2 - 3 - 5  (22%) 
**L30+ Moveset**: Mud Slap - Megahorn 
**L30+ CP**: 1101
**Gender**: Female
**Address**: 84 Auburn St
**Map**: <https://bostonpogomap.com#42.36215027,-71.10256278>
**Google Map**: <https://maps.google.com/maps?q=42.36215027,-71.10256278>
-----------------------------------'''

            await self.relay_spawn("rhydon", data)

            data = '''[Cambridge Highlands] **Larvitar** (44%)

**Until**: 01:54:46AM (29:44 left) 
**L30+ IV**: 2 - 9 - 9  (44%) 
**L30+ Moveset**: Bite - Ancient Power 
**L30+ CP**: 374
**Gender**: Female
**Address**: 679-681 Concord Ave
**Map**: <https://bostonpogomap.com#42.38984181,-71.15056095>
**Google Map**: <https://maps.google.com/maps?q=42.38984181,-71.15056095>
-----------------------------------'''

            await self.relay_spawn("larvitar", data)

        else:
            await self.send_message(message.channel, "I don't know what you meant.")
            pass
        pass


    # Handling PM from bot
    async def handle_bot_pm(self, message):
        if message.author.name.lower().startswith("gymhuntrbot"):
            if message.embeds:
                for embed in message.embeds:
                    # https://GymHuntr.com/#42.305976,-71.222634
                    gymhuntr_url = embed['url']
                    latitude = "0.0000"
                    longitude = "0.0000"
                    m = self.gymhuntr_raid_coord_re.search(gymhuntr_url)
                    if m:
                        latitude = m.group(1)
                        longitude = m.group(2)
                        pass

                    # 'Level 3 Raid has started!'
                    title = embed['title']
                    m = self.raid_level_re.search(title)
                    level = "0"
                    if m:
                        level = m.group(1)
                        pass
                    description = embed['description']
                    thumbnail = embed['thumbnail']
                    # thumbnail url can be used to identify the pokedex number
                    # eg - 'https://raw.githubusercontent.com/kvangent/PokeAlarm/master/icons/135.png'
                    thumbnail_url = thumbnail['url']

                    # desc
                    # '**Gym name here**\nJolteon\nCP: 19883.\n*Raid Ending: 0 hours 35 min 29 sec*'
                    lines = description.split('\n')
                    gym = lines[0]
                    pokemon_kind = lines[1]
                    cp = lines[2]
                    time_info = lines[3]
                    m = self.gymhuntr_raid_clock_re.search(description, re.MULTILINE)
                    hr = 0
                    min = 0
                    sec = 0
                    if m:
                        hr = m.group(1)
                        min = m.group(2)
                        sec = m.group(3)
                        pass

                    start_time = datetime.datetime.now()
                    dt = datetime.timedelta(hours=int(hr), minutes=int(min), seconds=int(sec))
                    end_time = start_time + dt
                    start_time_str = start_time.strftime("%H:%M:%S")
                    end_time_str = end_time.strftime("%H:%M:%S")

                    raid_data = '''**{pokemon}** - Level: {raidlevel} - {cp}
    
**Moveset**: 

**Start**: {startime}
**End**: {endtime}

**Current Team**: 

**Gym**: {gym}
**Address**: 
**Map**: 
**Google Map**: <https://maps.google.com/maps?q={lat},{lon}>
-----------------------------------'''.format(pokemon=pokemon_kind,
                                              raidlevel = level,
                                              startime=start_time_str,
                                              endtime=end_time_str,
                                              lat=latitude,
                                              lon=longitude,
                                              gym=gym,
                                              cp=cp)
                    await self.save_raid_data(raid_data)
                    pass
                pass
            pass
        pass


    async def on_ready(self):
        self.greeters = []

        # self.servers - all of servers that the bot is in.
        # Convenient cache for my servers
        for server in self.servers:
            # Using None for server - a bit of hack
            submap = {None: server}
            for channel in server.channels:
                submap[channel.name] = channel
                pass
            self.my_servers[server.name] = submap
            pass

        # setting up the source / destination pairs
        channel_map = self.config.get("channel-map")

        for map_spec in channel_map:
            source = map_spec.get("source")

            src_server_name = source.get("server")
            src_server = self.my_servers.get(src_server_name)
            if src_server is None:
                print(" Source server %s is not found\n" % src_server_name)
                continue
            src_channel_name = source.get("channel")
            src_channel = src_server.get(src_channel_name)

            if src_channel is None:
                print(" Source server %s / %s is not found\n" % (src_server_name, src_channel_name))
                continue
    
            dest = map_spec.get("destination")

            dst_server_name = dest.get("server")
            dst_server = self.my_servers.get(dst_server_name)
            if dst_server is None:
                print("%s is not specified\n" % dst_server_name)
                continue

            dst_channel_name = dest.get("channel")
            if dst_channel_name is None:
                print("A channel of %s is not specified\n" % dst_server_name)
                continue
            
            dst_channel = dst_server.get(dst_channel_name)
            if dst_channel is None:
                print(" %s / %s is not found\n" % dst_server_name, dst_channel_name)
                continue

            format_spec = map_spec.get("format")
            if self.xfer_map.get(src_server_name) is None:
                self.xfer_map[src_server_name] = {}
                pass

            everyone = map_spec.get("everyone")

            self.xfer_map[src_server_name][src_channel_name] = (dst_server, dst_channel, format_spec, everyone)
            pass
        return
    pass


bot = DoubleFault()
bot.run(bot.account["username"], bot.account["password"])
