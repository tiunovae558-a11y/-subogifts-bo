import asyncio, os, random, logging
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, PreCheckoutQuery
from sqlalchemy import String, Integer, BigInteger, Boolean, Float, ForeignKey, DateTime, Text, select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

TOKEN=os.getenv("BOT_TOKEN","")
DB=os.getenv("DATABASE_URL","sqlite+aiosqlite:///bot.db")
CHANNEL=os.getenv("PROMO_CHANNEL","@ProtivzlaNFT")
SUPPORT=os.getenv("SUPPORT_USERNAME","@support")
ADMINS={int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip().isdigit()}
REF_PERCENT=5

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__="users"
    id:Mapped[int]=mapped_column(primary_key=True)
    tg:Mapped[int]=mapped_column(BigInteger,unique=True,index=True)
    username:Mapped[str|None]=mapped_column(String(255),nullable=True)
    name:Mapped[str|None]=mapped_column(String(255),nullable=True)
    balance:Mapped[int]=mapped_column(Integer,default=0)
    deposits:Mapped[int]=mapped_column(Integer,default=0)
    prizes:Mapped[int]=mapped_column(Integer,default=0)
    referrer:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    notifications:Mapped[bool]=mapped_column(Boolean,default=True)
    created:Mapped[datetime]=mapped_column(DateTime,default=lambda:datetime.now(timezone.utc))
    daily:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)

class Tx(Base):
    __tablename__="tx"
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"))
    amount:Mapped[int]=mapped_column(Integer)
    kind:Mapped[str]=mapped_column(String(40))
    text:Mapped[str]=mapped_column(Text,default="")

class Payment(Base):
    __tablename__="payments"
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"))
    amount:Mapped[int]=mapped_column(Integer)
    charge:Mapped[str]=mapped_column(String(255),unique=True)
    payload:Mapped[str]=mapped_column(String(255))

class Case(Base):
    __tablename__="cases"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(100))
    emoji:Mapped[str]=mapped_column(String(10))
    price:Mapped[int]=mapped_column(Integer)
    daily:Mapped[bool]=mapped_column(Boolean,default=False)
    active:Mapped[bool]=mapped_column(Boolean,default=True)

class Prize(Base):
    __tablename__="prizes"
    id:Mapped[int]=mapped_column(primary_key=True)
    case_id:Mapped[int]=mapped_column(ForeignKey("cases.id"))
    name:Mapped[str]=mapped_column(String(100))
    emoji:Mapped[str]=mapped_column(String(10))
    value:Mapped[int]=mapped_column(Integer)
    weight:Mapped[float]=mapped_column(Float)

class Gift(Base):
    __tablename__="gifts"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(100))
    emoji:Mapped[str]=mapped_column(String(10))
    price:Mapped[int]=mapped_column(Integer)
    telegram_id:Mapped[str|None]=mapped_column(String(100),nullable=True)
    active:Mapped[bool]=mapped_column(Boolean,default=True)

class Task(Base):
    __tablename__="tasks"
    id:Mapped[int]=mapped_column(primary_key=True)
    title:Mapped[str]=mapped_column(String(150))
    reward:Mapped[int]=mapped_column(Integer)
    channel:Mapped[str|None]=mapped_column(String(255),nullable=True)
    active:Mapped[bool]=mapped_column(Boolean,default=True)

class UserTask(Base):
    __tablename__="user_tasks"
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"))
    task_id:Mapped[int]=mapped_column(ForeignKey("tasks.id"))
    done:Mapped[bool]=mapped_column(Boolean,default=False)

engine=create_async_engine(DB)
Session=async_sessionmaker(engine,expire_on_commit=False)
bot=Bot(TOKEN); dp=Dispatcher()

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Получить подарки",callback_data="tasks")],
        [InlineKeyboardButton(text="⭐ Заработать звёзды",callback_data="cases")],
        [InlineKeyboardButton(text="🎁 Магазин подарков",callback_data="shop")],
        [InlineKeyboardButton(text="💝 Ежедневный кейс",callback_data="daily")],
        [InlineKeyboardButton(text="👤 Профиль / Баланс",callback_data="profile")],
        [InlineKeyboardButton(text="📢 Наш канал",url="https://t.me/ProtivzlaNFT")]])

def back(cb="menu"):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад",callback_data=cb)]])

async def user(s,tg):
    return (await s.execute(select(User).where(User.tg==tg))).scalar_one_or_none()

async def add(s,u,n,kind,text=""):
    u.balance+=n
    s.add(Tx(user_id=u.id,amount=n,kind=kind,text=text))

