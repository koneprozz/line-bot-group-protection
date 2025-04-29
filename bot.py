from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import re

app = Flask(__name__)

import os
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

admin_users = ['U1234567890abcdef']

group_config = {}

def get_group_config(group_id):
    if group_id not in group_config:
        group_config[group_id] = {
            "lock_enabled": False,
            "link_block": True,
            "invite_block": True
        }
    return group_config[group_id]

def contains_link(text):
    return bool(re.search(r'https?://|www\.', text))

def send_log_to_admin(text):
    for admin_id in admin_users:
        try:
            line_bot_api.push_message(admin_id, TextSendMessage(text))
        except Exception as e:
            print(f"Log ส่งไม่สำเร็จ: {e}")

def kick_user(group_id, user_id, reply_token=None, reason="ไม่ระบุ"):
    try:
        line_bot_api.kickout_group_member(group_id, user_id)
        profile = line_bot_api.get_profile(user_id)
        user_name = profile.display_name
        send_log_to_admin(f"\U0001F6A5 เตะสมาชิก: {user_name} (ID: {user_id})\nกลุ่ม: {group_id}\nเหตุผล: {reason}")
    except:
        if reply_token:
            line_bot_api.reply_message(reply_token, TextSendMessage("❌ ไม่สามารถเตะได้ (อาจไม่มีสิทธิ์)"))

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent)
def handle_message(event):
    user_id = event.source.user_id
    group_id = getattr(event.source, 'group_id', None)
    msg = event.message

    if group_id is None:
        return

    config = get_group_config(group_id)

    if isinstance(msg, TextMessage):
        text = msg.text.strip().lower()

        if user_id in admin_users:
            if text == "/menu":
                menu = (
                    "📋 คำสั่งแอดมิน:\n"
                    "/lock - ล็อกกลุ่ม\n"
                    "/unlock - ปลดล็อกกลุ่ม\n"
                    "/enable link - เปิดบล็อกลิงก์\n"
                    "/disable link - ปิดบล็อกลิงก์\n"
                    "/enable invite - เปิดบล็อกเชิญสมาชิก\n"
                    "/disable invite - ปิดบล็อกเชิญสมาชิก\n"
                    "/status - ดูสถานะ"
                )
                line_bot_api.reply_message(event.reply_token, TextSendMessage(menu))
                return

            elif text == "/lock":
                config["lock_enabled"] = True
                line_bot_api.reply_message(event.reply_token, TextSendMessage("🔒 ล็อกกลุ่มแล้ว"))
                return

            elif text == "/unlock":
                config["lock_enabled"] = False
                line_bot_api.reply_message(event.reply_token, TextSendMessage("🔓 ปลดล็อกกลุ่มแล้ว"))
                return

            elif text == "/enable link":
                config["link_block"] = True
                line_bot_api.reply_message(event.reply_token, TextSendMessage("✅ เปิดบล็อกลิงก์"))
                return

            elif text == "/disable link":
                config["link_block"] = False
                line_bot_api.reply_message(event.reply_token, TextSendMessage("❌ ปิดบล็อกลิงก์"))
                return

            elif text == "/enable invite":
                config["invite_block"] = True
                line_bot_api.reply_message(event.reply_token, TextSendMessage("✅ เปิดบล็อกการเชิญ"))
                return

            elif text == "/disable invite":
                config["invite_block"] = False
                line_bot_api.reply_message(event.reply_token, TextSendMessage("❌ ปิดบล็อกการเชิญ"))
                return

            elif text == "/status":
                status = (
                    f"🔧 สถานะกลุ่ม:\n"
                    f"🔒 ล็อกกลุ่ม: {'✅' if config['lock_enabled'] else '❌'}\n"
                    f"🔗 บล็อกลิงก์: {'✅' if config['link_block'] else '❌'}\n"
                    f"🚫 บล็อกเชิญสมาชิก: {'✅' if config['invite_block'] else '❌'}"
                )
                line_bot_api.reply_message(event.reply_token, TextSendMessage(status))
                return

        if user_id not in admin_users:
            if config["lock_enabled"]:
                if contains_link(msg.text) and config["link_block"]:
                    kick_user(group_id, user_id, event.reply_token, reason="ส่งลิงก์ในกลุ่มที่ถูกบล็อก")
                    return

            allowed = (TextMessage, ImageMessage, StickerMessage)
            if config["lock_enabled"] and not isinstance(msg, allowed):
                kick_user(group_id, user_id, event.reply_token, reason="ส่งไฟล์/สื่อไม่อนุญาตตอนกลุ่มล็อก")
                return

    if isinstance(msg, (ImageMessage, StickerMessage)):
        return

    if user_id not in admin_users and config["lock_enabled"]:
        allowed = (TextMessage, ImageMessage, StickerMessage)
        if not isinstance(msg, allowed):
            kick_user(group_id, user_id, event.reply_token, reason="ส่งไฟล์/สื่อไม่อนุญาตตอนกลุ่มล็อก")

@handler.add(MemberJoinedEvent)
def handle_member_joined(event):
    group_id = event.source.group_id
    config = get_group_config(group_id)

    for member in event.joined.members:
        if config["invite_block"] and member.user_id not in admin_users:
            kick_user(group_id, member.user_id, reason="ถูกเชิญโดยไม่ใช่แอดมิน")
