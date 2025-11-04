"""
Telegram utility functions for robust file sending
"""
import logging
import os
from typing import Optional, Tuple
from telegram import Bot, InputFile
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

async def send_qr_image_robust(bot: Bot, chat_id: int, qr_image_path: str, client_name: str) -> Tuple[bool, str]:
    """
    Robustly send QR code image with multiple fallback methods
    Returns: (success, message)
    """
    if not os.path.exists(qr_image_path):
        return False, "QR image file not found"
    
    file_size = os.path.getsize(qr_image_path)
    if file_size == 0:
        return False, "QR image file is empty"
    
    caption = f"📱 QR Code for {client_name}\n\nScan this with your WireGuard app to connect!"
    
    # Method 1: Send as photo with file object
    try:
        with open(qr_image_path, 'rb') as photo_file:
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo_file,
                caption=caption
            )
        logger.info(f"QR code sent as photo for {client_name}")
        return True, "QR code sent as photo"
    except TelegramError as e:
        logger.warning(f"Failed to send QR as photo: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error sending QR as photo: {e}")
    
    # Method 2: Send as photo with InputFile
    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=InputFile(qr_image_path, filename=f"{client_name}_qr.png"),
            caption=caption
        )
        logger.info(f"QR code sent as photo (InputFile) for {client_name}")
        return True, "QR code sent as photo"
    except TelegramError as e:
        logger.warning(f"Failed to send QR as photo (InputFile): {e}")
    except Exception as e:
        logger.warning(f"Unexpected error sending QR as photo (InputFile): {e}")
    
    # Method 3: Send as document
    try:
        with open(qr_image_path, 'rb') as doc_file:
            await bot.send_document(
                chat_id=chat_id,
                document=doc_file,
                filename=f"{client_name}_qr.png",
                caption=caption
            )
        logger.info(f"QR code sent as document for {client_name}")
        return True, "QR code sent as document"
    except TelegramError as e:
        logger.warning(f"Failed to send QR as document: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error sending QR as document: {e}")
    
    # Method 4: Send as document with InputFile
    try:
        await bot.send_document(
            chat_id=chat_id,
            document=InputFile(qr_image_path, filename=f"{client_name}_qr.png"),
            caption=caption
        )
        logger.info(f"QR code sent as document (InputFile) for {client_name}")
        return True, "QR code sent as document"
    except TelegramError as e:
        logger.error(f"All methods failed to send QR code. Last error: {e}")
        return False, f"Failed to send QR code: {str(e)}"
    except Exception as e:
        logger.error(f"All methods failed with unexpected error: {e}")
        return False, f"Unexpected error: {str(e)}"
