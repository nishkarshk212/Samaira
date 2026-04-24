# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import aiohttp
import ssl
import certifi
from pyrogram import filters, types
from anony import app, config, lang

@app.on_message(filters.command(["lyrics", "lyric"], config.PREFIX) & ~app.bl_users)
@lang.language()
async def lyrics_hndlr(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text(m.lang["lyrics_usage"] if "lyrics_usage" in m.lang else "<b>Usage:</b> /lyrics [song name]")
    
    query = m.text.split(None, 1)[1]
    sent = await m.reply_text(m.lang["lyrics_searching"] if "lyrics_searching" in m.lang else "🔎 Searching for lyrics...")
    
    api_url = f"{config.API_BASE_URL}/lyrics"
    params = {
        "song": query,
        "token": config.API_TOKEN
    }
    
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params, ssl=ssl_context) as resp:
                if resp.status != 200:
                    return await sent.edit_text(m.lang["lyrics_not_found"] if "lyrics_not_found" in m.lang else "❌ Lyrics not found.")
                
                data = await resp.json()
                lyrics = data.get("lyrics")
                artist = data.get("artist", "Unknown Artist")
                title = data.get("title", query)
                
                if not lyrics:
                    return await sent.edit_text(m.lang["lyrics_not_found"] if "lyrics_not_found" in m.lang else "❌ Lyrics not found.")
                
                output = f"<b><u>Lyrics for {title}</u></b>\n\n<b>Artist:</b> {artist}\n\n{lyrics}"
                if len(output) > 4096:
                    output = output[:4090] + "..."
                
                await sent.edit_text(output)
                
    except Exception as e:
        await sent.edit_text(f"❌ Error: {str(e)}")
