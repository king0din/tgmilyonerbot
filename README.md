# Kim Milyoner Olmak İster Telegram Botu
Bu proje, Telegram gruplarında "Kim Milyoner Olmak İster?" yarışmasını oynatmak için bir botdur.
## Özellikler
- Gruplarda çoklu oyuncu ile yarışma
- Her soru için 90 saniye cevaplama süresi
- Zorluk seviyeleri (1-10 arası)
- İstatistik takibi (oyun sayısı, doğru cevaplar, kazanılan oyunlar)
- Özel mesajlar ile soru gönderilir
## Kurulum
### Gereksinimler
- Python 3.6 veya üzeri
- `pip` paket yöneticisi
### Adımlar
1. Depoyu klonlayın:
   ```bash
   git clone https://github.com/king0din/tgmilyonerbot.git
   cd tgmilyonerbot
   ```
2. Sanal ortam oluşturup etkinleştirin (isteğe bağlı):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Linux/Mac için bu komut
   venv\Scripts\activate  # Windows içinde bu komutu kulanın
   ```
3. Gerekli kütüphaneleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```
4. Soruları hazırlayın:
   - `questions` dizinin içinde ki zorluk seviyelerine göre json dosyaları var bunların içerisinse örnek sorular var içerisine bulabildiğiniz kadar soru doldurun:
     ```bash
     cd questions
     ```
   - Her zorluk seviyesi için 1 ila 10 arazında zorluk seviyesi olan JSON dosyaları vardır (örnek: `level_1.json`, `level_2.json`, ... `level_10.json`). Her dosya, aşağıdaki formattaki gibi sorular içermelidir:
     ```json
     [
         {
             "question": "Soru metni",
             "options": ["Seçenek1", "Seçenek2", "Seçenek3", "Seçenek4"],
             "correct": "Doğru Seçenek"
         },
         {
             "question": "Soru metni2",
             "options": ["Seçenek1", "Seçenek2", "Seçenek3", "Seçenek4"],
             "correct": "Doğru Seçenek"
         }
     ]
     ```
     - Aşağıdaki komutu kullanarak dosyayı açıp içine sorular ekleyebilirsiniz dilersenizde şimdilik bu adımı atlayabilirsiniz.
       ```bash
       nano level_1.json
       ```
       windows için:
       ```bash
       notepad level_1.json
       ```
       veya hangi zorluk sevyesindeki dosyaya eklemek istiyorsanız numarasını yazablirsiniz `nano level_(zorluk_numarası_buraya).json`
       -NOT: varsayılan olarak 1000 adet soru eklidir
       
5. Bot tokenini ayarlayın:
   - `milyoner_bot.py` dosyasını açın:
```bash
nano milyoner_bot.py
```
-windows için:
```bash
notepad milyoner_bot.py
```

- `TOKEN` değişkenini bulup kendi bot tokeninizle değiştirin:
     ```python
     # Bot token
     TOKEN = "bot_tokeniniz_buraya"
     bot = telebot.TeleBot(TOKEN)
     ```
6. Veritabanını başlatılması:
   - Botu ilk çalıştırdığınızda `milyoner_bot.db` adında bir SQLite veritabanı otomotik oluşturulacaktır.
## Çalıştırma
Botu çalıştırmak için:
```bash
python milyoner_bot.py
```

## Kullanım
1. Botu bir Telegram grubuna ekleyin.
2. Grupta `/yeniyarisma` komutu ile yeni bir yarışma başlatın (sadece yöneticiler).
3. Katılımcılar `/katil` komutu veya buton ile yarışmaya katılır.
4. Yeterli katılımcı olduğunda, yarışma sahibi `/baslat` komutu ile yarışmayı başlatır.
5. Sorular özel mesaj olarak gönderilir. Yarışmacılar 30 saniye içinde cevap verir.
6. 2 yanlış cevap veren elenir. Son kalan yarışmacı kazanır.

## Komutlar
- `/start` v `/yardim`: Bot hakkında bilgi ve komut listesi.
- `/yeniyarisma [raunt sayısı]`: Yeni yarışma başlatır (varsayılan raunt: 10).
- `/katil`: Aktif yarışmaya katılır.
- `/baslat`: Yarışmayı başlatır (sadece yarışma sahibi).
- `/iptal`: Yarışmayı iptal eder (sadece yarışma sahibi veya yönetici).
- `/durum`: Yarışmanın mevcut durumunu gösterir.
- `/istatistik`: Özel sohbette kullanıcı istatistiklerini gösterir.
```
### Dosya Yapısı
Proje dizini şöyle olmalı:
tgmilyonerbot/
├── bot.py
├── requirements.txt
├── README.md
├── questions/
│   ├── level_1.json
│   ├── level_2.json
│   └── ... (level_3.json ... level_10.json)
└── milyoner_bot.db (çalıştırdıktan sonra oluşacak)
```