async def seed():
    async with Session() as s:
        if not await s.scalar(select(func.count(Case.id))):
            cs=[("Ежедневный кейс","💝",0,1),("Мишка","🧸",15,0),("Ферма звёзд","⭐",25,0),("Ферма мишек","🧸",50,0),("Да / Нет","❓",10,0),("Ферма","🌱",75,0),("Реферальный","👥",100,0),("Выгодный","💰",150,0),("NFT CASE","💎",250,0)]
            for n,e,p,d in cs:
                c=Case(name=n,emoji=e,price=p,daily=bool(d));s.add(c);await s.flush()
                for pn,pe,v,w in [("10 Stars","⭐",10,55),("25 Stars","⭐",25,25),("50 Stars","⭐",50,12),("100 Stars","💎",100,6),("500 Stars","💰",500,2)]:
                    s.add(Prize(case_id=c.id,name=pn,emoji=pe,value=v,weight=w))
        if not await s.scalar(select(func.count(Gift.id))):
            for e,n,p in [("🧸","Мишка",25),("💝","Сердце",50),("🎁","Подарок",75),("🌹","Роза",100),("🎂","Торт",150),("🚀","Ракета",200),("🏆","Кубок",250),("💍","Кольцо",300),("💎","Алмаз",500),("💐","Букетик",750),("🍾","Шампанское",1000)]:
                s.add(Gift(name=n,emoji=e,price=p))
        if not await s.scalar(select(func.count(Task.id))):
            s.add(Task(title="Подписаться на канал",reward=10,channel=CHANNEL))
        await s.commit()

@dp.message(CommandStart())
async def start(m:Message):
    async with Session() as s:
        u=await user(s,m.from_user.id)
        if not u:
            ref=None
            a=m.text.split(maxsplit=1)
            if len(a)>1 and a[1].startswith("ref_"):
                try:
                    rid=int(a[1][4:])
                    if rid!=m.from_user.id: ref=await user(s,rid)
                except: pass
            u=User(tg=m.from_user.id,username=m.from_user.username,name=m.from_user.first_name,referrer=ref.id if ref else None)
            s.add(u);await s.commit()
    await m.answer("🎁 <b>Добро пожаловать!</b>\n\nПолучи Telegram подарки, Звёзды и NFT бесплатно!\n\nВыбирай раздел:",reply_markup=menu(),parse_mode="HTML")

@dp.callback_query(F.data=="menu")
async def main(c:CallbackQuery):
    await c.message.edit_text("🎁 <b>Главное меню</b>",reply_markup=menu(),parse_mode="HTML");await c.answer()

@dp.callback_query(F.data=="profile")
async def profile(c:CallbackQuery):
    async with Session() as s:
        u=await user(s,c.from_user.id)
        refs=await s.scalar(select(func.count(User.id)).where(User.referrer==u.id))
        me=await bot.get_me();link=f"https://t.me/{me.username}?start=ref_{u.tg}"
        kb=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Пополнить",callback_data="deposit")],
            [InlineKeyboardButton(text="👥 Рефералы",callback_data="refs")],
            [InlineKeyboardButton(text="🔔 Уведомления",callback_data="notify")],
            [InlineKeyboardButton(text="◀️ Меню",callback_data="menu")]])
        txt=f"👤 <b>Профиль</b>\n\n🆔 ID: <code>{u.tg}</code>\n⭐ Баланс: <b>{u.balance}</b>\n💰 Пополнено: <b>{u.deposits}</b>\n🎁 Призов: <b>{u.prizes}</b>\n👥 Рефералов: <b>{refs}</b>\n📅 Регистрация: <b>{u.created:%d.%m.%Y}</b>\n\n🛟 Поддержка: {SUPPORT}\n\n🔗 Реферальная ссылка:\n<code>{link}</code>"
        await c.message.edit_text(txt,reply_markup=kb,parse_mode="HTML")
    await c.answer()

@dp.callback_query(F.data=="notify")
async def notify(c:CallbackQuery):
    async with Session() as s:
        u=await user(s,c.from_user.id);u.notifications=not u.notifications;await s.commit()
        await c.answer("🔔 Уведомления "+("включены" if u.notifications else "выключены"),show_alert=True)

@dp.callback_query(F.data=="refs")
async def refs(c:CallbackQuery):
    async with Session() as s:
        u=await user(s,c.from_user.id);n=await s.scalar(select(func.count(User.id)).where(User.referrer==u.id));me=await bot.get_me()
        link=f"https://t.me/{me.username}?start=ref_{u.tg}"
    await c.message.edit_text(f"👥 <b>Рефералы</b>\n\nПриглашено: <b>{n}</b>\nДоход: <b>{REF_PERCENT}%</b> от пополнений друзей.\n\n<code>{link}</code>",reply_markup=back("profile"),parse_mode="HTML");await c.answer()

