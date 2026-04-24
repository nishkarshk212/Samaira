# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


import pyrogram
import asyncio
from pyrogram.errors import FloodWait

from anamika import config, logger


class Bot(pyrogram.Client):
    def __init__(self):
        super().__init__(
            name="anony",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            parse_mode=pyrogram.enums.ParseMode.HTML,
            max_concurrent_transmissions=7,
            in_memory=True,
            link_preview_options=pyrogram.types.LinkPreviewOptions(is_disabled=True),
        )
        self.owner = config.OWNER_ID
        self.logger = config.LOGGER_ID
        self.bl_users = pyrogram.filters.user()
        self.sudoers = pyrogram.filters.user(self.owner)

    async def boot(self):
        """
        Starts the bot and performs initial setup.

        Raises:
            SystemExit: If the bot fails to access the log group or is not an administrator in the logger group.
        """
        try:
            await super().start()
        except FloodWait as e:
            logger.warning(f"Telegram FloodWait detected! Waiting for {e.value} seconds...")
            await asyncio.sleep(e.value)
            await super().start()
        except Exception as ex:
            logger.error(f"Failed to start bot: {ex}")
            raise ex

        self.id = self.me.id
        self.name = self.me.first_name
        self.username = self.me.username
        self.mention = self.me.mention

        if self.logger != 0:
            try:
                await self.send_message(self.logger, "Bot Started")
                get = await self.get_chat_member(self.logger, self.id)
                if get.status != pyrogram.enums.ChatMemberStatus.ADMINISTRATOR:
                    logger.warning("Please promote the bot as an admin in logger group.")
            except Exception as ex:
                logger.warning(f"Bot has failed to access the log group: {self.logger}\nReason: {ex}")
        logger.info(f"Bot started as @{self.username}")

    async def exit(self):
        """
        Asynchronously stops the bot.
        """
        await super().stop()
        logger.info("Bot stopped.")
