# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


import os
import ssl
import certifi
import aiohttp
import time
from PIL import (Image, ImageDraw, ImageEnhance,
                 ImageFilter, ImageFont, ImageOps)

from anamika import config, logger
from anamika.helpers import Track


class Thumbnail:
    def __init__(self):
        self.fill = (255, 255, 255)
        self.font_bold = "anony/helpers/Raleway-Bold.ttf"
        self.font_light = "anony/helpers/Inter-Light.ttf"
        self.session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self.session = aiohttp.ClientSession()
    async def close(self) -> None:
        if self.session:
            await self.session.close()

    async def save_thumb(self, output_path: str, url: str) -> str:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        async with self.session.get(url, ssl=ssl_context) as resp:
            with open(output_path, "wb") as f: f.write(await resp.read())
        return output_path

    def changeImageSize(self, maxWidth, maxHeight, image):
        widthRatio = maxWidth / image.size[0]
        heightRatio = maxHeight / image.size[1]
        newRatio = max(widthRatio, heightRatio)
        newSize = (int(image.size[0] * newRatio), int(image.size[1] * newRatio))
        image = image.resize(newSize, Image.Resampling.LANCZOS)
        return image

    def truncate(self, text):
        if len(text) >= 45:
            return text[:42] + "..."
        return text

    async def generate(self, song: Track, size=(1280, 720)) -> str:
        if not self.session:
            await self.start()
            
        thumb_path = f"cache/thumb_{song.id}.png"
        if not os.path.exists(thumb_path):
            try:
                await self.save_thumb(thumb_path, song.thumbnail)
            except Exception as e:
                logger.error(f"Failed to save thumbnail: {e}")
                return config.DEFAULT_THUMB

        try:
            img = Image.open(thumb_path)
        except Exception as e:
            logger.error(f"Failed to open thumbnail: {e}")
            return config.DEFAULT_THUMB

        # Background blur
        background = self.changeImageSize(1280, 720, img)
        background = background.crop((0, 0, 1280, 720))
        background = background.filter(ImageFilter.GaussianBlur(radius=40))
        enhancer = ImageEnhance.Brightness(background)
        background = enhancer.enhance(0.7)
        background = background.convert("RGBA")

        draw = ImageDraw.Draw(background)
        
        # Rounded main cover art
        cover_size = (640, 480)
        cover = self.changeImageSize(cover_size[0], cover_size[1], img)
        cover = cover.crop((0, 0, cover_size[0], cover_size[1]))
        
        # Create rounded corners mask
        mask = Image.new('L', cover_size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, cover_size[0], cover_size[1]), radius=50, fill=255)
        
        # Center the cover
        cover_x = (1280 - cover_size[0]) // 2
        cover_y = (720 - cover_size[1]) // 2 - 50
        
        # Add a subtle glow/shadow effect
        shadow_mask = Image.new('L', (cover_size[0] + 40, cover_size[1] + 40), 0)
        shadow_draw = ImageDraw.Draw(shadow_mask)
        shadow_draw.rounded_rectangle((20, 20, cover_size[0] + 20, cover_size[1] + 20), radius=60, fill=100)
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(radius=20))
        background.paste((255, 255, 255), (cover_x - 20, cover_y - 20), shadow_mask)

        background.paste(cover, (cover_x, cover_y), mask)

        # Fonts
        font_title = ImageFont.truetype(self.font_bold, 45)
        font_info = ImageFont.truetype(self.font_light, 35)
        font_duration = ImageFont.truetype(self.font_bold, 30)
        font_hires = ImageFont.truetype(self.font_bold, 45)

        # Title and Info
        title = self.truncate(song.title)
        artist = f"{song.channel_name} | {song.view_count} views" if song.view_count else song.channel_name
        
        draw.text((cover_x, cover_y + cover_size[1] + 40), title, fill=self.fill, font=font_title)
        draw.text((cover_x, cover_y + cover_size[1] + 100), artist, fill=self.fill, font=font_info)

        # Hi-Res label with background
        hires_text = "Hi-Res"
        hires_bbox = draw.textbbox((0, 0), hires_text, font=font_hires)
        hires_width = hires_bbox[2] - hires_bbox[0]
        hires_height = hires_bbox[3] - hires_bbox[1]
        
        hires_x = cover_x + cover_size[0] + 40
        hires_y = cover_y + (cover_size[1] // 2) - (hires_height // 2)
        
        # Draw rounded background for label
        draw.rounded_rectangle(
            (hires_x - 15, hires_y - 10, hires_x + hires_width + 15, hires_y + hires_height + 15),
            radius=15,
            fill=(255, 255, 255, 80),
            outline=self.fill,
            width=2
        )
        draw.text((hires_x, hires_y), hires_text, fill=self.fill, font=font_hires)

        # Progress bar (left vertical)
        bar_x = 100
        bar_start_y = 120
        bar_end_y = 600
        bar_height = bar_end_y - bar_start_y
        
        # Background bar
        draw.line((bar_x, bar_start_y, bar_x, bar_end_y), fill=(150, 150, 150), width=12)
        
        # Duration text
        duration = song.duration if song.duration else "00:00"
        draw.text((bar_x - 25, bar_start_y - 50), duration, fill=self.fill, font=font_duration)
        
        # Current time text
        curr_time = time.strftime("%M:%S", time.gmtime(song.time))
        draw.text((bar_x - 30, bar_end_y + 20), curr_time, fill=self.fill, font=font_duration)
        
        # Progress (calculating from current time and total duration)
        if song.duration_sec > 0:
            progress = (song.time / song.duration_sec)
            progress_y = bar_end_y - (bar_height * progress)
            # Active bar (from bottom to current position)
            draw.line((bar_x, bar_end_y, bar_x, progress_y), fill=(100, 200, 255), width=12)
        else:
            # If no duration, just draw the full bar as inactive
            pass

        final_thumb = f"cache/final_{song.id}.png"
        background.convert("RGB").save(final_thumb)
        
        # Clean up
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
            
        return final_thumb