@dp.callback_query(F.data=="cases")
async def cases(c:CallbackQuery):
    async with Session() as s:
        rows=(await s.execute(select(Case).where(Case.active==True,Case.daily==False))).scalars().all()
    kb=[[InlineKeyboardButton(text=f"{x.emoji} {x.name} — {x.price}⭐",callback_data=f"case:{x.id}")] for x in rows]+[[InlineKeyboardButton(text="◀️ Назад",callback_data="menu")]]
    await c.message.edit_text("⭐ <b>Кейсы</b>\n\nВыбери кейс:",reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML");await c.answer()

def pick(ps):
    return random.choices(ps,weights=[max(0,x.weight) for x in ps],k=1)[0]

@dp.callback_query(F.data.startswith("case:"))
async def case(c:CallbackQuery):
    cid=int(c.data.split(":")[1])
    async with Session() as s:
        u=await user(s,c.from_user.id);cs=await s.get(Case,cid);ps=(await s.execute(select(Prize).where(Prize.case_id==cid))).scalars().all()
        if not cs or not ps: return await c.answer("Кейс недоступен",show_alert=True)
        if u.balance<cs.price:return await c.answer("❌ Недостаточно Stars",show_alert=True)
        u.balance-=cs.price;p=pick(ps);u.prizes+=1;await add(s,u,p.value,"case_prize",cs.name);s.add(Tx(user_id=u.id,amount=-cs.price,kind="case",text=cs.name));await s.commit()
    await c.message.edit_text(f"🎉 <b>Кейс открыт!</b>\n\n{p.emoji} <b>{p.name}</b>\n⭐ +{p.value} Stars",reply_markup=back(),parse_mode="HTML");await c.answer()

@dp.callback_query(F.data=="daily")
async def daily(c:CallbackQuery):
    async with Session() as s:
        u=await user(s,c.from_user.id);now=datetime.now(timezone.utc)
        if u.daily and u.daily+timedelta(hours=24)>now:return await c.answer("⏳ Ежедневный кейс доступен раз в 24 часа.",show_alert=True)
        ps=(await s.execute(select(Prize).join(Case,Case.id==Prize.case_id).where(Case.daily==True,Case.active==True))).scalars().all()
        if not ps:return await c.answer("Кейс ещё не настроен",show_alert=True)
        p=pick(ps);u.daily=now;u.prizes+=1;await add(s,u,p.value,"daily","daily");await s.commit()
    await c.message.edit_text(f"💝 <b>Ежедневный кейс</b>\n\n🎁 {p.emoji} <b>{p.name}</b>\n⭐ +{p.value} Stars",reply_markup=back(),parse_mode="HTML");await c.answer()

@dp.callback_query(F.data=="shop")
async def shop(c:CallbackQuery):
    async with Session() as s: gs=(await s.execute(select(Gift).where(Gift.active==True))).scalars().all()
    kb=[[InlineKeyboardButton(text=f"{g.emoji} {g.name} — {g.price}⭐",callback_data=f"gift:{g.id}")] for g in gs]+[[InlineKeyboardButton(text="◀️ Назад",callback_data="menu")]]
    await c.message.edit_text("🎁 <b>Магазин подарков</b>",reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML");await c.answer()

@dp.callback_query(F.data.startswith("gift:"))
async def gift(c:CallbackQuery):
    gid=int(c.data.split(":")[1])
    async with Session() as s:
        u=await user(s,c.from_user.id);g=await s.get(Gift,gid)
        if not g:return await c.answer("Нет такого подарка",show_alert=True)
        if u.balance<g.price:return await c.answer("❌ Недостаточно Stars",show_alert=True)
        u.balance-=g.price;s.add(Tx(user_id=u.id,amount=-g.price,kind="gift",text=g.name));await s.commit()
    await c.message.edit_text(f"🎁 <b>Заказ принят</b>\n\n{g.emoji} {g.name}\n⭐ {g.price}\n\nВыдача Telegram Gift подключается через Bot API после настройки telegram_gift_id.",reply_markup=back(),parse_mode="HTML");await c.answer()

@dp.callback_query(F.data=="tasks")
async def tasks(c:CallbackQuery):
    async with Session() as s: ts=(await s.execute(select(Task).where(Task.active==True))).scalars().all()
    kb=[[InlineKeyboardButton(text=f"🎁 {t.title} +{t.reward}⭐",callback_data=f"task:{t.id}")] for t in ts]+[[InlineKeyboardButton(text="◀️ Назад",callback_data="menu")]]
    await c.message.edit_text("🎁 <b>Задания</b>",reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML");await c.answer()

async def subscribed(tg,channel):
    try:
        m=await bot.get_chat_member(channel,tg)
        return m.status in {"creator","administrator","member"} or (m.status=="restricted" and m.is_member)
    except:return False

@dp.callback_query(F.data.startswith("task:"))
async def task(c:CallbackQuery):
    tid=int(c.data.split(":")[1])
    async with Session() as s:
        u=await user(s,c.from_user.id);t=await s.get(Task,tid)
        old=(await s.execute(select(UserTask).where(UserTask.user_id==u.id,UserTask.task_id==tid))).scalar_one_or_none()
        if old and old.done:return await c.answer("Уже выполнено",show_alert=True)
        if t.channel and not await subscribed(u.tg,t.channel):
            kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 Подписаться",url="https://t.me/"+t.channel.lstrip("@"))],[InlineKeyboardButton(text="✅ Проверить",callback_data=f"task:{tid}")]])
            await c.message.edit_text("❌ Подпишись на канал и нажми «Проверить».",reply_markup=kb);return await c.answer()
        if not old:old=UserTask(user_id=u.id,task_id=tid);s.add(old)
        old.done=True;await add(s,u,t.reward,"task",t.title);await s.commit()
    await c.message.edit_text(f"🎉 <b>Готово!</b>\n⭐ +{t.reward}",reply_markup=back(),parse_mode="HTML");await c.answer()

@dp.callback_query(F.data=="deposit")
async def deposit(c:CallbackQuery):
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ 50",callback_data="pay:50"),InlineKeyboardButton(text="⭐ 100",callback_data="pay:100")],
        [InlineKeyboardButton(text="⭐ 250",callback_data="pay:250"),InlineKeyboardButton(text="⭐ 500",callback_data="pay:500")],
        [InlineKeyboardButton(text="⭐ 1000",callback_data="pay:1000")],[InlineKeyboardButton(text="◀️ Назад",callback_data="profile")]])
    await c.message.edit_text("⭐ <b>Пополнение</b>\n\nВыбери сумму:",reply_markup=kb,parse_mode="HTML");await c.answer()

@dp.callback_query(F.data.startswith("pay:"))
async def pay(c:CallbackQuery):
    n=int(c.data.split(":")[1]);payload=f"deposit:{c.from_user.id}:{n}:{random.randint(10000,99999)}"
    await bot.send_invoice(c.from_user.id,f"Пополнение {n} Stars",f"Внутренний баланс бота: {n} Stars",payload,"", "XTR",[LabeledPrice(label="Stars",amount=n)]);await c.answer()

@dp.pre_checkout_query()
async def checkout(q:PreCheckoutQuery): await q.answer(ok=True)

@dp.message(F.successful_payment)
async def paid(m:Message):
    p=m.successful_payment
    async with Session() as s:
        if await s.scalar(select(Payment).where(Payment.charge==p.telegram_payment_charge_id)):return
        u=await user(s,m.from_user.id)
        if not u:return
        n=p.total_amount;u.balance+=n;u.deposits+=n;s.add(Payment(user_id=u.id,amount=n,charge=p.telegram_payment_charge_id,payload=p.invoice_payload));s.add(Tx(user_id=u.id,amount=n,kind="deposit",text="Telegram Stars"))
        if u.referrer:
            r=await s.get(User,u.referrer);reward=n*REF_PERCENT//100
            if r and reward:r.balance+=reward;s.add(Tx(user_id=r.id,amount=reward,kind="referral",text="Referral"))
        await s.commit()
    await m.answer(f"✅ Оплата успешна!\n⭐ Зачислено: <b>{n}</b>",parse_mode="HTML")

@dp.message(Command("admin"))
async def admin(m:Message):
    if m.from_user.id not in ADMINS:return await m.answer("⛔ Доступ запрещён.")
    await m.answer("🛠 <b>Админ-панель</b>\n\n/admin — открыть статистику",parse_mode="HTML")

@dp.message(Command("stats"))
async def stats(m:Message):
    if m.from_user.id not in ADMINS:return
    async with Session() as s:
        users=await s.scalar(select(func.count(User.id)));deposits=await s.scalar(select(func.coalesce(func.sum(Payment.amount),0)));balance=await s.scalar(select(func.coalesce(func.sum(User.balance),0)))
    await m.answer(f"📊 <b>Статистика</b>\n\n👥 Пользователей: {users}\n💰 Пополнено: {deposits}⭐\n⭐ Балансы: {balance}⭐",parse_mode="HTML")

async def main():
    if not TOKEN: raise RuntimeError("Укажи BOT_TOKEN")
    logging.basicConfig(level=logging.INFO)
    async with engine.begin() as c: await c.run_sync(Base.metadata.create_all)
    await seed()
    await dp.start_polling(bot)

if __name__=="__main__": asyncio.run(main())
