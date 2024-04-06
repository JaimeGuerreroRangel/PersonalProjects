# Discord bot
# By: Jaime Guerrero

# Import libraries
import discord
import requests
import json
from googleapiclient.discovery import build # Google API

# Initialize YouTube API
youtube_api_key = 'YOUR_YOUTUBE_API_KEY'
youtube = build('youtube', 'v3', developerKey=youtube_api_key)

# Function to tell a random joke
def get_joke():
    """Get a random joke from the official joke API.
       - API URL: https://official-joke-api.appspot.com/random_ten
       The first line of code gets a list of 10 random jokes.
       The second line selects the first joke from the list and returns it.
       Returns the joke in text format.
    """
    response = requests.get('https://official-joke-api.appspot.com/random_ten')
    json_data = json.loads(response.text)
    return json_data[0]['setup'] + '\n' + json_data[0]['punchline']

# Help function to know how to use the bot
def help_bot():
    """Show a help message with a list of commands the bot can handle."""
    help_message = "Hello! I'm a Discord bot. Here's a list of commands you can use:\n\n"
    commands = {
        "$help": "Show this help message.",
        "$joke": "Get a random joke.",
        "$meme": "Get a random meme.",
        "$music <song name or artist>": "Search for music on YouTube."
    }
    for command, description in commands.items():
        help_message += f"{command}: {description}\n"
    return help_message

# Function to get a random meme
def get_meme():
  response = requests.get('https://meme-api.com/gimme')
  json_data = json.loads(response.text)
  return json_data['url']

# Function to search for music on YouTube
async def fetch_music(channel, search_query: str):
    """Search for music on YouTube using the YouTube API.
       - Parameters:
           channel (discord.TextChannel): Discord channel where the response will be sent.
           search_query (str): Search query to look for music on YouTube.
       - Returns:
           None
       - Send a message to the Discord channel with a list of YouTube songs that match the search query.
    """
    request = youtube.search().list(
        part="snippet",
        maxResults=5,
        q=f"{search_query} music",
        type="video",
        videoCategoryId="10"  # Music Category
    )
    response = request.execute()

    if response['items']:
        reply = "**Here are some songs you might like:**\n"
        for item in response['items']:
            video_title = item['snippet']['title']
            video_url = f"https://www.youtube.com/watch?v={item['id']['videoId']}"
            reply += f"[{video_title}]({video_url})\n"
    else:
        reply = "Sorry, I couldn't find music that matches your search."

    await channel.send(reply)

# Class for the Discord client
class MyClient(discord.Client):
  async def on_ready(self):
    print('Logged on as {0}!'.format(self.user))

  async def on_message(self, message):
    if message.author == self.user:
      return
    if message.content.startswith('$help'):
      await message.channel.send(help_bot())
    if message.content.startswith('$joke'):
        await message.channel.send(get_joke())
    if message.content.startswith('$meme'):
      await message.channel.send(get_meme())
    if message.content.startswith('$music'):
            search_query = message.content.split(' ', 1)[1] if len(message.content.split(' ', 1)) > 1 else ''
            if search_query:  # Ensure there is a search query
                await fetch_music(message.channel, search_query=search_query)
            else:
                await message.channel.send("Please provide the name of the song or artist you want to search for.")

intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run('YOUR_BOT_TOKEN')
