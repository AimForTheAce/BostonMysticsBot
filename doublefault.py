#/usr/bin/python3

import discord
import json
import sys

VERSION = "0.1"

connection = discord.Client()

# Count members on the server which has any role
def count_members(server):
    n_members = 0
    n_whites = 0
    for member in server.members:
        if (len(member.roles) > 1):
            n_members = n_members + 1
            pass
        else:
            n_whites = n_whites + 1
            pass
        pass
    return (n_members, n_whites)


async def assign_member_role(connection, server, members, role_name):
    role = discord.utils.find(lambda role: role.name == role_name, server.roles)
    if role is not None:
        for member in members:
            await connection.add_roles(member, role)
            pass
        pass
    pass


class DoubleFault:
    
    def __init__(self):
        self.config = json.load(open( "/var/lib/doublefault/config.json"))
        self.account = json.load(open("/var/lib/doublefault/account.json"))
        self.new_members = []
        self.greeting_servers = {}
        for server_desc in self.config["greeting-servers"]:
            self.greeting_servers[server_desc[0]] = server_desc[1]
            pass
        self.my_servers = {} # The severs that the bot belongs
        self.xfer_map = {}
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

        await connection.send_message(server, message)
        pass

        if len(self.greeters) > 0:
            line_to_drop = '{0.mention} is here'.format(member)
            for greeter in self.greeters:
                await connection.send_message(greeter, line_to_drop)
                pass
            pass
        pass
    pass


    async def on_message(self, message):
        # PM
        if message.server is None:
            await self.handle_pm(message)
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
                    dst_server, dst_channel, format_spec = destination_spec
                    lines = message.content.split("\n")
                    if format_spec == "raid":
                        output = " ".join( [lines[0], lines[2], lines[4], lines[5], lines[8], lines[10]])
                    else:
                        output = " ".join( [lines[0], lines[2], lines[7], lines[9]])
                        pass
                    await connection.send_message(dst_channel, output)
                    pass
                pass
            pass
    
        i_am = connection.user
        if i_am in message.mentions:
            if "thank" in message.content.lower():
                await connection.send_message(message.channel, str(self.config.get("ur-welcome")))
                pass
            return
        return
        

    # Handling PM
    async def handle_pm(self, message):
        reply = None

        # From down, low-tech!

        if message.content.lower() == "count":
            counted_server_spec = self.my_servers.get(self.config.get("count"))
            counted_server = counted_server_spec[None] if counted_server_spec is not None else None
            if counted_server:
                reply = "members %d whites %d" % count_members(counted_server)
                pass
            else:
                reply = "no counting server? %s" % "\n".join(servers.keys())
                pass
            pass
        elif message.content.lower() == "iamgreeter":
            self.greeters.append(message.author)
            reply = "Greetings!\n"
            pass

        elif message.content.lower() == "tellmegreeters":
            if len(self.greeters) == 0:
                reply = "<cricket> <cricket> <cricket>"
            else:
                reply = " ".join( [ greeter.mention for greeter in self.greeters ] )
                pass
            pass

        elif message.content.lower() == "nogreeter":
            self.greeters = [ greeter for greeter in self.greeters if greeter != message.author ]
            reply = "No greetings\n"
            pass
        elif message.content.lower() == "version":
            reply = VERSION
            pass

        if reply is None:
            reply = str(self.config.get("bot-reply"))
            pass
        
        await connection.send_message(message.channel, reply)
        return
    

    async def on_ready(self):
        self.greeters = []

        # self.servers - all of servers that the bot is in.
        # Convenient cache for my servers
        for server in connection.servers:
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

            self.xfer_map[src_server_name][src_channel_name] = (dst_server, dst_channel, format_spec)
            pass
        return
    pass

bot = DoubleFault()

@connection.event
async def on_ready():
    await bot.on_ready()
    pass

@connection.event
async def on_message(message):
    #
    if message.author == connection.user:
        return
    print("message %s" % message.content)
    await bot.on_message(message)
    pass

@connection.event
async def on_member_join(member):
    await bot.on_member_join(member)
    pass

connection.run(bot.account["username"], bot.account["password"])