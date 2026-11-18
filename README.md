# Metro Transit Rider Alert Bot
This project is a discord bot that pulls from the Metro Transit API and post updates to a given channel. There is also the ability to distinguish between all routes and local routes if desired.

## How To Run:

If you have the appropriate libraries installed you can just run `python3 metro-transit-rider-alerts.py`

Otherwise you can create a virtual environment using `python3 -m venv .venv` to create a virtual environment where you can install the libraries specified in requirements.txt

After setting up the virtual environment run `source .venv/bin/activate` to use it.

Run `pip install -r requirements.txt` to install the required libraries, then `python metro-transit-rider-alerts.py` to actually run the script.

From there the script will pull from the Rider Alerts API every 60 seconds to check for updates.

## How It's Made:

**Tech used:** Python, discord.py, requests

This project was created for a neighborhood discord server in the Twin Cities. It uses the [discord.py library](https://discordpy.readthedocs.io) to integrate with the Discord API. The requests library is used to fetch updates from the [Metro Transit - Rider Alerts API](https://svc.metrotransit.org/swagger/index.html?urls.primaryName=Alerts+API+-+v1). 

## Optimizations

On our discord server this project is just one cog using the [Cogs class](https://discordpy.readthedocs.io/en/stable/ext/commands/cogs.html?highlight=cogs). Since that project is hosted on a private forgejo instance I pulled this out to run as a standalone instance, but there are features that it could probably both rely on and contribute to as part of the library, such as use of the database.

A specific optimization that could be made is to use aiohttp instead of requests. Running as a standalone bot for just one API it probably doesn't make a huge difference in practice, but if there were other cogs to consider or multiple APIs to use then it would make sense to move to an async approach, which I may yet do if I have time someday.

## Lessons Learned:

This project was a great opportunity to learn more about a locally relevant API and how to use the discord.py library. I also learned how to use Python async/await syntax at the same time I've been studying Javascript's version of it. This project was a great opportunity to learn more about python asyncio and coroutines.

During testing I also realized that the bot would have issues staying online after a day or so. I learned that I needed to be more efficient with any rate limit sensitive operations. For example, it didn't make sense to check previous messages on a channel again if the route alerts hadn't actually been updated since the last timestamp of the most recent post (which only changes with new alerts). Plus it was more efficient to just grab the message right after posting.
