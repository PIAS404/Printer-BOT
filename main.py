import os
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import telegram

# ====== CONFIG ======
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # <-- put your token here

# ====== GLOBAL STATE ======
chat_state = {}
running_tasks = {}
_monitor_task = None

# ====== BUTTONS ======
def get_buttons(is_running: bool):
    if is_running:
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ STOP", callback_data="stop")]])
    else:
        return InlineKeyboardMarkup([[InlineKeyboardButton("▶️ START", callback_data="start")]])


# ====== SAFE SEND (without auto-reaction) ======
async def safe_send(bot: telegram.Bot, chat_id: int, text: str, reply_markup=None, max_retries=4):
    """
    Send message with retries. After successful send, print to terminal.
    No auto-reaction is performed (reaction removed).
    """
    delay = 0.01
    for attempt in range(1, max_retries + 1):
        try:
            sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] Sent to chat={chat_id}: {text} (message_id={sent.message_id})")
            return sent

        except (telegram.error.NetworkError, telegram.error.TimedOut) as e:
            print(f"[safe_send] attempt {attempt} failed: {type(e).__name__}: {e}")
            if attempt == max_retries:
                print("[safe_send] max retries reached, giving up this send.")
                raise
            await asyncio.sleep(delay)
            delay *= 0.01
        except Exception as e:
            print(f"[safe_send] unexpected error attempt {attempt}: {type(e).__name__}: {e}")
            if attempt == max_retries:
                raise
            await asyncio.sleep(delay)
            delay *= 0.01


# ====== COUNTER TASK ======
async def counter_task(application, chat_id: int):
    state = chat_state.get(chat_id)
    if not state:
        return
    bot = application.bot
    try:
        while True:
            state = chat_state.get(chat_id)
            if not state or not state.get("running", False):
                print(f"[counter_task] stopping because running flag false for chat={chat_id}")
                return

            n = state.get("n", 1)
            delay = state.get("delay", 0.01)
            text = f"⚡ {n} 𝗠𝗲𝘀𝘀𝗮𝗴𝗲 𝗦𝗲𝗻𝘁 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆 ✅"

            try:
                await safe_send(bot, chat_id, text, reply_markup=get_buttons(True))
            except Exception as e:
                print(f"[counter_task] send permanently failed chat={chat_id} n={n}: {e}")
                await asyncio.sleep(1)

            chat_state[chat_id]["n"] = n + 1
            await asyncio.sleep(delay)

    except asyncio.CancelledError:
        print(f"[counter_task] cancelled for chat={chat_id}")
        raise
    except Exception as e:
        print(f"[counter_task] unexpected exception for chat={chat_id}: {type(e).__name__}: {e}")
        return


# ====== MONITOR ======
async def monitor_loop(application, interval: float = 3.0):
    print("[monitor] started")
    while True:
        try:
            for chat_id, state in list(chat_state.items()):
                should_run = state.get("running", False)
                has_task = chat_id in running_tasks and not running_tasks[chat_id].done()

                if should_run and not has_task:
                    print(f"[monitor] restarting counter for chat={chat_id} (n={state.get('n')} delay={state.get('delay')})")
                    task = asyncio.create_task(counter_task(application, chat_id))
                    running_tasks[chat_id] = task

                if not should_run and has_task:
                    print(f"[monitor] cancelling task for chat={chat_id} because running=False")
                    t = running_tasks.pop(chat_id, None)
                    if t:
                        t.cancel()

            for cid, t in list(running_tasks.items()):
                if t.done():
                    try:
                        exc = t.exception()
                        if exc:
                            print(f"[monitor] task for chat={cid} finished with exception: {type(exc).__name__}: {exc}")
                        else:
                            print(f"[monitor] task for chat={cid} finished normally.")
                    except Exception:
                        pass
                    running_tasks.pop(cid, None)

        except Exception as e:
            print(f"[monitor] unexpected error: {type(e).__name__}: {e}")

        await asyncio.sleep(interval)


# ====== COMMANDS / BUTTON HANDLERS ======
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in chat_state:
        chat_state[chat_id] = {"n": 1, "delay": 0.01, "running": True}
    else:
        chat_state[chat_id]["running"] = True
        if context.args:
            try:
                d = float(context.args[0])
                chat_state[chat_id]["delay"] = max(0.01, d)
            except:
                pass

    if chat_id in running_tasks and not running_tasks[chat_id].done():
        await update.message.reply_text("Already running!", reply_markup=get_buttons(True))
    else:
        await update.message.reply_text("▶️ Counter Started (monitor will keep it running).", reply_markup=get_buttons(True))


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in chat_state or not chat_state[chat_id].get("running", False):
        await update.message.reply_text("Not running!", reply_markup=get_buttons(False))
        return
    chat_state[chat_id]["running"] = False
    await update.message.reply_text("⛔ Counter Stopped", reply_markup=get_buttons(False))


async def handle_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    if query.data == "start":
        if chat_id not in chat_state:
            chat_state[chat_id] = {"n": 1, "delay": 0.01, "running": True}
        else:
            chat_state[chat_id]["running"] = True
        await query.message.reply_text("▶️ Started (monitor will keep it running).", reply_markup=get_buttons(True))
    elif query.data == "stop":
        if chat_id in chat_state:
            chat_state[chat_id]["running"] = False
        await query.message.reply_text("⛔ Stopped.", reply_markup=get_buttons(False))


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    st = chat_state.get(chat_id)
    if not st or not st.get("running", False):
        await update.message.reply_text("❌ Counter not active.", reply_markup=get_buttons(False))
    else:
        await update.message.reply_text(f"✔️ Running. Next n={st.get('n',1)} delay={st.get('delay',0.01)}", reply_markup=get_buttons(True))


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"[error_handler] {type(context.error).__name__}: {context.error}")


# ====== MAIN ======
def main():
    global _monitor_task
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CallbackQueryHandler(handle_click))
    app.add_error_handler(error_handler)

    async def _on_startup(application):
        global _monitor_task
        print("[main] app startup - launching monitor")
        _monitor_task = asyncio.create_task(monitor_loop(application, interval=3.0))

    app.post_init = _on_startup
    print("Bot is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
