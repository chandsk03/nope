import logging
import json
import os
import sqlite3
import time
import random
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# Configure logging with rotation
logger = logging.getLogger(__name__)
handler = RotatingFileHandler("bot_marketing.log", maxBytes=5*1024*1024, backupCount=3)
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[handler])

# Configuration (use environment variables)
API_ID = os.getenv("API_ID", "29637547")
API_HASH = os.getenv("API_HASH", "13e303a526522f741c0680cfc8cd9c00")
BOT_TOKEN = os.getenv("BOT_TOKEN", "7552161237:AAGnwooPr-CUI3UuL8DNV62e2DJSioYnkIw")
SESSION_FILE = os.getenv("SESSION_FILE", "+213663915683.session")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7303763913"))
SESSION_USERNAME = os.getenv("SESSION_USERNAME", "@none_seller")

# Database setup
def init_db():
    """Initialize the SQLite database with required tables."""
    try:
        with sqlite3.connect("marketing.db") as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_interaction TIMESTAMP,
                last_interaction TIMESTAMP,
                interaction_count INTEGER DEFAULT 0,
                rate_limit INTEGER DEFAULT 0,
                marketing_stage TEXT DEFAULT 'new'
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                message TEXT,
                sent_count INTEGER DEFAULT 0,
                last_sent TIMESTAMP
            )''')
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database initialization failed: {e}")

# Session management
def save_session(session_string):
    """Save Telegram client session to a file."""
    try:
        with open(SESSION_FILE, "w") as f:
            json.dump({"session": session_string}, f)
    except IOError as e:
        logger.error(f"Failed to save session: {e}")

def load_session():
    """Load Telegram client session from a file."""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                data = json.load(f)
                return data.get("session")
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load session: {e}")
    return None

# Rate limiting
def check_rate_limit(user_id):
    """Check if user has exceeded rate limit (8 messages per minute)."""
    try:
        with sqlite3.connect("marketing.db") as conn:
            c = conn.cursor()
            c.execute("SELECT rate_limit, last_interaction FROM users WHERE user_id = ?", (user_id,))
            result = c.fetchone()
            if result:
                rate_limit, last_interaction = result
                if rate_limit >= 8:
                    last_time = datetime.fromisoformat(last_interaction)
                    if (datetime.now() - last_time).seconds < 60:
                        logger.warning(f"Rate limit exceeded for user {user_id}")
                        return False
            c.execute("UPDATE users SET rate_limit = rate_limit + 1, last_interaction = ? WHERE user_id = ?",
                      (datetime.now().isoformat(), user_id))
            conn.commit()
            return True
    except sqlite3.Error as e:
        logger.error(f"Rate limit check failed: {e}")
        return False

async def reset_rate_limits(context: ContextTypes.DEFAULT_TYPE):
    """Reset rate limits for all users."""
    try:
        with sqlite3.connect("marketing.db") as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET rate_limit = 0")
            conn.commit()
            logger.info("Rate limits reset")
    except sqlite3.Error as e:
        logger.error(f"Rate limit reset failed: {e}")

# Initialize Telegram client
async def init_client():
    """Initialize and start the Telegram client."""
    try:
        session_string = load_session()
        client = TelegramClient(
            StringSession(session_string) if session_string else StringSession(),
            API_ID,
            API_HASH,
        )
        await client.start(bot_token=BOT_TOKEN)
        if not session_string:
            save_session(client.session.save())
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Telegram client: {e}")
        raise

# Marketing messages
WELCOME_NEW = [
    "👋 Welcome to our Telegram Account Marketing Hub! 🌟 Discover premium Telegram accounts! Use /promotions to learn more!",
    "🎉 Hey there! Excited to have you! Explore our top-tier Telegram accounts with /promotions! 🚀",
    "✨ New here? Welcome to the best place for Telegram account promotions! Check out /promotions! 📱"
]

WELCOME_BACK = [
    "🎉 Welcome back! Ready for more Telegram account awesomeness? Use /promotions! 🚀",
    "👋 Great to see you again! Dive into our latest Telegram account offers with /promotions! 🌟",
    "✨ You're back! Explore our premium Telegram accounts with /promotions! 📱"
]

PROMO_MESSAGES = [
    "🌟 Discover Premium Telegram Accounts! High-quality, verified accounts for all your needs! Reply 'INFO' for details! 📱",
    "🚀 Elevate your Telegram game with our exclusive accounts! Reply 'INTERESTED' to learn more! ✨",
    "🎉 Special Promotion! Get the best Telegram accounts tailored for you! Reply 'DETAILS' now! 🛒"
]

# Bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    user_id = update.effective_user.id
    if not check_rate_limit(user_id):
        await update.message.reply_text("⏳ Please wait a minute before sending more messages.")
        return

    try:
        with sqlite3.connect("marketing.db") as conn:
            c = conn.cursor()
            c.execute("SELECT first_interaction, interaction_count FROM users WHERE user_id = ?", (user_id,))
            result = c.fetchone()

            if result:
                welcome_message = random.choice(WELCOME_BACK)
                c.execute("UPDATE users SET interaction_count = interaction_count + 1, last_interaction = ?, marketing_stage = ? WHERE user_id = ?",
                          (datetime.now().isoformat(), 'returning', user_id))
            else:
                welcome_message = random.choice(WELCOME_NEW)
                c.execute("INSERT INTO users (user_id, username, first_interaction, last_interaction, interaction_count, marketing_stage) VALUES (?, ?, ?, ?, ?, ?)",
                          (user_id, update.effective_user.username, datetime.now().isoformat(), datetime.now().isoformat(), 1, 'new'))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error in start handler: {e}")
        await update.message.reply_text("⚠️ An error occurred. Please try again later.")
        return

    await update.message.reply_text(welcome_message)
    await update.message.reply_text("⏳ Please wait, an admin will get back to you soon!")

async def promotions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /promotions command."""
    user_id = update.effective_user.id
    if not check_rate_limit(user_id):
        await update.message.reply_text("⏳ Please wait a minute before sending more messages.")
        return

    keyboard = [
        [
            InlineKeyboardButton("Learn More", callback_data="learn_more"),
            InlineKeyboardButton("Contact Admin", callback_data="contact_admin"),
        ],
        [InlineKeyboardButton("View Account", callback_data="view_account")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        random.choice(PROMO_MESSAGES) + "\n\nWhat would you like to do?",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callback queries."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not check_rate_limit(user_id):
        await query.message.reply_text("⏳ Please wait a minute before sending more messages.")
        return

    try:
        with sqlite3.connect("marketing.db") as conn:
            c = conn.cursor()
            if query.data == "learn_more":
                await query.message.reply_text(
                    "📱 Our Telegram accounts are perfect for:\n"
                    "✅ Business marketing\n"
                    "✅ Community building\n"
                    "✅ Personal branding\n\n"
                    "Reply 'INTERESTED' to get in touch with our team!"
                )
            elif query.data == "contact_admin":
                await query.message.reply_text(
                    "⏳ An admin will reach out to you soon! In the meantime, reply 'INFO' for more details!"
                )
            elif query.data == "view_account":
                await query.message.reply_text(
                    f"🌟 Interested in our premium Telegram accounts?\n"
                    f"Contact our session account: {SESSION_USERNAME}\n"
                    f"An admin will guide you through the process!"
                )

            c.execute("UPDATE users SET marketing_stage = ?, interaction_count = interaction_count + 1 WHERE user_id = ?",
                      ('engaged', user_id))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error in button callback: {e}")
        await query.message.reply_text("⚠️ An error occurred. Please try again later.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    user_id = update.effective_user.id
    if not check_rate_limit(user_id):
        await update.message.reply_text("⏳ Please wait a minute before sending more messages.")
        return

    text = update.message.text.lower()
    responses = {
        "info": "ℹ️ Our Telegram accounts are verified and ready for your marketing needs! Use /promotions to explore!",
        "interested": f"🎉 Great! Contact our session account {SESSION_USERNAME} to proceed! An admin will assist you soon!",
        "details": "📱 Premium Telegram accounts with top features! Reply 'INTERESTED' or use /promotions for more!"
    }

    response = responses.get(text, f"⏳ Thanks for your message! Please wait, an admin will get back to you soon!\n\n{random.choice(PROMO_MESSAGES)}")

    await update.message.reply_text(response)

    try:
        with sqlite3.connect("marketing.db") as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET interaction_count = interaction_count + 1, last_interaction = ?, marketing_stage = ? WHERE user_id = ?",
                      (datetime.now().isoformat(), 'active', user_id))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error in message handler: {e}")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /stats command for admins."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 Unauthorized access.")
        return

    try:
        with sqlite3.connect("marketing.db") as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users")
            user_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM users WHERE marketing_stage = 'engaged'")
            engaged_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM users WHERE marketing_stage = 'active'")
            active_count = c.fetchone()[0]
            await update.message.reply_text(
                f"📊 Marketing Statistics:\n"
                f"Total Users: {user_count}\n"
                f"Engaged Users: {engaged_count}\n"
                f"Active Users: {active_count}"
            )
    except sqlite3.Error as e:
        logger.error(f"Database error in admin stats: {e}")
        await update.message.reply_text("⚠️ An error occurred. Please try again later.")

async def send_promo(context: ContextTypes.DEFAULT_TYPE):
    """Send promotional messages to eligible users."""
    promo_message = random.choice(PROMO_MESSAGES)
    try:
        with sqlite3.connect("marketing.db") as conn:
            c = conn.cursor()
            c.execute("SELECT user_id FROM users WHERE marketing_stage IN ('new', 'returning', 'active')")
            users = c.fetchall()

            for user_id in users:
                try:
                    await context.bot.send_message(
                        chat_id=user_id[0],
                        text=promo_message + "\n\nUse /promotions to learn more!"
                    )
                except Exception as e:
                    logger.error(f"Failed to send promo to {user_id[0]}: {e}")

            c.execute("INSERT INTO campaigns (name, message, sent_count, last_sent) VALUES (?, ?, ?, ?)",
                      ('daily_promo', promo_message, len(users), datetime.now().isoformat()))
            conn.commit()
            logger.info(f"Sent promo to {len(users)} users")
    except sqlite3.Error as e:
        logger.error(f"Database error in send_promo: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors during bot operation."""
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("⚠️ An error occurred. Please try again or contact an admin!")

def main():
    """Main function to start the bot."""
    init_db()
    try:
        app = Application.builder().token(BOT_TOKEN).build()

        # Add handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("promotions", promotions))
        app.add_handler(CommandHandler("stats", admin_stats))
        app.add_handler(CallbackQueryHandler(button_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_error_handler(error_handler)

        # Schedule jobs if JobQueue is available
        if app.job_queue is None:
            logger.error("JobQueue is not available. Install python-telegram-bot[job-queue] to enable scheduled tasks.")
            raise RuntimeError("JobQueue is required but not available.")
        
        app.job_queue.run_repeating(reset_rate_limits, interval=60, first=60)
        app.job_queue.run_daily(send_promo, time=time(hour=12, minute=0, second=0))

        logger.info("Bot is starting...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")
        raise

if __name__ == "__main__":
    main()
