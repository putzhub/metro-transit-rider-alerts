import os
import aiohttp
import discord
from discord.ext import tasks
from dotenv import load_dotenv

if not hasattr(os.environ, "DISCORD_TOKEN"):
    #Load .env if needed in development, unsure how this is handled on production.
    load_dotenv()

CHANNEL_ID_ALL_ROUTES = int(os.environ["CHANNEL_ID_ALL_ROUTES"])
CHANNEL_ID_LOCAL_ROUTES = int(os.environ["CHANNEL_ID_LOCAL_ROUTES"])
MESSAGE_HISTORY_SIZE=70

# See doc: https://svc.metrotransit.org/swagger/index.html
TRANSIT_API_ENDPOINT = "https://svc.metrotransit.org/alerts/all"
#List of routes in the neighborhood
NEIGHBORHOOD_ROUTES = [
    #Route IDs go here
    ""
]

class TripAdvisor(discord.Client):
    def __init__(self, *args, **kwargs):
        '''TripAdvisor pulls in MetroTransit and Minneapolis Snow Emergencies to post.'''
        super().__init__(*args, **kwargs)
        self.message_history = [] 

    # --- MetroTransit check ---
    def create_message(self, response_json, highlight_local=False):
        '''Helper to pluck most recent update from the API response and keep code cleaner'''
        RIDER_ALERTS_URL = "https://www.metrotransit.org/rider-alerts"
        
        #Pick out desired API data
        header_text = response_json["header_text"]["translation"][0]["text"]
        routes = set([r["route_id"] for r in response_json["informed_entity"]])
        #Default to the main rider alerts page if there isn't a URL provided
        url = response_json.get("url", RIDER_ALERTS_URL)
        url = url.get("translation")[0].get("text") if url != RIDER_ALERTS_URL else url
        #Put the message together
        title = f"Routes: {', '.join(routes)}"
        if highlight_local:
            #Point out if it's a route with at least one stop in Uptown or Whittier
            title = f"{title} - [NEIGHBORHOOD ROUTE]"
        #Check if there's an image
        img = response_json.get("image")
        thumbnail = img["localized_image"][0]["url"] if img else None

        #Prep the embed
        embed = discord.Embed(title=title, description=header_text, url=url, color=discord.Color.red())
        embed.set_footer(text=f"Alert ID:{response_json["id"]}")
        if thumbnail is not None:
            embed.set_thumbnail(url=thumbnail)
        return embed

    async def get_message_history(self, channel_id, l=MESSAGE_HISTORY_SIZE):
        channel = self.get_channel(channel_id)
        # Tell the type checker that this is a messageable channel
        assert isinstance(channel, discord.abc.Messageable)
        return [message async for message in channel.history(limit=l)]

    def verify_unique_message(self, msg):
        if len(self.message_history) == 0:
            return True
        for message in self.message_history:
            #Compare embed content to message history of plain text (backwards compatiblity)
            if msg.description in message.content:
                return False
            #Compare embed content to messages using embeds
            for embed in message.embeds:
                if msg.description in embed.description:
                    return False
        return True

    @property
    def last_message(self):
        return self.message_history[0]
    
    @last_message.setter
    def last_message(self, value):
        #Discord returns messages with most recent first
        self.message_history.insert(0, value)
        if len(self.message_history) > MESSAGE_HISTORY_SIZE:
            self.message_history.pop()

    async def check_rider_alerts(self):
        '''Call MetroTransit API and post if there's a new advisory.'''

        last_timestamp = 0
        #TODO: Replace using timestamp with the ID eventually once I figure out a safe way
        #Prefer timestamp over ID if there's no ID
        #last_id = 1000000
        if len(self.message_history) > 0:
            #Avoid access error if this is being used on a new channel
            last_timestamp = int(self.last_message.created_at.timestamp())
            #last_id = int(self.last_message.embeds[0].footer.text.split(":")[1])

        # Call API and pick out the alerts that are new since last post
        async with self.metro_transit_session.get(TRANSIT_API_ENDPOINT) as response:
            response = await response.json()
        response_filter = lambda res: res["last_modified_timestamp"] > last_timestamp 
                            #or int(res["id"]) > last_id
        alerts = [a for a in filter(response_filter, response)]

        for alert in alerts:
            # 🚨 TRANSIT ALERT: IT'S GOING DOWN 🚨
            route_filter = lambda r: r["route_id"] in NEIGHBORHOOD_ROUTES
            local_routes = [r for r in filter(route_filter, alert["informed_entity"])]
            is_local = len(local_routes) > 0 
            msg_all_routes = self.create_message(alert, is_local)

            # Use all routes channel since local posts are derived from it
            if self.verify_unique_message(msg_all_routes):
                self.last_message = await self.post_update(CHANNEL_ID_ALL_ROUTES, msg_all_routes)
                if is_local:
                    msg_local_routes = self.create_message(alert)
                    await self.post_update(CHANNEL_ID_LOCAL_ROUTES, msg_local_routes)

    async def __init_async__(self):
        '''Initialize some instance variables that require async'''
        self.metro_transit_session = aiohttp.ClientSession()
        self.message_history = await self.get_message_history(CHANNEL_ID_ALL_ROUTES)

    # Discord bot code setup
    async def setup_hook(self) -> None:
        # start the task to run in the background
        self.check_transit_updates.start()

    async def on_ready(self):
        print(f'Logged in as {self.user}')
        print('------')

    async def close(self):
        await self.metro_transit_session.close()
        await super().close()

    # Main loop
    @tasks.loop(seconds=60)
    async def check_transit_updates(self):
        await self.check_rider_alerts()
        #TODO: await self.check_snow_emergencies()

    @check_transit_updates.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()  # wait until the bot logs in
        # Wait until we can actually call self.get_latest_message()
        await self.__init_async__()

    async def post_update(self, channel, msg):
        '''Send a message to the channel'''
        
        channel = self.get_channel(channel)
        # Tell the type checker that this is a messageable channel
        assert isinstance(channel, discord.abc.Messageable)
        return await channel.send(embed=msg)

if __name__ == "__main__":
    client = TripAdvisor(intents=discord.Intents.default())
    client.run(os.environ["DISCORD_TOKEN"])