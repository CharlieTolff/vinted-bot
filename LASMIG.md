# Vinted-bevakaren

Söker på Vinted var tredje minut med dina sparade sökningar och skickar nya annonser till Telegram med bild, pris och länk.

## Hemsidan och Telegram
- `hemsida/index.html` är din alarm-sida. Där lägger du till alarm och ser alla träffar.
- Telegram skickar bara **kap**: priset är högst ditt kap-pris, eller (utan kap-pris) högst hälften av vanliga priset för sökningen. Per alarm kan du välja "Bara kap", "Alla nya träffar" eller "Inga".
- `traffar.json` skapas automatiskt och är det hemsidan visar.
- På GitHub körs allt var 5:e minut av `.github/workflows/bevaka.yml`.

## Filer
- `vinted_bot.py` – själva programmet (behöver bara Python 3, inget att installera).
- `sokningar.json` – dina bevakningar. Ändra här, ändringen gäller från nästa runda.
- `installningar.json` – Telegram-token, chat-id och hur ofta det ska sökas.
- `sedda.json` – skapas automatiskt och minns vilka annonser du redan fått.

## En bevakning
```json
{
  "namn": "Nudie jeans under 200 kr",
  "sokord": "nudie jeans",
  "maxpris": 200,
  "minpris": 50,
  "marke": "Nudie",
  "storlekar": ["W30", "W31", "M"],
  "skick": ["Ny med prislapp", "Ny utan prislapp", "Mycket bra"],
  "uteslut": ["t-shirt", "jacka"],
  "kappris": 120,
  "telegram": "kap",
  "aktiv": true
}
```
Allt utom `namn` och `sokord` kan lämnas bort. Tom lista betyder "alla".
Skick som finns: Ny med prislapp, Ny utan prislapp, Mycket bra, Bra, Tillfredsställande.

Vill du ha Vinteds egna filter (kategori, färg osv.)? Gör sökningen på vinted.se, kopiera länken och skriv
`"url": "https://www.vinted.se/catalog?..."` i stället för `sokord`.

## Skaffa en Telegram-bot (5 min)
1. Öppna Telegram och sök på **@BotFather**.
2. Skriv `/newbot`, välj ett namn och ett användarnamn som slutar på `bot`.
3. Du får en **token** (ser ut som `123456:ABC-...`). Lägg in den i `installningar.json`.
4. Öppna din nya bot i Telegram och skicka "hej" till den.
5. Kör `python3 vinted_bot.py --hitta-chat-id` och lägg in siffran som `telegram_chat_id`.

## Köra
- `python3 vinted_bot.py --test` skickar de 3 senaste träffarna, så du ser att notiserna funkar.
- `python3 vinted_bot.py` bevakar tills du stänger av den.
- Första gången sparas alla nuvarande annonser som "sedda", så du bara får helt nya.
