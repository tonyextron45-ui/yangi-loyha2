import os, sqlite3, logging, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ChatMemberHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN", "8643378046:AAF3VyM6OtHJ4ZkYh7AM5YvFnEQUAA0-o7A")
ADMINS = {int(x) for x in os.getenv("ADMIN_IDS", "8837120659").split(",") if x.strip().isdigit()}
DB = os.getenv("DB_PATH", "/var/data/kino.sqlite3")
PORT = int(os.getenv("PORT", "10000"))
PRICE = os.getenv("PREMIUM_PRICE", "Admin bilan kelishiladi")
PAYMENT = os.getenv("PAYMENT_INFO", "To‘lov ma’lumotini admin beradi.")
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("kino-vibeuz")

def conn():
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    c = sqlite3.connect(DB, timeout=30); c.row_factory = sqlite3.Row
    return c

def init():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT, name TEXT, blocked INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS movies(code TEXT PRIMARY KEY,title TEXT,file_id TEXT,kind TEXT,description TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS channels(channel TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS premium(uid INTEGER PRIMARY KEY,expires TEXT,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS refs(referrer INTEGER, referred INTEGER UNIQUE);
        CREATE TABLE IF NOT EXISTS events(uid INTEGER,channel TEXT,kind TEXT,at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS ads(id INTEGER PRIMARY KEY AUTOINCREMENT,uid INTEGER,file_id TEXT,kind TEXT,caption TEXT,status TEXT DEFAULT 'pending');
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        """)
        c.execute("INSERT OR IGNORE INTO settings VALUES('start','🎬 Kino Vibeuz botiga xush kelibsiz!\\n\\nKino kodini yuboring.')")
        c.execute("INSERT OR IGNORE INTO settings VALUES('help','Kino kodini yuboring. Premium: /premium. Reklama: /ad. Referal: /ref.')")

def admin(uid): return uid in ADMINS
def setval(k,v):
    with conn() as c: c.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,v))
def getval(k):
    with conn() as c:
        r=c.execute("SELECT value FROM settings WHERE key=?",(k,)).fetchone()
    return r["value"] if r else ""
def reg(u):
    if u:
        with conn() as c: c.execute("INSERT INTO users VALUES(?,?,?,0) ON CONFLICT(id) DO UPDATE SET username=excluded.username,name=excluded.name",(u.id,u.username or "",u.first_name or ""))
def premium(uid):
    with conn() as c: r=c.execute("SELECT * FROM premium WHERE uid=? AND active=1",(uid,)).fetchone()
    if not r: return False
    if not r["expires"]: return True
    try: return datetime.fromisoformat(r["expires"]) > datetime.now(timezone.utc)
    except: return True
def kb_admin():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎞 Kino qo‘shish",callback_data="add"),InlineKeyboardButton("✏️ Kino tahrirlash",callback_data="edit")],
        [InlineKeyboardButton("🗑 Kino o‘chirish",callback_data="delete"),InlineKeyboardButton("📊 Statistika",callback_data="stats")],
        [InlineKeyboardButton("📢 Kanallar",callback_data="channels"),InlineKeyboardButton("⭐ Premium",callback_data="premium")],
        [InlineKeyboardButton("🔗 Referal statistika",callback_data="refs"),InlineKeyboardButton("📣 Reklamalar",callback_data="ads")],
        [InlineKeyboardButton("📝 Start/Yordam",callback_data="texts"),InlineKeyboardButton("📨 Xabar yuborish",callback_data="broadcast")]
    ])
async def missing(bot, uid):
    if premium(uid): return []
    with conn() as c: channels=[r["channel"] for r in c.execute("SELECT channel FROM channels")]
    out=[]
    for ch in channels:
        try:
            m=await bot.get_chat_member(ch,uid)
            if m.status not in (ChatMember.MEMBER,ChatMember.ADMINISTRATOR,ChatMember.OWNER,ChatMember.RESTRICTED): out.append(ch)
        except TelegramError:
            out.append(ch)
    return out
def subkb(chs):
    rows=[]
    for ch in chs:
        url=ch if ch.startswith("https://") else "https://t.me/"+ch.lstrip("@")
        rows.append([InlineKeyboardButton("📢 "+ch,url=url)])
    rows.append([InlineKeyboardButton("✅ Obunani tekshirish",callback_data="check")])
    return InlineKeyboardMarkup(rows)
async def start(u:Update,ctx:ContextTypes.DEFAULT_TYPE):
    user=u.effective_user; reg(user)
    if ctx.args and ctx.args[0].startswith("ref"):
        try:
            ref=int(ctx.args[0][3:])
            if ref!=user.id:
                with conn() as c: c.execute("INSERT OR IGNORE INTO refs VALUES(?,?)",(ref,user.id))
        except: pass
    if admin(user.id):
        await u.effective_message.reply_text("🛠 Admin panel",reply_markup=kb_admin()); return
    chs=await missing(ctx.bot,user.id)
    if chs:
        await u.effective_message.reply_text("Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo‘ling:",reply_markup=subkb(chs)); return
    await u.effective_message.reply_text(getval("start"))
async def helpcmd(u,ctx): await u.effective_message.reply_text(getval("help"))
async def check_cb(u,ctx):
    q=u.callback_query; await q.answer()
    chs=await missing(ctx.bot,q.from_user.id)
    if chs: await q.edit_message_text("Hali barcha kanallarga obuna bo‘lmagansiz:",reply_markup=subkb(chs))
    else: await q.edit_message_text(getval("start"))
async def admin_cmd(u,ctx):
    if not admin(u.effective_user.id): return await u.effective_message.reply_text("Ruxsat yo‘q.")
    await u.effective_message.reply_text("🛠 Admin panel",reply_markup=kb_admin())
async def admin_cb(u,ctx):
    q=u.callback_query; await q.answer()
    if not admin(q.from_user.id): return await q.message.reply_text("Ruxsat yo‘q.")
    d=q.data
    actions={"add":"add","edit":"edit","delete":"delete","premium":"premium","refs":"refs","broadcast":"broadcast"}
    if d in actions:
        ctx.user_data["action"]=actions[d]
        prompts={"add":"KOD | NOMI | TAVSIF yuboring, keyin video/rasm/fayl yuborasiz.","edit":"KOD | YANGI NOMI | YANGI TAVSIF","delete":"O‘chiriladigan kino kodini yuboring.","premium":"USER_ID | kunlar (masalan 12345 | 30) yoki 12345 | forever","refs":"Referal statistikasi uchun foydalanuvchi ID yuboring.","broadcast":"Barcha foydalanuvchilarga yuboriladigan matn yoki media yuboring."}
        return await q.message.reply_text(prompts[d])
    if d=="stats":
        with conn() as c:
            n=c.execute("SELECT COUNT(*) FROM users WHERE blocked=0").fetchone()[0]
            m=c.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
            p=c.execute("SELECT COUNT(*) FROM premium WHERE active=1").fetchone()[0]
            a=c.execute("SELECT COUNT(*) FROM ads WHERE status='pending'").fetchone()[0]
            r=c.execute("SELECT COUNT(*) FROM refs").fetchone()[0]
        return await q.message.reply_text(f"📊 Bot statistikasi\\n👥 Foydalanuvchilar: {n}\\n🎞 Kinolar: {m}\\n⭐ Premium: {p}\\n📣 Kutilayotgan reklamalar: {a}\\n🔗 Referal yozuvlari: {r}")
    if d=="channels":
        with conn() as c: ch=[r["channel"] for r in c.execute("SELECT channel FROM channels")]
        return await q.message.reply_text("Kanallar: "+(", ".join(ch) or "yo‘q")+
            "\\nQo‘shish: /addchannel @kanal\\nO‘chirish: /delchannel @kanal\\nStatistika: /channelstats")
    if d=="texts": return await q.message.reply_text("Start: /setstart Yangi matn\\nYordam: /sethelp Yangi matn")
    if d=="ads":
        with conn() as c: rows=c.execute("SELECT * FROM ads WHERE status='pending' ORDER BY id DESC LIMIT 10").fetchall()
        if not rows: return await q.message.reply_text("Kutilayotgan reklama yo‘q.")
        for r in rows:
            await q.message.reply_text(f"Reklama #{r['id']} | user {r['uid']}\\n{r['caption'] or ''}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Tasdiqlash",callback_data=f"adok_{r['id']}"),InlineKeyboardButton("❌ Rad etish",callback_data=f"adno_{r['id']}")]]))
async def input_text(u,ctx):
    msg=u.effective_message; user=u.effective_user
    if not msg or not msg.text: return
    reg(user)
    if not admin(user.id):
        chs=await missing(ctx.bot,user.id)
        if chs: return await msg.reply_text("Kino olishdan oldin kanalga obuna bo‘ling:",reply_markup=subkb(chs))
        with conn() as c: r=c.execute("SELECT * FROM movies WHERE code=?",(msg.text.strip(),)).fetchone()
        if not r: return await msg.reply_text("❌ Bu kod bo‘yicha kino topilmadi.")
        caption="🎬 "+r["title"]+(("\\n\\n"+r["description"]) if r["description"] else "")
        try:
            if r["kind"]=="video": await msg.reply_video(r["file_id"],caption=caption)
            elif r["kind"]=="photo": await msg.reply_photo(r["file_id"],caption=caption)
            else: await msg.reply_document(r["file_id"],caption=caption)
        except TelegramError: await msg.reply_text("Kinoni yuborishda xatolik. Admin bilan bog‘laning.")
        return
    action=ctx.user_data.get("action")
    if not action: return
    text=msg.text.strip()
    if action in ("add","edit"):
        p=[x.strip() for x in text.split("|")]
        if len(p)<2: return await msg.reply_text("Format: KOD | NOMI | TAVSIF")
        code,title=p[0],p[1]; desc=p[2] if len(p)>2 else ""
        if action=="add":
            ctx.user_data["pending_movie"]={"code":code,"title":title,"description":desc}; ctx.user_data["action"]="moviefile"
            return await msg.reply_text("Endi shu kino videosi, rasmi yoki faylini yuboring.")
        with conn() as c: cur=c.execute("UPDATE movies SET title=?,description=? WHERE code=?",(title,desc,code))
        ctx.user_data.pop("action",None)
        return await msg.reply_text("✅ Kino tahrirlandi." if cur.rowcount else "Kino kodi topilmadi.")
    if action=="delete":
        with conn() as c: cur=c.execute("DELETE FROM movies WHERE code=?",(text,))
        ctx.user_data.pop("action",None); return await msg.reply_text("🗑 Kino o‘chirildi." if cur.rowcount else "Kod topilmadi.")
    if action=="premium":
        p=[x.strip() for x in text.split("|")]
        try:
            uid=int(p[0]); exp=None if p[1].lower()=="forever" else (datetime.now(timezone.utc)+timedelta(days=max(1,int(p[1])))).isoformat()
        except: return await msg.reply_text("Format: USER_ID | kunlar yoki USER_ID | forever")
        with conn() as c: c.execute("INSERT INTO premium VALUES(?,?,1) ON CONFLICT(uid) DO UPDATE SET expires=excluded.expires,active=1",(uid,exp))
        ctx.user_data.pop("action",None); return await msg.reply_text("⭐ Premium faollashtirildi.")
    if action=="refs":
        try: target=int(text)
        except: return await msg.reply_text("ID raqam bo‘lishi kerak.")
        with conn() as c: total=c.execute("SELECT COUNT(*) FROM refs WHERE referrer=?",(target,)).fetchone()[0]
        ctx.user_data.pop("action",None); return await msg.reply_text(f"🔗 {target} referal statistikasi\\nBotga taklif qilganlar: {total}\\nChiqib ketish statistikasi kanal hodisalari orqali /channelstats da.")
    if action=="broadcast":
        with conn() as c: ids=[r["id"] for r in c.execute("SELECT id FROM users WHERE blocked=0")]
        sent=0
        for target in ids:
            try: await ctx.bot.send_message(target,text); sent+=1
            except TelegramError:
                with conn() as c: c.execute("UPDATE users SET blocked=1 WHERE id=?",(target,))
        ctx.user_data.pop("action",None); return await msg.reply_text(f"📨 Yuborildi: {sent}/{len(ids)}")
async def media(u,ctx):
    msg=u.effective_message; user=u.effective_user
    if not msg: return
    action=ctx.user_data.get("action")
    if admin(user.id) and action=="moviefile":
        p=ctx.user_data.get("pending_movie")
        if msg.video: fid,kind=msg.video.file_id,"video"
        elif msg.photo: fid,kind=msg.photo[-1].file_id,"photo"
        elif msg.document: fid,kind=msg.document.file_id,"document"
        else: return await msg.reply_text("Video, rasm yoki hujjat yuboring.")
        with conn() as c: c.execute("INSERT OR REPLACE INTO movies VALUES(?,?,?,?,?)",(p["code"],p["title"],fid,kind,p["description"]))
        ctx.user_data.pop("action",None); ctx.user_data.pop("pending_movie",None)
        return await msg.reply_text(f"✅ Kino saqlandi: {p['title']} (kod {p['code']})")
    if not admin(user.id):
        reg(user)
        if msg.video: fid,kind=msg.video.file_id,"video"
        elif msg.photo: fid,kind=msg.photo[-1].file_id,"photo"
        else: return
        with conn() as c: cur=c.execute("INSERT INTO ads(uid,file_id,kind,caption) VALUES(?,?,?,?)",(user.id,fid,kind,msg.caption or "")); aid=cur.lastrowid
        await msg.reply_text(f"📣 Reklama so‘rovi qabul qilindi: #{aid}. Admin ko‘rib chiqadi.")
        for a in ADMINS:
            try: await ctx.bot.send_message(a,f"Yangi reklama #{aid}, foydalanuvchi {user.id}. /admin → Reklamalar")
            except TelegramError: pass
async def ad_review(u,ctx):
    q=u.callback_query; await q.answer()
    if not admin(q.from_user.id): return await q.message.reply_text("Ruxsat yo‘q.")
    act,aid=q.data.split("_"); aid=int(aid); status="approved" if act=="adok" else "rejected"
    with conn() as c: r=c.execute("SELECT * FROM ads WHERE id=?",(aid,)).fetchone(); c.execute("UPDATE ads SET status=? WHERE id=?",(status,aid))
    if r:
        try: await ctx.bot.send_message(r["uid"],"Reklama so‘rovingiz "+("tasdiqlandi." if status=="approved" else "rad etildi."))
        except TelegramError: pass
    await q.edit_message_reply_markup(reply_markup=None)
async def premium_cmd(u,ctx):
    uid=u.effective_user.id
    if premium(uid): return await u.effective_message.reply_text("⭐ Premium faol — majburiy obuna talab qilinmaydi.")
    await u.effective_message.reply_text(f"⭐ Premium xizmat\\nNarx: {PRICE}\\n{PAYMENT}\\n\\nAdmin bilan bog‘laning; to‘lov tekshirilgach admin faollashtiradi.")
    for a in ADMINS:
        try: await ctx.bot.send_message(a,f"Premium so‘rovi: {uid}. Faollashtirish: /grantpremium {uid} 30")
        except TelegramError: pass
async def grantpremium(u,ctx):
    if not admin(u.effective_user.id): return
    try:
        uid=int(ctx.args[0]); days=ctx.args[1].lower()
        exp=None if days=="forever" else (datetime.now(timezone.utc)+timedelta(days=max(1,int(days)))).isoformat()
    except: return await u.effective_message.reply_text("Foydalanish: /grantpremium USER_ID 30 yoki /grantpremium USER_ID forever")
    with conn() as c: c.execute("INSERT INTO premium VALUES(?,?,1) ON CONFLICT(uid) DO UPDATE SET expires=excluded.expires,active=1",(uid,exp))
    await u.effective_message.reply_text("Premium faollashtirildi.")
async def addchannel(u,ctx):
    if not admin(u.effective_user.id) or not ctx.args: return
    ch=ctx.args[0]
    with conn() as c: c.execute("INSERT OR IGNORE INTO channels VALUES(?)",(ch,))
    await u.effective_message.reply_text(f"✅ Kanal qo‘shildi: {ch}. Botni kanalga admin qiling.")
async def delchannel(u,ctx):
    if not admin(u.effective_user.id) or not ctx.args: return
    with conn() as c: c.execute("DELETE FROM channels WHERE channel=?",(ctx.args[0],))
    await u.effective_message.reply_text("Kanal o‘chirildi.")
async def setstart(u,ctx):
    if admin(u.effective_user.id) and ctx.args: setval("start"," ".join(ctx.args)); await u.effective_message.reply_text("Start matni yangilandi.")
async def sethelp(u,ctx):
    if admin(u.effective_user.id) and ctx.args: setval("help"," ".join(ctx.args)); await u.effective_message.reply_text("Yordam matni yangilandi.")
async def refcmd(u,ctx):
    uid=u.effective_user.id; reg(u.effective_user); me=await ctx.bot.get_me()
    with conn() as c: n=c.execute("SELECT COUNT(*) FROM refs WHERE referrer=?",(uid,)).fetchone()[0]
    await u.effective_message.reply_text(f"🔗 Referal havolangiz:\\nhttps://t.me/{me.username}?start=ref{uid}\\nTaklif qilganlar: {n}")
async def channelmember(u,ctx):
    ev=u.chat_member
    if not ev: return
    old=ev.old_chat_member.status in ("member","administrator","creator","restricted")
    new=ev.new_chat_member.status in ("member","administrator","creator","restricted")
    if old==new: return
    kind="joined" if new else "left"; ch="@"+ev.chat.username if ev.chat.username else str(ev.chat.id)
    with conn() as c: c.execute("INSERT INTO events(uid,channel,kind) VALUES(?,?,?)",(ev.new_chat_member.user.id,ch,kind))
async def channelstats(u,ctx):
    if not admin(u.effective_user.id): return
    with conn() as c: rows=c.execute("SELECT channel,kind,COUNT(*) n FROM events GROUP BY channel,kind").fetchall()
    data={}
    for r in rows: data.setdefault(r["channel"],{"joined":0,"left":0})[r["kind"]]=r["n"]
    await u.effective_message.reply_text("📊 Kanal statistikasi (bot kuzatishni boshlaganidan beri):\\n"+("\\n".join(f"{k}\\n➕ {v['joined']} kirgan\\n➖ {v['left']} chiqqan" for k,v in data.items()) or "Hali hodisalar yo‘q. Botni kanalga admin qiling."))
async def adcmd(u,ctx): await u.effective_message.reply_text("📣 Reklama buyurtmasi: rasm/video va tavsifini bitta xabarda yuboring. Admin tasdiqlashi va narxni kelishishi kerak.")
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        body=b"Kino Vibeuz bot running"; self.send_response(200); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self,*a): pass
def health(): HTTPServer(("0.0.0.0",PORT),Health).serve_forever()
def main():
    if not TOKEN: raise RuntimeError("BOT_TOKEN environment variable is missing")
    init(); threading.Thread(target=health,daemon=True).start()
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start)); app.add_handler(CommandHandler("help",helpcmd)); app.add_handler(CommandHandler("admin",admin_cmd))
    app.add_handler(CommandHandler("premium",premium_cmd)); app.add_handler(CommandHandler("grantpremium",grantpremium))
    app.add_handler(CommandHandler("addchannel",addchannel)); app.add_handler(CommandHandler("delchannel",delchannel))
    app.add_handler(CommandHandler("setstart",setstart)); app.add_handler(CommandHandler("sethelp",sethelp))
    app.add_handler(CommandHandler("ref",refcmd)); app.add_handler(CommandHandler("channelstats",channelstats)); app.add_handler(CommandHandler("ad",adcmd))
    app.add_handler(CallbackQueryHandler(check_cb,pattern="^check$")); app.add_handler(CallbackQueryHandler(admin_cb,pattern="^(add|edit|delete|stats|channels|premium|refs|ads|texts|broadcast)$"))
    app.add_handler(CallbackQueryHandler(ad_review,pattern="^(adok|adno)_\\d+$"))
    app.add_handler(ChatMemberHandler(channelmember,ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.VIDEO|filters.PHOTO|filters.Document.ALL,media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,input_text))
    app.run_polling(allowed_updates=["message","callback_query","chat_member","my_chat_member"])
if __name__=="__main__": main()
