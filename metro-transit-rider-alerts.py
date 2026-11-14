import os
import json
import requests
import discord
from discord.ext import tasks
from dotenv import load_dotenv

if not hasattr(os.environ, "DISCORD_TOKEN"):
    #Load .env if needed in development, unsure how this is handled on production.
    load_dotenv()

class TripAdvisor(discord.Client):
    # Response lives in memory, but caches to avoid spam if restarted
    _json_response = {}
    _cache_path = ""
    NEIGHBORHOOD_ROUTES = [
        "2",
        "4",
        "11",
        "17",
        "18",
        "27",
        "36",
        "38",
        "113",
        "114",
        "156",
        "460",
        "465",
        "467",
        "470",
        "475",
        "477",
        "578",
        "600",
        "695",
        "904",
        "922",
        "925",
    ]

    def __init__(self, *args, **kwargs):
        '''TripAdvisor pulls in MetroTransit and Minneapolis Snow Emergencies to post.'''
        super().__init__(*args, **kwargs)       
        
        # data path: /app/data/metro_transit.json
        data_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(data_dir, exist_ok=True)
        self._cache_path = os.path.join(data_dir, "metro_transit.json")

        # Read from file if it exists, only ever relevant on restart
        if os.path.exists(self._cache_path):
            self._read_cache()

    def _save_cache(self):
        with open(self._cache_path, "w") as json_file:
            json.dump(self._json_response, json_file, indent=2)

    def _read_cache(self):
        with open(self._cache_path, "r") as json_file:
            self._json_response = json.load(json_file)

    # --- MetroTransit check ---
    def _create_message(self, response_json):
        '''Helper to pluck most recent update from the API response and keep code cleaner'''
        
        #Avoid throwing an error if response_json is empty
        if response_json != {}:
            #Response is sorted by date last modified.
            most_recent = len(response_json)-1
            #Pick out desired API data
            route_id = response_json[most_recent]["informed_entity"][0]["route_id"]
            header_text = response_json[most_recent]["header_text"]["translation"][0]["text"]
            url = response_json[most_recent]["url"]["translation"][0]["text"]
            #Put the message together
            msg = f"{header_text} - [More details on MetroTransit - see Alerts tab here.]({url})"
            #Point out if it's a route with at least one stop in Uptown or Whittier
            if route_id in self.NEIGHBORHOOD_ROUTES:
                msg = f"*[NEIGHBORHOOD ROUTE]*\n**{msg}**"

            return msg

    async def check_transit_advisories(self):
        '''Call MetroTransit API and post if there's a new advisory.'''

        # See doc: https://svc.metrotransit.org/swagger/index.html
        r = requests.get("https://svc.metrotransit.org/alerts/all")
        new_reponse = json.loads(r.text)

        #TODO: Come up with a better check, works for now
        if self._create_message(new_reponse) != self._create_message(self._json_response):
            # 🚨️ TRANSIT ALERT: IT'S GOING DOWN 🚨️
            self._json_response = new_reponse

            #Post the news - TODO: Make a better formatted message
            msg = self._create_message(self._json_response)
            await self.post_update(msg)

            #Once we're sure it got posted, cache it
            self._save_cache()

    # Discord bot code setup
    async def setup_hook(self) -> None:
        # start the task to run in the background
        self.check_transit_updates.start()

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    # Main loop
    @tasks.loop(seconds=60)
    async def check_transit_updates(self):
        await self.check_transit_advisories()
        #TODO: await self.check_snow_emergencies()

    @check_transit_updates.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()  # wait until the bot logs in

    async def post_update(self, msg):
        '''Send a message to the #trip-advisory channel'''
        
        channel = self.get_channel(int(os.environ["TRANSIT_CHANNEL_ID"]))
        # Tell the type checker that this is a messageable channel
        assert isinstance(channel, discord.abc.Messageable)
        await channel.send(msg)

if __name__ == "__main__":
    # For testing purposes
    client = TripAdvisor(intents=discord.Intents.default())
    client.run(os.environ["DISCORD_TOKEN"])