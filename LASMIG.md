# Vinted-bevakaren

Söker på Vinted var tredje minut med dina sparade sökningar och skickar nya annonser till Telegram med bild, pris och länk.

## Hemsidan och Telegram
- `hemsida/index.html` är din alarm-sida. Där lägger du till alarm och ser alla träffar.
- Telegram skickar bara **kap**: priset är högst ditt kap-pris, eller (utan kap-pris) högst hälften av vanliga priset för sökningen. Per alarm kan du välja "Bara kap", "Alla nya träffar" eller "Inga".
- `traffar.json` skapas automatiskt och är det hemsidan visar. Varje runda kollar boten några av annonserna på hemsidan och tar bort de som är sålda eller borttagna på Vinted.
- På GitHub körs allt var 5:e minut av `.github/workflows/bevaka.yml`.

## Filer
- `vinted_bot.py` – själva programmet (behöver bara Python 3, inget att installera).
- `sokningar.json` – dina bevakningar. Ändra här, ändringen gäller från nästa runda.
- `installningar.json` – Telegram-token, chat-id och hur ofta det ska sökas.
- `sedda.json` – skapas automatiskt och minns vilka annonser du redan fått.
- `minne.json` – skapas automatiskt och minns priser, säljare och märken.

## En bevakning
```json
{
  "namn": "Nudie jeans under 200 kr",
  "sokord": "nudie jeans",
  "kon": "herr",
  "kategorier": ["klader"],
  "lander": ["SE", "DK", "FI"],
  "maxpris": 200,
  "minpris": 50,
  "marke": "Nudie",
  "storlekar": ["W30", "W31", "M"],
  "skick": ["Ny med prislapp", "Ny utan prislapp", "Mycket bra"],
  "uteslut": ["t-shirt", "jacka"],
  "kappris": 120,
  "frakt": 60,
  "min_betyg": 4.5,
  "telegram": "kap",
  "aktiv": true
}
```
Allt utom `namn` och `sokord` kan lämnas bort. Tom lista betyder "alla". Enklast är att ändra på hemsidan.

- `kon` och `kategorier`: "herr" eller "dam", och kategorierna klader, skor, accessoarer (och vaskor för dam).
  Botten använder Vinteds egna filter, så du får bara rätt sorts saker.
- `sokord` och `marke` kan vara en text eller en lista, t.ex. `["skjorta", "oxford"]`. Ett sökord räcker för träff, och flera märken bevakas samtidigt.
- `marke`: botten slår upp märket hos Vinted och söker bara på det märket.
- `storlekar`: måste stämma exakt, så "S" träffar inte "XS".
- `maste`: fraser som måste stå i titeln, t.ex. `["regular alf"]` för en viss modell. Alla ord i frasen måste finnas, och en av fraserna räcker.
- `farger`: Vinteds färgfilter, t.ex. `["Svart", "Marinblå"]`. Tomt = alla färger. Färger som finns: Svart, Grå, Vit, Crèmefärgad, Beige, Aprikos, Orange, Korall, Röd, Vinröd, Rosa, Ros, Lila, Syrenlila, Ljusblå, Blå, Marinblå, Turkos, Mint, Grön, Mörkgrön, Khaki, Brun, Senapsgul, Gul, Silver, Guld, Flerfärgad, Genomskinlig.
- `skick`: används också som Vinted-filter. Skick som finns: Ny med prislapp, Ny utan prislapp, Mycket bra, Bra, Tillfredsställande.
- `lander`: vilka länder säljaren ska bo i. På svenska Vinted kan du köpa från SE (Sverige), DK (Danmark), FI (Finland) och PL (Polen).
- `min_betyg`: säljare med lägre snittbetyg (stjärnor) hoppas över. Säljare utan omdömen är okej. 0 stänger av.
- Säljpriset uppskattas automatiskt: botten söker (var 6:e timme) på samma sak utan prisgräns och tar priset där
  40 % av liknande annonser är billigare, justerat för skicket. Vinsten = säljpris − (pris + Vinteds avgift + `frakt`).
- Efterfrågan (låg/medel/hög) räknas på hur många som brukar gilla liknande annonser.
- Vanligt pris räknas på alarmets träffar de senaste 30 dagarna (minst 8 st), och kap räknas mot det.

Vill du ha andra filter från Vinted (färg osv.)? Gör sökningen på vinted.se, kopiera länken och skriv
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
