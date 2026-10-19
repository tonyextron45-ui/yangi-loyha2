# Kino Vibeuz — Python Telegram bot

## Funksiyalar
- Foydalanuvchi kino kodini yuboradi va bot filmni jo‘natadi.
- Majburiy kanal obunasi; Premium foydalanuvchilar uchun obuna tekshiruvi chetlab o‘tiladi.
- Admin panel: kino qo‘shish, tahrirlash, o‘chirish va statistika.
- Kanalga kirish/chiqish hodisalari statistikasi.
- Premium so‘rovi va admin orqali faollashtirish.
- Rasm/video reklama so‘rovi va admin tasdig‘i.
- Referal havola va takliflar statistikasi.
- Start/yordam matnlarini tahrirlash va xabar tarqatish.
- Render health endpoint va SQLite persistent disk.

## O‘rnatish
1. `@BotFather` orqali Telegram bot yarating.
2. Admin Telegram ID'ingizni aniqlang.
3. GitHub repository'ga ZIP ichidagi fayllarni yuklang.
4. Render'da **New → Blueprint** orqali `render.yaml` bilan deploy qiling.
5. Render Environment Variables'ga `BOT_TOKEN`, `ADMIN_IDS` (masalan `123456789,987654321`), `PREMIUM_PRICE`, `PAYMENT_INFO` kiriting.
6. Botni majburiy kanal(lar)ga admin qilib qo‘shing.

## Buyruqlar
- `/start`, `/help`, `/admin`
- `/addchannel @kanal`, `/delchannel @kanal`
- `/channelstats`
- `/grantpremium USER_ID 30` yoki `/grantpremium USER_ID forever`
- `/setstart Yangi matn`, `/sethelp Yangi matn`
- `/premium`, `/ad`, `/ref`

## Admin panel
Kino qo‘shish: `KOD | NOMI | TAVSIF` yuboring, keyin media yuboring.
Kino tahrirlash: `KOD | YANGI NOMI | YANGI TAVSIF`.
Kino o‘chirish: kodni yuboring.
Reklama so‘rovlarini tasdiqlash/rad etish: Admin panel → Reklamalar.

## Muhim cheklovlar
- Bot kanal a’zoligini tekshirishi va kanalga kirish/chiqish hodisalarini kuzatishi uchun har bir kanalga admin qilib qo‘shilishi kerak.
- Kanal statistikasi bot qo‘shilgan va hodisalarni qabul qila boshlagan vaqtdan boshlab sanaydi; oldingi obunachilar tarixi Telegram Bot API orqali to‘liq olinmaydi.
- Referal hisobi botdagi `/start=ref...` havolasi orqali birinchi marta kirganlarni sanaydi. Kanalga kirib-chiqishni har bir referalga aniq bog‘lash uchun maxsus invite-link oqimi qo‘shimcha sozlanishi kerak.
- Premium to‘lovi avtomatik qabul qilinmaydi: admin to‘lovni tekshirib `/grantpremium` bilan faollashtiradi.
- Reklama xizmati buyurtmani admin ko‘rib chiqishiga yuboradi; kanalda real joylashtirishni admin alohida bajaradi.
- Faqat tarqatish huquqingiz bor filmlarni joylang.
- Ishga tushirishdan oldin test bot va test kanalda tekshirib ko‘ring.
