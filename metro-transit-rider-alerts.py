import os
import json
import requests
import discord
from discord.ext import tasks
from dotenv import load_dotenv

if not hasattr(os.environ, "DISCORD_TOKEN"):
    #Load .env if needed in development, unsure how this is handled on production.
    load_dotenv()

CHANNEL_ID_ALL_ROUTES = int(os.environ["CHANNEL_ID_ALL_ROUTES"])
CHANNEL_ID_LOCAL_ROUTES = int(os.environ["CHANNEL_ID_LOCAL_ROUTES"])

#List of routes in the neighborhood
NEIGHBORHOOD_ROUTES = [
    #Route IDs go here
    ""
]

class TripAdvisor(discord.Client):
    def __init__(self, *args, **kwargs):
        '''TripAdvisor pulls in MetroTransit and Minneapolis Snow Emergencies to post.'''
        super().__init__(*args, **kwargs)       

    # --- MetroTransit check ---
    def create_message(self, response_json, highlight_local=False):
        '''Helper to pluck most recent update from the API response and keep code cleaner'''
        
        #Avoid throwing an error if response_json is empty
        if response_json != {}:
            #Pick out desired API data
            header_text = response_json["header_text"]["translation"][0]["text"]
            url = response_json["url"]["translation"][0]["text"]
            #Put the message together
            msg = f"{header_text} - [More details on MetroTransit - see Alerts tab here.]({url})"
            if highlight_local:
                #Point out if it's a route with at least one stop in Uptown or Whittier
                msg = f"*[NEIGHBORHOOD ROUTE]*\n**{msg}**"

            return msg

    async def get_latest_message_timestamp(self, channel):
        async for message in self.get_channel(channel).history(limit=1):
            return int(message.created_at.timestamp())
        return None

    async def check_transit_advisories(self):
        '''Call MetroTransit API and post if there's a new advisory.'''

        # See doc: https://svc.metrotransit.org/swagger/index.html
        r = requests.get("https://svc.metrotransit.org/alerts/all")
        # Responses are sorted with most recently updated last.
        response_json = json.loads(r.text).pop()
        # Use all routes channel since it'll have local too
        last_timestamp = await self.get_latest_message_timestamp(CHANNEL_ID_ALL_ROUTES)

        if response_json["last_modified_timestamp"] > last_timestamp:
            # 🚨️ TRANSIT ALERT: IT'S GOING DOWN 🚨️
            route_id = response_json["informed_entity"][0]["route_id"]
            local_route = route_id in NEIGHBORHOOD_ROUTES

            # Post the news
            msg_all_routes = self.create_message(response_json, local_route)
            await self.post_update(CHANNEL_ID_ALL_ROUTES, msg_all_routes)
            if local_route:
                msg_local_routes = self.create_message(response_json)
                await self.post_update(CHANNEL_ID_LOCAL_ROUTES, msg_local_routes)

    # Discord bot code setup
    async def setup_hook(self) -> None:
        # start the task to run in the background
        self.check_transit_updates.start()

    async def on_ready(self):
        print(f'Logged in as {self.user}')
        print('------')

    # Main loop
    @tasks.loop(seconds=60)
    async def check_transit_updates(self):
        await self.check_transit_advisories()
        #TODO: await self.check_snow_emergencies()

    @check_transit_updates.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()  # wait until the bot logs in

    async def post_update(self, channel, msg):
        '''Send a message to the #trip-advisory channel'''
        
        channel = self.get_channel(channel)
        # Tell the type checker that this is a messageable channel
        assert isinstance(channel, discord.abc.Messageable)
        await channel.send(msg)

if __name__ == "__main__":
    client = TripAdvisor(intents=discord.Intents.default())
    client.run(os.environ["DISCORD_TOKEN"])